import copy
import json
import pytest
from cad_cf.mock_backend import initial_state, SCREENSHOT, UI
from cad_cf.snapshot import SnapshotStore, prove_equivalence, InvalidPair

def test_restore_equivalence(checkpoint, tmp_path):
    store = SnapshotStore()
    for name in ('A','B'):
        p = store.clone(checkpoint, tmp_path/name)
        prove_equivalence(checkpoint, json.loads((p/'canonical.json').read_text()), SCREENSHOT, UI)

def test_clean_clone(checkpoint,tmp_path):
    store=SnapshotStore()
    a=store.clone(checkpoint,tmp_path/'A')
    b=store.clone(checkpoint,tmp_path/'B')
    (a/'artifact.mock.json').write_text('mutated')
    assert (b/'artifact.mock.json').read_bytes() == (checkpoint.path/'artifact.mock.json').read_bytes()

def test_reject_modified_source(checkpoint,tmp_path):
    (checkpoint.path/'canonical.json').write_text('{}')
    with pytest.raises(InvalidPair,match='mutated'):
        SnapshotStore().clone(checkpoint,tmp_path/'A')

def test_different_s0_rejected(checkpoint):
    state=initial_state()
    state['objects'][1]['properties']['Length']=9
    with pytest.raises(InvalidPair,match='different_S0'):
        prove_equivalence(checkpoint,state,SCREENSHOT,UI)
