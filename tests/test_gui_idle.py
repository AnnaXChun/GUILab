import json
import os
import sys
from types import SimpleNamespace as NS
import pytest
from cad_cf import gui_idle


def monitor(monkeypatch,tmp_path):
    clock=NS(now=0.0)
    monkeypatch.setattr(gui_idle.time,'monotonic',lambda:clock.now)
    class Timer:
        def __init__(self,*a):self.timeout=NS(connect=lambda f:None)
        def start(self,*a):pass
    class Progress:
        visible=True
        def isVisible(self):return self.visible
    state=NS(widgets=[],cursor=None,exposed=True,visible=True)
    window=NS(isVisible=lambda:state.visible,windowHandle=lambda:NS(isExposed=lambda:state.exposed))
    app=NS(allWidgets=lambda:state.widgets,overrideCursor=lambda:state.cursor,activeModalWidget=lambda:None)
    monkeypatch.setitem(sys.modules,'PySide',NS(QtCore=NS(QTimer=Timer,Qt=NS(WaitCursor=1,BusyCursor=2)),QtWidgets=NS(QApplication=app,QProgressBar=Progress)))
    namespace=dict(window=window,root=tmp_path)
    exec(compile(gui_idle.MONITOR,'gui_idle_monitor','exec'),namespace)
    (tmp_path/'idle_inbox'/'idle_test.json').write_text('{}')
    return window.ACTC_IDLE_MONITOR,state,clock,Progress


@pytest.mark.parametrize('busy_kind',['progress','cursor','hidden','not_exposed'])
def test_main_thread_monitor_waits_for_busy_to_clear_and_stay_clear(monkeypatch,tmp_path,busy_kind):
    m,state,clock,Progress=monitor(monkeypatch,tmp_path)
    if busy_kind=='progress':state.widgets=[Progress()]
    elif busy_kind=='cursor':state.cursor=NS(shape=lambda:1)
    elif busy_kind=='hidden':state.visible=False
    else:state.exposed=False
    for t in (0,2,10):clock.now=t;m.tick()
    assert not (tmp_path/'idle_test.json').exists()
    state.widgets=[];state.cursor=None;state.visible=True;state.exposed=True
    clock.now=11;m.tick()
    clock.now=12.9;m.tick()
    assert not (tmp_path/'idle_test.json').exists()
    clock.now=13;m.tick()
    row=json.loads((tmp_path/'idle_test.json').read_text())
    assert row==dict(ready=True,marker='idle_test',pid=os.getpid(),elapsed_seconds=13,busy_ticks=3)
    clock.now=100;m.tick()
    assert json.loads((tmp_path/'idle_test.json').read_text())==row


def test_busy_resets_stability_window(monkeypatch,tmp_path):
    m,state,clock,_=monitor(monkeypatch,tmp_path)
    m.tick();clock.now=1.9;state.cursor=NS(shape=lambda:2);m.tick()
    state.cursor=None;clock.now=2;m.tick();clock.now=3;m.tick()
    assert not (tmp_path/'idle_test.json').exists()
    clock.now=4;m.tick()
    assert (tmp_path/'idle_test.json').exists()


@pytest.mark.parametrize('fault',['none','timeout','wrong_pid','extra_data'])
def test_host_poll_never_repeats_marker_or_exposes_state(monkeypatch,tmp_path,fault):
    clock=NS(now=0.0);commands=[];polls=[]
    monkeypatch.setattr(gui_idle.time,'monotonic',lambda:clock.now)
    monkeypatch.setattr(gui_idle.time,'sleep',lambda t:setattr(clock,'now',clock.now+t))
    class Bridge:
        def __init__(self,*a):pass
        def close(self):pass
        def execute(self,cmd,**kw):commands.append((cmd,kw))
    monkeypatch.setattr(gui_idle,'TerminalBridge',Bridge)
    monkeypatch.setattr(gui_idle.uuid,'uuid4',lambda:NS(hex='fixed'))
    def post(url,**kw):
        polls.append(kw)
        row=dict(ready=True,marker='idle_fixed',pid=42,elapsed_seconds=2,busy_ticks=0)
        if fault=='wrong_pid':row['pid']=43
        if fault=='extra_data':row['widgets']='must never propagate'
        return NS(status_code=404 if fault=='timeout' or len(polls)<3 else 200,json=lambda:row)
    monkeypatch.setattr(gui_idle.requests,'post',post)
    barrier=gui_idle.GuiIdleBarrier('http://127.0.0.1:15040',tmp_path,42,seconds=5)
    if fault=='none':assert barrier.wait('one_action') is None
    else:
        with pytest.raises(gui_idle.GuiIdleTimeout):barrier.wait('one_action')
    assert len(commands)==1
    assert all('file_path' in p['data'] and 'json' not in p for p in polls)
    trace=json.loads((tmp_path/'gui_idle.jsonl').read_text())
    assert trace['status']==('READY' if fault=='none' else 'FAILED')
    assert 'widgets' not in json.dumps(trace)


def test_idle_failure_quarantines_without_reexecuting_model_action(monkeypatch,tmp_path):
    from cad_cf import upstream_runtime as runtime
    order=[]
    class Controller:
        http_server='http://127.0.0.1:15040'
        pkgs_prefix='import pyautogui\n{command}'
        def execute_python_command(self,command):raise AssertionError('original')
    def idle_fail(_):order.append('idle');raise gui_idle.GuiIdleTimeout('busy')
    class Provider:
        current=tmp_path;endpoint=Controller.http_server
        gui_idle=NS(wait=idle_fail)
        def __init__(self,**kw):pass
        def stop_emulator(self):order.append('stop')
    class Bridge:
        def __init__(self,*a):pass
        def execute(self,*a,**kw):order.append('action');return {'returncode':0}
        def close(self):pass
    env=NS(create_vm_manager_and_provider=None,MAX_RETRIES=4)
    monkeypatch.setitem(sys.modules,'desktop_env',NS(desktop_env=env))
    monkeypatch.setitem(sys.modules,'desktop_env.controllers.python',NS(PythonController=Controller))
    monkeypatch.setattr(runtime,'install_lazy_registries',lambda _:None)
    monkeypatch.setattr(runtime,'NativeQemuProvider',Provider)
    monkeypatch.setattr(runtime,'TerminalBridge',Bridge)
    cleanup=runtime.install_native_runtime('unused',{'base':str(tmp_path)},on_uncertain=lambda:order.append('block'))
    try:
        env.create_vm_manager_and_provider('docker',None)
        for _ in range(2):
            with pytest.raises(gui_idle.ExecutionUncertain):Controller().execute_python_command('pyautogui.click()')
        assert order==['action','idle','block','stop']
    finally:cleanup()
