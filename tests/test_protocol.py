import pytest
from dataclasses import replace
from cad_cf.tool_protocol import TypedAction, PolicyError, validate_gui
from cad_cf.mock_backend import proposals, initial_state
from cad_cf.candidate_generator import paired_candidates
from cad_cf.cadworld_adapter import agent_view

@pytest.mark.parametrize('source', ['import os', 'pyautogui.write("import FreeCAD")', '__import__("os")', 'pyautogui.click(x=f())', 'pyautogui.hotkey("ctrl","alt","terminal")'])
def test_deny_code_or_shell(source):
    with pytest.raises((PolicyError, ValueError)):
        validate_gui(source)

def test_same_intent():
    raw,intent,gui,api = proposals()
    bad = replace(api, intent=replace(intent, target={'Length': 13.}))
    with pytest.raises(PolicyError, match='same-intent'):
        paired_candidates(intent, gui, bad, agent_view(raw, initial_state()), '/home/user/current')

@pytest.mark.parametrize('path', ['/tmp/host.FCStd','/home/user/current/../other.FCStd','/home/user/current/mesh.stl'])
def test_path_boundary(path):
    with pytest.raises(PolicyError):
        TypedAction('save_as', {'path':path}).validate('/home/user/current')

@pytest.mark.parametrize('args', [{'object_name':'Pad','type_id':'PartDesign::Pad','property':'ExpressionEngine','value':12},
                                 {'object_name':'Pad','type_id':'PartDesign::Pad','property':'Length','value':float('nan')}])
def test_property_boundary(args):
    with pytest.raises(PolicyError):
        TypedAction('set_object_property',args).validate('/home/user/current')

@pytest.mark.parametrize('source', ['pyautogui.hotkey("ctrl","alt","t")', 'pyautogui.write("/host/evaluation.json")', 'pyautogui.write("App.ActiveDocument.Pad.Length=13")'])
def test_gui_cannot_become_shell_or_api(source):
    with pytest.raises(PolicyError):
        validate_gui(source)
