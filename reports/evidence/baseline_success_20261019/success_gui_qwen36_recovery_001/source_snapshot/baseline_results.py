"""Collect official episode evidence without treating runner errors as score zero."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from .trace import write_json


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()] if Path(path).exists() else []


def collect_episode(directory, usage_path, *, kind, task_id):
    directory=Path(directory)
    usage=read_jsonl(usage_path)
    trajectory=read_jsonl(directory/('trajectory.jsonl' if kind=='cli' else 'traj.jsonl'))
    upstream_result=json.loads((directory/'result.json').read_text()) if (directory/'result.json').exists() else {}
    diagnostics=(directory/'evaluation.json').exists()
    raw_score=upstream_result.get('score')
    if (directory/'result.txt').exists():raw_score=float((directory/'result.txt').read_text().strip())
    errors=[row for row in usage if row.get('event')=='model_error']
    errors += [row for row in trajectory if row.get('error_type')]
    reason=None
    if (Path(usage_path).parent/'external_stop.json').exists():
        reason='externally_stopped_diagnostic_run'
    elif (directory/'error.json').exists() or errors or upstream_result.get('error'):
        reason='runner_or_model_error'
    elif any(row.get('event')=='budget_rejected' or (row.get('event')=='budget_summary' and row.get('circuit_open')) for row in usage):
        reason='model_or_execution_circuit_open'
    elif raw_score is None:reason='official_score_missing'
    artifacts=[]
    for path in sorted(directory.glob('*.FCStd')):
        native_zip=False
        try:
            with zipfile.ZipFile(path) as z:native_zip='Document.xml' in z.namelist() and z.testzip() is None
        except zipfile.BadZipFile:pass
        artifacts.append({'name':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'native_zip_document_present':native_zip,'freecad_reopen_verified':None,'parametric_history_verified':None})
    measured=[row for row in usage if row.get('event')=='model_usage']
    calls=sum(row.get('event')=='model_dispatch' for row in usage)
    complete_usage=len(measured)==calls and all(row.get('usage_available') for row in measured)
    known_output=sum((row.get('output_tokens') or 0)+(row.get('thinking_tokens') or 0) for row in measured)
    return {'task_id':task_id,'kind':kind,'protocol':'exploratory_tcg',
        'status':'RUN_ERROR' if reason else ('EVALUATED' if diagnostics else 'EVALUATED_DIAGNOSTICS_MISSING'),
        'strict':None if reason else raw_score,'strict_unavailable_reason':reason,'upstream_raw_score':raw_score,
        'diagnostics_present':diagnostics,'trajectory_rows':len(trajectory),'termination':upstream_result.get('termination'),
        'model_calls':calls,'output_tokens':known_output if complete_usage else None,'known_output_tokens':known_output,
        'input_tokens':sum(row.get('input_tokens') or 0 for row in measured) if complete_usage else None,
        'atomic_gui_actions':None,'atomic_gui_actions_reason':'not instrumented; action code may contain multiple calls',
        'artifacts':artifacts,'artifact_count':len(artifacts),
        'note':'ZIP integrity is not evidence of FreeCAD reopen, geometry validity, or editable feature history.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--episode-dir',type=Path,required=True);p.add_argument('--usage',type=Path,required=True)
    p.add_argument('--kind',choices=['gui','cli'],required=True);p.add_argument('--task-id',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    record=collect_episode(a.episode_dir,a.usage,kind=a.kind,task_id=a.task_id)
    write_json(a.output,record);print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
