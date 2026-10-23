"""Composed with cli_causal_worker; prospective Pad-only S1 and Pocket blocks."""


def finish_pocket(doc, spec):
    body = doc.getObject(spec['binding']['body'])
    body.touch()
    doc.recompute()


def generic_pocket_api_probe(root):
    doc = App.newDocument('GenericPocketApiProbe')
    checks = {}
    try:
        body = doc.addObject('PartDesign::Body', 'ApiBody')
        sketch = body.newObject('Sketcher::SketchObject', 'ApiSketch')
        sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 7), False)
        pad = body.newObject('PartDesign::Pad', 'ApiPad')
        pad.Profile = sketch
        pad.Length = 11
        ps = body.newObject('Sketcher::SketchObject', 'ApiPocketSketch')
        ps.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 2), False)
        ps.addConstraint(Sketcher.Constraint('Radius', 0, 2))
        ps.setExpression('Placement.Base.z', 'ApiPad.Length')
        doc.recompute()
        pocket = body.newObject('PartDesign::Pocket', 'ApiPocket')
        pocket.Profile = ps
        pocket.Length = App.Units.Quantity('3 mm')
        body.Tip = pocket
        doc.recompute()
        checks['profile_link'] = pocket.Profile[0].Name == ps.Name
        checks['base_feature'] = pocket.BaseFeature.Name == pad.Name
        checks['native_validity'] = pocket.Shape.isValid() and len(pocket.Shape.Solids) == 1
        checks['volume'] = math.isclose(pocket.Shape.Volume, math.pi * (49 * 11 - 4 * 3), rel_tol=1e-8)
        path = root / 'api_pocket.FCStd'
        doc.saveAs(str(path))
    finally:
        App.closeDocument(doc.Name)
    before = sha(path)
    doc = App.openDocument(str(path))
    try:
        doc.getObject('ApiPad').Length = 13
        doc.recompute()
        ps = doc.getObject('ApiPocketSketch')
        pocket = doc.getObject('ApiPocket')
        checks['persisted_placement_expression'] = math.isclose(ps.Placement.Base.z, 13, abs_tol=1e-9)
        checks['persisted_parameter_response'] = pocket.Shape.isValid() and math.isclose(
            pocket.Shape.Volume, math.pi * (49 * 13 - 4 * 3), rel_tol=1e-8)
    finally:
        App.closeDocument(doc.Name)
    checks['source_bytes_unchanged'] = sha(path) == before
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'freecad_version': list(App.Version()), 'scope': 'task-independent XY API document'}


def capture_file(path, spec):
    doc = App.openDocument(str(path))
    try:
        doc.recompute()
        state = native_state(doc)
    finally:
        App.closeDocument(doc.Name)
    return {'path': str(path), 'seed_sha256': sha(path), 'seed_state_sha256': digest(state),
            'native_state': state, 'spec': spec, 'captured_before_model_requests': True}


def prepare(request):
    root = Path(request['root'])
    root.mkdir(parents=True, exist_ok=False)
    os.chdir(root)
    original = ORIGINAL_SEED
    if sha(original['path']) != original['seed_sha256']:
        raise RuntimeError('original S0 bytes differ')
    path = root / 'pad_s1.FCStd'
    shutil.copyfile(original['path'], path)
    doc = App.openDocument(str(path))
    try:
        doc.recompute()
        if state_sha(doc) != original['seed_state_sha256']:
            raise RuntimeError('original S0 native state differs')
        spec = original['spec']
        trusted_pad(doc, spec)
        saved = native_state(doc)
        doc.saveAs(str(path))
    finally:
        App.closeDocument(doc.Name)
    seed = capture_file(path, spec)
    if saved != seed['native_state']:
        raise RuntimeError('prospective S1 reopen differs')
    trusted = root / 'trusted_pocket.FCStd'
    shutil.copyfile(path, trusted)
    doc = App.openDocument(str(trusted))
    try:
        continuation(doc, spec)
        built = observe(doc, spec)
        doc.saveAs(str(trusted))
    finally:
        App.closeDocument(doc.Name)
    control = capture_file(trusted, spec)
    if control['native_state'] != built['native']:
        raise RuntimeError('trusted downstream reopen differs')
    tests = []
    for i, probe in enumerate(spec['probes']):
        probe_path = root / ('trusted_probe_' + str(i) + '.FCStd')
        shutil.copyfile(trusted, probe_path)
        doc = App.openDocument(str(probe_path))
        try:
            doc.recompute()
            apply_probe(doc, probe)
            tests.append({'id': probe['id'], 'observation': observe(doc, spec)})
        finally:
            App.closeDocument(doc.Name)
    return {'classification': 'prospective_native_pad_s1_prepare',
            'seeds': {'pocket': seed, 'pocket-control': control},
            'trusted_test': {'reopened': built, 'probes': tests},
            'generic_api_probe': generic_pocket_api_probe(root),
            'source_s0_unchanged': sha(original['path']) == original['seed_sha256'],
            'freecad_version': list(App.Version()), 'pid': os.getpid()}


def execute(request):
    pair, branch, seed = request['pair'], request['branch'], request['seed']
    for key in ('intent', 'spec', 'probes', 'continuation'):
        if digest(pair[key]) != pair['hashes'][key + '_sha256']:
            raise ValueError('pair content hash mismatch')
    code = pair['candidates'][branch]
    if digest(code) != pair['hashes']['candidate_sha256'][branch]:
        raise ValueError('candidate hash mismatch')
    if not pair.get('control') and pair['continuation'] != FINISH_SOURCE:
        raise ValueError('frozen finish differs')
    root = Path(request['root'])
    root.mkdir(parents=True, exist_ok=False)
    os.chdir(root)
    source = Path(seed['path'])
    path = root / 'seed.FCStd'
    shutil.copyfile(source, path)
    if sha(path) != seed['seed_sha256']:
        raise RuntimeError('S1 byte mismatch')
    doc = App.openDocument(str(path))
    try:
        doc.recompute()
        before = native_state(doc)
        if digest(before) != seed['seed_state_sha256']:
            raise RuntimeError('S1 native state mismatch')
        if pair.get('control'):
            if code != "doc.getObject('AuditNote').Text=" + repr('control-' + branch):
                raise ValueError('unknown negative control')
        else:
            b = pair['spec']['binding']
            if scoped_pocket_code(json.dumps({'code': code}), body_name=b['body'], sketch_name=b['sketch']) != code:
                raise ValueError('candidate was modified')
        exec(code, {'doc': doc, 'App': App, 'Part': Part, 'Sketcher': Sketcher, 'math': math,
                    '__builtins__': {'float': float, 'len': len, 'abs': abs}})
        finish_pocket(doc, pair['spec'])
        built = observe(doc, pair['spec'])
        after = {o['name']: o for o in built['native']['objects']}
        protected = [o for o in before['objects'] if o['name'] not in (pair['spec']['binding']['body'], 'AuditNote')]
        if any(after.get(o['name']) != o for o in protected):
            raise RuntimeError('protected upstream objects changed')
        artifact = root / 'artifact.FCStd'
        doc.saveAs(str(artifact))
    finally:
        App.closeDocument(doc.Name)
    artifact_sha = sha(artifact)
    doc = App.openDocument(str(artifact))
    try:
        doc.recompute()
        reopened = observe(doc, pair['spec'])
        if reopened['native'] != built['native']:
            raise RuntimeError('artifact reopen differs')
    finally:
        App.closeDocument(doc.Name)
    rows = []
    for i, probe in enumerate(pair['probes']):
        path = root / ('probe_' + str(i) + '.FCStd')
        shutil.copyfile(artifact, path)
        doc = App.openDocument(str(path))
        try:
            doc.recompute()
            if native_state(doc) != reopened['native']:
                raise RuntimeError('parameter probe clone differs')
            apply_probe(doc, probe)
            rows.append({'id': probe['id'], 'observation': observe(doc, pair['spec']),
                         'source_artifact_sha256': artifact_sha,
                         'candidate_reexecuted': False, 'suffix_reexecuted': False})
        finally:
            App.closeDocument(doc.Name)
        if sha(path) != artifact_sha:
            raise RuntimeError('parameter probe source saved')
    return {'classification': 'native_cli_pocket_boundary_execution',
            **{k: v[branch] if k == 'candidate_sha256' else v for k, v in pair['hashes'].items()},
            'seed_sha256': seed['seed_sha256'], 'seed_state_sha256': seed['seed_state_sha256'],
            'artifact_sha256': artifact_sha, 'artifact_base64': base64.b64encode(artifact.read_bytes()).decode(),
            'source_seed_unchanged': sha(source) == seed['seed_sha256'], 'native_reopen_equal': True,
            'protected_source_preserved': True, 'probes_from_artifact_copies': True,
            'candidate_executions': 1, 'pid': os.getpid(), 'workdir': str(root),
            'freecad_version': list(App.Version()), 'initial': built, 'reopened': reopened, 'probes': rows}
