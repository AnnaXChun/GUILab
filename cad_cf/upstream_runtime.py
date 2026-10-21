"""Explicit exploratory runtime adapters around pinned, unmodified CADWorld.

Lazy registries resolve the exact functions exported by upstream __init__.py.
No metric/getter implementation or expected rule is replaced.
"""
from __future__ import annotations
import ast
import importlib
import importlib.machinery
import json
import requests
from pathlib import Path
import sys
import types
import uuid
from .qemu_runtime import NativeQemuProvider
from .terminal_bridge import TerminalBridge, ExecutionUncertain
from .controller_guard import guarded_post


def lazy_registry(name, directory):
    directory=Path(directory)
    exports={}
    for node in ast.parse((directory/'__init__.py').read_text()).body:
        if isinstance(node,ast.ImportFrom) and node.level==1 and node.module:
            for alias in node.names:
                if alias.name=='*':raise ValueError('wildcard registry not supported')
                exports[alias.asname or alias.name]=(node.module,alias.name)
    module=types.ModuleType(name)
    module.__path__=[str(directory)]
    module.__file__=str(directory/'__init__.py')
    module.__package__=name
    module.__spec__=importlib.machinery.ModuleSpec(name,loader=None,is_package=True)
    module.__spec__.submodule_search_locations=module.__path__
    def resolve(attr):
        if attr not in exports:raise AttributeError(attr)
        source,original=exports[attr]
        value=getattr(importlib.import_module(name+'.'+source),original)
        setattr(module,attr,value)
        return value
    module.__getattr__=resolve
    module.__all__=list(exports)
    return module


def install_lazy_registries(upstream):
    for suffix in ('metrics','getters'):
        name='desktop_env.evaluators.'+suffix
        if name in sys.modules:raise RuntimeError('install lazy registry before importing DesktopEnv')
        sys.modules[name]=lazy_registry(name,Path(upstream)/'desktop_env/evaluators'/suffix)


def install_native_runtime(upstream, config, on_uncertain=None):
    """Install in a dedicated runner process. Returned cleanup is idempotent."""
    install_lazy_registries(upstream)
    from desktop_env import desktop_env as env_module
    from desktop_env.controllers.python import PythonController
    original_factory=env_module.create_vm_manager_and_provider
    original_execute=PythonController.execute_python_command
    original_retries=env_module.MAX_RETRIES
    providers=[];bridges={}
    original_post=requests.post
    config=dict(config)
    class Manager:
        def get_vm_path(self,**kwargs):return str(Path(config['base']).resolve())
        def delete_vm(self,*args,**kwargs):pass
    def factory(provider_name,region,use_proxy=False):
        if provider_name!='docker' or use_proxy:raise ValueError('unsupported exploratory provider request')
        if providers:raise RuntimeError('one environment per bounded runner process required')
        provider=NativeQemuProvider(**config)
        providers.append(provider)
        return Manager(),provider
    def once(controller,command):
        if not providers or providers[0].current is None:raise RuntimeError('no registered VM')
        provider=providers[0]
        if controller.http_server!=provider.endpoint:raise ValueError('unregistered controller')
        ledger=provider.current/'gui_dispatch.sqlite'
        key=str(ledger)
        if key not in bridges:bridges[key]=TerminalBridge(provider.endpoint,provider.endpoint,ledger)
        if getattr(provider,'quarantined',False):raise ExecutionUncertain('VM quarantined; no replay')
        try:
            action_id=str(uuid.uuid4())
            result=bridges[key].execute(['python','-c',controller.pkgs_prefix.format(command=command)],execution_id=action_id)
            if getattr(provider,'gui_idle',None):provider.gui_idle.wait(action_id)
            return result
        except ExecutionUncertain:
            provider.quarantined=True
            if on_uncertain:on_uncertain()
            provider.stop_emulator()
            raise
    def post(url,*args,**kwargs):
        if providers:return guarded_post(original_post,url,providers[0],*args,on_uncertain=on_uncertain,**kwargs)
        return original_post(url,*args,**kwargs)
    requests.post=post
    env_module.create_vm_manager_and_provider=factory
    env_module.MAX_RETRIES=1
    PythonController.execute_python_command=once
    # Replace get_screenshot to bypass the hanging Xcursor path on the
    # controller's /screenshot endpoint.  pyautogui.screenshot() works
    # when called through /execute; the route handler's own Xcursor()
    # call is what blocks.  This fallback captures a screenshot via
    # /execute, reads it back through /file, and returns the PNG bytes.
    original_get_screenshot = getattr(PythonController, 'get_screenshot', None)
    if original_get_screenshot:
        def _get_screenshot_via_execute(controller):
            import base64 as _b64
            from .terminal_bridge import TerminalBridge, ExecutionUncertain
            if not providers or providers[0].current is None:
                return None
            provider = providers[0]
            br = TerminalBridge(provider.endpoint, provider.endpoint,
                                provider.current / 'screenshot_dispatch.sqlite')
            source = (
                'import os,base64,tempfile,pyautogui;'
                'os.environ.update(DISPLAY=":0",XAUTHORITY="/run/user/1000/gdm/Xauthority");'
                'img=pyautogui.screenshot();'
                'buf=tempfile.NamedTemporaryFile(suffix=".png",delete=False);'
                'img.save(buf.name);'
                'print(base64.b64encode(buf.name.encode()).decode())'
            )
            try:
                result = br.execute(['python3', '-c', source],
                                    execution_id='screenshot-' + str(uuid.uuid4()),
                                    timeout=30)
            except ExecutionUncertain:
                return None
            finally:
                br.close()
            if result.get('returncode') != 0:
                return None
            file_in_vm = _b64.b64decode(result['output'].strip()).decode()
            try:
                response = requests.post(
                    provider.endpoint + '/file',
                    data={'file_path': file_in_vm},
                    timeout=(3, 10))
            except Exception:
                return None
            if response.status_code != 200:
                return None
            return response.content
        PythonController.get_screenshot = _get_screenshot_via_execute
    def cleanup():
        for bridge in bridges.values():
            try:bridge.close()
            except Exception:pass
        bridges.clear()
        requests.post=original_post
        for provider in providers:provider.stop_emulator()
        env_module.create_vm_manager_and_provider=original_factory
        env_module.MAX_RETRIES=original_retries
        PythonController.execute_python_command=original_execute
    if original_get_screenshot:
        PythonController.get_screenshot = original_get_screenshot
    return cleanup
