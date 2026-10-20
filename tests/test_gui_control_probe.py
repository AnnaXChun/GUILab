import json
import pytest
from cad_cf.gui_control_probe import ControlProbe,INSPECTOR,_widget,_check_counts


def state(objects=(),widgets=()):
    return {'documents':[{'objects':list(objects)}],'widgets':list(widgets),'frame':[0,0,1920,1080],'pid':123}


def test_pending_gui_action_is_not_replayed(monkeypatch,tmp_path):
    probe=ControlProbe.__new__(ControlProbe);probe.output=tmp_path
    probe.deadline=float('inf');probe.last=None
    ready=state([{'type_id':'PartDesign::Body'}])
    rows=iter([state(),ready,ready,ready]);calls=[]
    probe._observe=lambda:next(rows)
    probe._execute=lambda source,label:calls.append(label)
    probe._emit=lambda *a,**kw:None
    from cad_cf import gui_control_probe as module
    monkeypatch.setattr(module.time,'sleep',lambda seconds:None)
    class Response:
        content=b'\x89PNG synthetic trace image'
        def raise_for_status(self):pass
    probe.provider=type('Provider',(),{'endpoint':'http://unused'})()
    monkeypatch.setattr(module.requests,'get',lambda *a,**kw:Response())
    probe._action('new_body','pyautogui.click(10,10)',lambda s:bool(s['documents'][0]['objects']))
    assert calls==['new_body']


def test_dialog_move_during_screenshot_refreshes_coordinates_without_reopening(monkeypatch,tmp_path):
    from cad_cf import gui_control_probe as module
    probe=ControlProbe.__new__(ControlProbe);probe.output=tmp_path;probe.deadline=float('inf')
    old=state(widgets=[{'name':'fileNameEdit','x':759,'y':675}])
    new=state(widgets=[{'name':'fileNameEdit','x':769,'y':715}])
    rows=iter([old,old,new,new,new]);actions=[];captures=[];events=[]
    probe._observe=lambda:next(rows)
    probe._execute=lambda source,label:actions.append(label)
    probe._emit=lambda event,**kw:events.append(event)
    probe.provider=type('Provider',(),{'endpoint':'http://unused'})()
    monkeypatch.setattr(module.time,'sleep',lambda seconds:None)
    class Response:
        content=b'\x89PNG synthetic screenshot'
        def raise_for_status(self):pass
    def capture(*args,**kwargs):captures.append(1);return Response()
    monkeypatch.setattr(module.requests,'get',capture)
    result=probe._action('open_dialog',"pyautogui.hotkey('ctrl','o')",lambda row:True)
    assert actions==['open_dialog'] and len(captures)==2
    assert result['widgets'][0]['y']==715
    assert events==['gui_action','gui_boundary_pending','gui_boundary']


def test_slow_gui_observation_waits_without_resending_request(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from cad_cf import gui_control_probe as module
    clock=[0];calls=[]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda seconds:clock.__setitem__(0,clock[0]+20)))
    probe=ControlProbe.__new__(ControlProbe);probe.output=tmp_path;probe.sequence=0;probe.guest='/home/user/probe';probe.deadline=200
    probe._execute=lambda source,label:calls.append(label)
    probe._file=lambda path:SimpleNamespace(status_code=404 if clock[0]<40 else 200,json=lambda:{'ok':True,'result':state()})
    assert probe._observe()==state()
    assert clock[0]==40 and calls==['inspect']


def test_duplicate_body_is_failure_not_success():
    with pytest.raises(RuntimeError,match='never replay'):
        _check_counts(state([{'type_id':'PartDesign::Body'},{'type_id':'PartDesign::Body'}]))


def test_clipped_done_button_and_ambiguous_control_are_rejected():
    button={'enabled':True,'text':'Done','name':'','cls':'QPushButton','x':1900,'y':50,'width':106,'height':25}
    with pytest.raises(RuntimeError,match='clipped'):_widget(state(widgets=[button]),text='Done')
    button={**button,'x':100}
    with pytest.raises(RuntimeError,match='ambiguous'):_widget(state(widgets=[button,button]),text='Done')


def test_inspector_is_read_only_and_handles_empty_native_shapes():
    compile(INSPECTOR.replace('"__ACTC_INFRA_OUTPUT__"',repr('/home/user/private_probe')),'fixed_inspector','exec')
    assert 'shape.isNull()' in INSPECTOR
    assert not any(name in INSPECTOR for name in ('addObject(','saveAs(','openDocument(','setDatum(','recompute('))
