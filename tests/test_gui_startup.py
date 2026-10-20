import ast
import base64
import configparser
import pytest
from pathlib import Path
from cad_cf.gui_startup import gui_launch_source,validate_alive_timeout


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


@pytest.mark.parametrize('value',[True,False,0,-1,999,600001,1.5,float('nan'),'600000'])
def test_invalid_desktop_alive_policy_rejected_before_guest_execution(value):
    with pytest.raises(ValueError,match='alive timeout'):
        gui_launch_source('/home/user/probe','pass',alive_timeout_ms=value)


def test_desktop_alive_policy_is_opt_in_and_read_back():
    assert validate_alive_timeout(None) is None
    assert validate_alive_timeout(600000)==600000
    default=gui_launch_source('/home/user/probe','pass')
    selected=gui_launch_source('/home/user/probe','pass',alive_timeout_ms=600000)
    compile(selected,'trusted_gui_launcher','exec')
    assert "'requested_alive_timeout_ms':None" in default
    assert "'requested_alive_timeout_ms':600000" in selected
    assert selected.count("setting('set',")==1
    assert "supported_range=setting('range'),before=setting('get')" in selected
    assert "desktop_policy['after']=setting('get')" in selected
    assert "'uint32 600000'" in selected
    assert 'readback mismatch' in selected
    assert 'unix:path=/run/user/1000/bus' in selected


@pytest.mark.parametrize('failure',[None,'set','readback'])
def test_generated_desktop_policy_fails_closed_and_never_retries(tmp_path,failure):
    import json
    from types import SimpleNamespace
    calls=[]
    def run(command,**kwargs):
        operation=command[1];calls.append(operation)
        assert kwargs['timeout']==15
        assert kwargs['env']['DBUS_SESSION_BUS_ADDRESS']=='unix:path=/run/user/1000/bus'
        if failure=='set' and operation=='set':
            return SimpleNamespace(returncode=1,stdout='',stderr='permission denied')
        output='range u 0 4294967295' if operation=='range' else ''
        if operation=='get':output='uint32 5000' if calls.count('get')==1 or failure=='readback' else 'uint32 600000'
        return SimpleNamespace(returncode=0,stdout=output,stderr='')
    tree=ast.parse(gui_launch_source('/home/user/probe','pass',alive_timeout_ms=600000))
    policy_nodes=[n for n in tree.body if
        isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='desktop_policy' for t in n.targets)
        or isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Subscript)]
    context={'env':{},'root':tmp_path,'json':json,'subprocess':SimpleNamespace(run=run)}
    code=compile(ast.Module(body=policy_nodes,type_ignores=[]),'generated_desktop_policy','exec')
    if failure:
        with pytest.raises(RuntimeError,match='policy'):
            exec(code,context)
    else:
        exec(code,context)
        saved=json.loads((tmp_path/'desktop_policy.json').read_text())
        assert saved['before']=='uint32 5000' and saved['after']=='uint32 600000' and saved['changed']
    assert calls==['range','get','set']+([] if failure=='set' else ['get'])


def test_readiness_produces_parseable_acceptance_and_only_one_launch(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace
    from cad_cf import gui_startup
    calls=[]
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):calls.append(kwargs['execution_id']);return {'output':'{"pid":123}','returncode':0}
        def close(self):pass
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    ready={'status':'PASS_GUI_READY','window_visible':True,'window_maximized':True,'pid':123,'documents':[]}
    monkeypatch.setattr(gui_startup.requests,'post',lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:dict(ready)))
    monkeypatch.setattr(gui_startup,'verify_singleton',lambda *a,**kw: {'remaining_pid':123,'singleton_verified':True})
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
        def execute(self,*args,**kwargs):return {'output':'{"pid":123}','returncode':0}
        def close(self):pass
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    ready={'status':'PASS_GUI_READY','window_visible':True,'window_maximized':True,'pid':123,'documents':[],'canvas_warmed':acknowledged}
    monkeypatch.setattr(gui_startup.requests,'post',lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:ready))
    monkeypatch.setattr(gui_startup,'verify_singleton',lambda *a,**kw:{'singleton_verified':True})
    if acknowledged:gui_startup.prepare_gui('http://unused',tmp_path,warm_canvas=True)
    else:
        with pytest.raises(RuntimeError,match='warmup acceptance'):gui_startup.prepare_gui('http://unused',tmp_path,warm_canvas=True)
    tree=ast.parse((tmp_path/'gui_launch_source.py').read_text())
    macro=next(base64.b64decode(n.args[0].value).decode() for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode')
    compile(macro,'warmup_macro','exec')
    assert '.FCStd' not in macro and 'addObject' not in macro
    assert 'saveImage' in macro and 'App.closeDocument(warm_doc.Name)' in macro


@pytest.mark.parametrize('ack_pid',[123,456])
def test_singleton_before_ack_and_ack_belongs_to_launched_process(monkeypatch,tmp_path,ack_pid):
    from types import SimpleNamespace
    from cad_cf import gui_startup
    events=[]
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):
            events.append('launch')
            return {'output':'{"pid":123}','returncode':0}
        def close(self):pass
    def singleton(*args,phase='ready'):
        events.append('singleton_'+phase)
        return {'remaining_pid':123,'singleton_verified':True}
    def poll(*args,**kwargs):
        events.append('poll')
        return SimpleNamespace(status_code=200,json=lambda:{'status':'PASS_GUI_READY','window_visible':True,'window_maximized':True,'pid':ack_pid})
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    monkeypatch.setattr(gui_startup,'verify_singleton',singleton)
    monkeypatch.setattr(gui_startup.requests,'post',poll)
    if ack_pid==123:
        gui_startup.prepare_gui('http://unused',tmp_path)
        assert events==['launch','singleton_startup','poll','singleton_ready']
    else:
        with pytest.raises(RuntimeError,match='PID differs'):
            gui_startup.prepare_gui('http://unused',tmp_path)
        assert events==['launch','singleton_startup','poll']


def test_unsafe_duplicate_aborts_before_waiting_for_macro(monkeypatch,tmp_path):
    from cad_cf import gui_startup
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):return {'output':'{"pid":123}','returncode':0}
        def close(self):pass
    def reject(*args,**kwargs):raise RuntimeError('unexpected second GUI with document')
    def poll(*args,**kwargs):pytest.fail('must not poll/enable GUI after unsafe duplicate')
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    monkeypatch.setattr(gui_startup,'verify_singleton',reject)
    monkeypatch.setattr(gui_startup.requests,'post',poll)
    with pytest.raises(RuntimeError,match='unexpected second GUI'):
        gui_startup.prepare_gui('http://unused',tmp_path)


def test_visible_but_clipped_window_is_not_accepted(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from cad_cf import gui_startup
    class Bridge:
        def __init__(self,*args,**kwargs):pass
        def execute(self,*args,**kwargs):return {'output':'{"pid":123}','returncode':0}
        def close(self):pass
    monkeypatch.setattr(gui_startup,'TerminalBridge',Bridge)
    monkeypatch.setattr(gui_startup,'verify_singleton',lambda *a,**kw:{'singleton_verified':True})
    monkeypatch.setattr(gui_startup.requests,'post',lambda *a,**kw:SimpleNamespace(status_code=200,json=lambda:{'status':'PASS_GUI_READY','window_visible':True,'window_maximized':False,'pid':123}))
    with pytest.raises(RuntimeError,match='controls may be clipped'):
        gui_startup.prepare_gui('http://unused',tmp_path)
