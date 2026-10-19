import ast
import base64
import configparser
import pytest
from pathlib import Path
from cad_cf.gui_startup import gui_launch_source


def test_gui_bootstrap_pins_output_path_and_disables_duplicate_autostart():
    macro='from pathlib import Path\nroot=Path("__ACTC_INFRA_OUTPUT__")\n'
    source=gui_launch_source('/home/user/private_gui_001',macro)
    tree=ast.parse(source)
    compile(source,'trusted_gui_launcher','exec')
    desktop=[];deployed=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        if isinstance(node.func,ast.Attribute) and node.func.attr=='write_text' and isinstance(node.args[0],ast.Constant):
            desktop.append(node.args[0].value)
        if isinstance(node.func,ast.Attribute) and node.func.attr=='b64decode':
            deployed.append(base64.b64decode(node.args[0].value).decode())
    config=configparser.ConfigParser();config.read_string(desktop[0])
    assert config.getboolean('Desktop Entry','Hidden')
    assert not config.getboolean('Desktop Entry','X-GNOME-Autostart-enabled')
    assert '/home/user/private_gui_001' in deployed[0]
    assert '__ACTC_INFRA_OUTPUT__' not in deployed[0]
    assert "env['HOME']" not in source


def test_readiness_produces_parseable_acceptance_and_only_one_launch(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace
    from cad_cf import gui_startup
    calls=[]
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):calls.append(kwargs['execution_id']);return {'output':'{}','returncode':0}
        def close(self):pass
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    ready={'status':'PASS_GUI_READY','window_visible':True,'pid':123,'documents':[]}
    monkeypatch.setattr(gui_startup.requests,'post',lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:dict(ready)))
    monkeypatch.setattr(gui_startup,'verify_singleton',lambda *a: {'remaining_pid':123,'singleton_verified':True})
    result=gui_startup.prepare_gui('http://unused',tmp_path)
    saved=json.loads((tmp_path/'gui_ready.json').read_text())
    assert saved['singleton_verified'] and result['pid']==123
    assert calls==['gui-bootstrap-once']


@pytest.mark.parametrize('acknowledged',[True,False])
def test_render_warmup_requires_ack_and_never_saves_task_geometry(monkeypatch,tmp_path,acknowledged):
    from types import SimpleNamespace
    from cad_cf import gui_startup
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):return {'output':'{}','returncode':0}
        def close(self):pass
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    ready={'status':'PASS_GUI_READY','window_visible':True,'pid':123,'documents':[],'canvas_warmed':acknowledged}
    monkeypatch.setattr(gui_startup.requests,'post',lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:ready))
    monkeypatch.setattr(gui_startup,'verify_singleton',lambda *a:{'singleton_verified':True})
    if acknowledged:gui_startup.prepare_gui('http://unused',tmp_path,warm_canvas=True)
    else:
        with pytest.raises(RuntimeError,match='warmup acceptance'):gui_startup.prepare_gui('http://unused',tmp_path,warm_canvas=True)
    tree=ast.parse((tmp_path/'gui_launch_source.py').read_text())
    macro=next(base64.b64decode(n.args[0].value).decode() for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode')
    compile(macro,'warmup_macro','exec')
    assert '.FCStd' not in macro and 'addObject' not in macro
    assert 'saveImage' in macro and 'App.closeDocument(warm_doc.Name)' in macro
