import json
from pathlib import Path
from cad_cf.selection import build_manifests

def test_public_split_is_grouped_and_rebuildable():
    a=build_manifests(Path.cwd())
    path=Path('manifests/splits.json')
    first=path.read_bytes()
    b=build_manifests(Path.cwd())
    assert first==path.read_bytes()
    data=json.loads(first)
    ownership={}
    for split,tasks in data['splits'].items():
        for task in tasks:
            gid=data['groups'][task]
            assert ownership.setdefault(gid,split)==split
    records=json.loads(Path('manifests/public_tasks.json').read_text())
    assert all(r['requires_precondition'] and r['source_sha256'] for r in records if r['eligible_edit'])
    assert a['N_part_sketch']==b['N_part_sketch']==140
    assert all('evaluator' not in r and 'expected' not in r for r in records)
