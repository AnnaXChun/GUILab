import copy
import json
from pathlib import Path

import pytest

from cad_cf.cli_pocket_credit import pocket_code, pocket_messages, selection_table, evaluate_isolated
from scripts.run_cli_pocket_credit import composed_worker

CODE = """body=doc.getObject('Body')
sketch=doc.getObject('Sketch')
pad=doc.getObject('Pad')
pocket_sketch=body.newObject('Sketcher::SketchObject','PocketSketch')
pocket_sketch.Placement=sketch.Placement
pocket_sketch.addGeometry(Part.Circle(App.Vector(0,0,0),App.Vector(0,0,1),4),False)
pocket_sketch.addConstraint(Sketcher.Constraint('Radius',0,4))
pocket_sketch.setExpression('Placement.Base.z','Pad.Length')
pocket=body.newObject('PartDesign::Pocket','Pocket')
pocket.Profile=pocket_sketch
pocket.Length=App.Units.Quantity('6 mm')
body.Tip=pocket
"""


def test_pocket_scope_preserves_original_model_text_and_alternative_placement():
    for code in (CODE, CODE.replace("pocket_sketch.setExpression('Placement.Base.z','Pad.Length')",
                                     'pocket_sketch.Placement.Base.z=pad.Length.Value')):
        text = '```json\n' + json.dumps({'code': code}) + '\n```'
        assert pocket_code(text) == code


@pytest.mark.parametrize('extra', ['pad.Length=20', 'sketch.Placement.Base.x=4',
    'pocket_sketch=sketch', 'pocket=pad', "body=doc.getObject('Other')", "doc.saveAs('file')",
    'import os', 'pocket_sketch.Shape=pad.Shape', 'doc=body', 'pocket_sketch.clearGeometry()',
    "pocket_sketch.setExpression('Constraints[0]','Pad.Length')"])
def test_upstream_mutations_and_unreviewed_calls_are_rejected(extra):
    with pytest.raises(ValueError):
        pocket_code(json.dumps({'code': CODE + extra}))


def test_messages_use_public_state_and_explicit_subgoal_without_verifier_results():
    seed = {'spec': {'binding': {'body': 'Body', 'sketch': 'Sketch'}}, 'native_state': {'objects': []},
            'seed_sha256': 'bytes', 'seed_state_sha256': 'native', 'trusted_test': {'gold': 'NEVER_SEND'}}
    pair = {'intent': {'instruction': 'public task', 'subgoal': 'persist pocket on Pad end'}}
    assert pocket_messages(pair, seed) == pocket_messages(pair, seed)
    text = json.dumps(pocket_messages(pair, seed))
    assert 'NEVER_SEND' not in text and 'persist pocket' in text


def result(a, b, valid=True):
    return {'pair_valid': valid, 'A': {'q': a, 'initial_proxy_q': 1},
            'B': {'q': b, 'initial_proxy_q': 1}, 'credit': a-b if valid and a is not None and b is not None else None}


@pytest.mark.parametrize('a,b,selected,swapped', [(1, 0, 'A', 'B'), (0, 1, 'B', 'A'),
                                                (1, 1, 'A', 'A'), (0, 0, 'A', 'A')])
def test_same_reward_equivalence_and_actual_label_swap(a, b, selected, swapped):
    rows = {r['method']: r for r in selection_table(result(a, b))['rows']}
    assert rows['local_credit']['selected'] == rows['response_terminal_best_of_2']['selected'] == selected
    assert rows['swapped_credit']['selected'] == swapped
    assert rows['initial_geometry_best_of_2']['selected'] == 'A'


def test_unknown_or_invalid_pair_does_not_supply_selection_reward():
    for r in (result(None, 1), result(1, 0, valid=False)):
        control = selection_table(r)
        assert not control['shared_reward_equivalence']
        if not r['pair_valid']:
            assert all(x['observed_response_q'] is None for x in control['rows'])
        else:
            assert control['rows'][2]['selected'] is None
    r = result(1, 0)
    r['credit'] = -1
    with pytest.raises(ValueError, match='shared response reward'):
        selection_table(r)


def test_new_vm_proof_is_required_beyond_a_shared_seed(monkeypatch):
    from cad_cf import cli_pocket_credit
    monkeypatch.setattr(cli_pocket_credit, 'evaluate', lambda *args: {'pair_valid': True, 'invalid_reasons': [], 'credit': 1, 'response_discriminating': True})
    a = {'vm_overlay': '/a/disk', 'vm_output': '/a', 'vm_pid': 1, 'snapshot_sha256': 'frozen'}
    b = {'vm_overlay': '/b/disk', 'vm_output': '/b', 'vm_pid': 2, 'snapshot_sha256': 'frozen'}
    assert evaluate_isolated({}, a, b)['pair_valid']
    for key in a:
        bad = copy.deepcopy(b)
        bad[key] = a[key] if key != 'snapshot_sha256' else 'other'
        assert evaluate_isolated({}, a, bad)['credit'] is None


def test_composed_worker_compiles_and_contains_only_frozen_minimal_seed():
    source, finish = composed_worker({'path': '/seed.FCStd', 'spec': {}})
    compile(source, 'new_worker', 'exec')
    assert 'def finish_pocket' in finish and 'def scoped_pocket_code' in source
    from scripts.run_structural_credit_diagnostic import command
    assert max(len(x.encode()) for x in command({'mode': 'prepare'}, source)) < 120000
    config = json.loads((Path(__file__).resolve().parents[1]/'configs/cli_pocket_credit_20261023.json').read_text())
    assert config['max_model_calls'] == 2 and config['max_model_output_tokens'] == 4096
    assert config['max_candidate_dispatches'] == 2 and config['paid_runs_default'] == 0


@pytest.mark.parametrize('uncertain', [False, True])
def test_branch_dispatches_original_once_and_stops_clone_even_on_unknown(tmp_path, monkeypatch, uncertain):
    import base64
    import hashlib
    from types import SimpleNamespace
    from scripts import run_cli_pocket_credit as runner
    from cad_cf.terminal_bridge import ExecutionUncertain
    calls = []
    stopped = []

    class Provider:
        def __init__(self, **runtime):
            self.output = Path(runtime['output'])
            self.current = self.output / 'vm_001'
            self.process = SimpleNamespace(pid=7, poll=lambda: None)
            self.endpoint = 'http://registered'
        def start_emulator(self, base):
            self.current.mkdir(parents=True)
        def stop_emulator(self):
            stopped.append(True)
            self.process = None

    class Bridge:
        def __init__(self, *args, **kwargs):
            pass
        def execute(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            if uncertain:
                raise ExecutionUncertain('unknown no replay')
            data = b'native-fixture-export'
            obs = {'classification': 'fake_native', 'artifact_base64': base64.b64encode(data).decode(),
                   'artifact_sha256': hashlib.sha256(data).hexdigest()}
            return {'output': json.dumps(obs)}
        def close(self):
            pass

    monkeypatch.setattr(runner, 'NativeQemuProvider', Provider)
    monkeypatch.setattr(runner, 'TerminalBridge', Bridge)
    output = tmp_path / 'branch_A'
    if uncertain:
        with pytest.raises(ExecutionUncertain):
            runner.run_branch({'candidates': {'A': CODE}}, {}, 'A', {'base': 'disk'}, output, 'pass', 'sha')
        assert json.loads((output / 'error.json').read_text())['quality'] is None
    else:
        obs = runner.run_branch({'candidates': {'A': CODE}}, {}, 'A', {'base': 'disk'}, output, 'pass', 'sha')
        assert obs['snapshot_sha256'] == 'sha' and obs['vm_pid'] == 7
    assert len(calls) == 1 and stopped == [True]
    assert calls[0][1]['execution_id'] == 'candidate-A'
    assert json.loads((output / 'request.json').read_text())['pair']['candidates']['A'] == CODE
    assert json.loads((output / 'execution_summary.json').read_text())['vm_stopped']
