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
            return bridges[key].execute(['python','-c',controller.pkgs_prefix.format(command=command)],execution_id=str(uuid.uuid4()))
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
    return cleanup
