import pytest
from cad_cf.mock_backend import initial_state, SCREENSHOT, UI
from cad_cf.snapshot import SnapshotStore
from cad_cf.trace import write_json

@pytest.fixture
def checkpoint(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    write_json(source/'artifact.mock.json', initial_state())
    return SnapshotStore().capture(source, tmp_path/'cp', initial_state(), SCREENSHOT, UI, synthetic=True)

@pytest.fixture
def budgets():
    return dict(model_calls=12, tokens=12000, wall_s=600, gui_atomic_actions=100, typed_api_calls=40)
