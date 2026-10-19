import importlib
import sys
import pytest
from cad_cf.upstream_runtime import lazy_registry
from cad_cf.qemu_runtime import NativeQemuProvider


def test_lazy_registry_preserves_upstream_exports_without_eager_imports(tmp_path,monkeypatch):
    package=tmp_path/'registry';package.mkdir()
    (package/'__init__.py').write_text('from .cad import evaluate as check\nfrom .unused import expensive\n')
    (package/'cad.py').write_text('def evaluate(value): return value*2\n')
    (package/'unused.py').write_text("raise RuntimeError('unused import must not run')\n")
    module=lazy_registry('runtime_registry_test',package)
    monkeypatch.setitem(sys.modules,'runtime_registry_test',module)
    assert 'runtime_registry_test.cad' not in sys.modules
    assert module.check(3)==6
    assert module.check is importlib.import_module('runtime_registry_test.cad').evaluate
    with pytest.raises(AttributeError):module.unknown()
    assert 'runtime_registry_test.unused' not in sys.modules
    sys.modules.pop('runtime_registry_test.cad',None)


def test_native_runtime_bad_sha_never_launches_process(tmp_path,monkeypatch):
    base=tmp_path/'base';base.write_bytes(b'base')
    firmware=tmp_path/'firmware';firmware.write_bytes(b'firmware')
    def forbidden(*a,**kw):raise AssertionError('process launch forbidden')
    monkeypatch.setattr('cad_cf.qemu_runtime.subprocess.Popen',forbidden)
    monkeypatch.setattr('cad_cf.qemu_runtime.subprocess.run',forbidden)
    runtime=NativeQemuProvider(base,'bad',firmware,'bad',tmp_path/'new')
    with pytest.raises(ValueError,match='SHA'):runtime.start_emulator(str(base))
    assert not list((tmp_path/'new').rglob('*.qcow2'))
    runtime.stop_emulator()
