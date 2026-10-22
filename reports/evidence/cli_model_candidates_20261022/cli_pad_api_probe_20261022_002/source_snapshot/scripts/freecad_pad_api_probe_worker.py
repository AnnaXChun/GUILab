"""Task-independent native Pad API probe; never used as a model candidate."""


def generic_pad_api_probe(root):
    checks = {}
    interfaces = []
    for creation in ('body.newObject', 'doc.addObject_then_body.addObject'):
        doc = App.newDocument('GenericPadApiProbe')
        path = root / (creation.replace('.', '_') + '.FCStd')
        try:
            body = doc.addObject('PartDesign::Body', 'ProbeBody')
            sketch = body.newObject('Sketcher::SketchObject', 'ProbeSketch')
            sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 3), False)
            if creation == 'body.newObject':
                pad = body.newObject('PartDesign::Pad', 'ProbePad')
            else:
                pad = doc.addObject('PartDesign::Pad', 'ProbePad')
                body.addObject(pad)
            pad.Profile = sketch
            pad.Length = 7
            body.Tip = pad
            doc.recompute()
            checks[creation + ':native_validity'] = pad.Shape.isValid() and len(pad.Shape.Solids) == 1
            checks[creation + ':volume'] = math.isclose(pad.Shape.Volume, math.pi * 9 * 7, rel_tol=1e-8)
            checks[creation + ':body_membership'] = pad in body.Group and body.Tip == pad
            interfaces.append({'creation': creation, 'type': pad.TypeId,
                'Profile': pad.getTypeIdOfProperty('Profile'),
                'Length': pad.getTypeIdOfProperty('Length'),
                'BaseFeature': pad.getTypeIdOfProperty('BaseFeature'),
                'Base_present': 'Base' in pad.PropertiesList,
                'Mode_present': 'Mode' in pad.PropertiesList})
            pad.Length = '8 mm'
            doc.recompute()
            checks[creation + ':length_unit_string'] = math.isclose(pad.Length.Value, 8, abs_tol=1e-9)
            pad.Length = App.Units.Quantity('9 mm')
            doc.recompute()
            checks[creation + ':length_quantity'] = math.isclose(pad.Length.Value, 9, abs_tol=1e-9)
            doc.saveAs(str(path))
        finally:
            App.closeDocument(doc.Name)
        before = sha(path)
        doc = App.openDocument(str(path))
        try:
            doc.recompute()
            pad = doc.getObject('ProbePad')
            profile = pad.Profile
            if isinstance(profile, (tuple, list)):
                profile = profile[0]
            checks[creation + ':reopened_profile'] = profile.Name == 'ProbeSketch'
            pad.Length = 11
            doc.recompute()
            checks[creation + ':persisted_parameter_response'] = math.isclose(pad.Shape.Volume, math.pi * 9 * 11, rel_tol=1e-8)
        finally:
            App.closeDocument(doc.Name)
        checks[creation + ':source_bytes_unchanged'] = sha(path) == before
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
        'interfaces': interfaces, 'freecad_version': list(App.Version()),
        'scope': 'independent XY circle API probe; no supplied task or evaluator input'}
