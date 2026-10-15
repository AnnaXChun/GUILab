import ast
import json
from pathlib import Path
import pytest
from cad_cf.cadworld_adapter import agent_view
from cad_cf.tool_protocol import PolicyError
from cad_cf.mock_backend import initial_state

@pytest.mark.parametrize('field',['evaluation','evaluator','expected','reference_solution_path','host_metrics'])
def test_mock_agent_denied(field):
    view=agent_view({'id':'t','instruction':'x','evaluator':{'expected':'secret'},'reference_solution_path':'secret'},initial_state())
    assert field not in json.dumps(dict(view))
    with pytest.raises(PolicyError):
        _=view[field]
    with pytest.raises(PolicyError):
        view.get(field)

def test_online_modules_do_not_import_official_scoring():
    for path in Path('cad_cf').glob('*.py'):
        if path.name == 'posthoc.py':
            continue
        tree=ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom):
                assert not any(x in (n.module or '') for x in ('evaluators','posthoc','run_single'))

def test_nested_leak_rejected():
    with pytest.raises(PolicyError):
        agent_view({'id':'t','instruction':'x'}, {'objects':[], 'evaluator':{'expected':1}})
