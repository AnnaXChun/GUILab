"""Offline CLI trajectory cleaning and public-goal rewards; no evaluator imports."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
from .instruction import normalize_instruction
from .cadworld_adapter import verify_pin,PIN


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_goal(instruction, audit):
    """Fail closed outside three explicitly supported public task grammars."""
    text=normalize_instruction(instruction)
    objects=audit.get('reopened_objects',[])
    if not audit:return {'value':None,'reason':'native_audit_missing','source':'public_instruction_only'}
    suffix=r' Save the completed model to /home/user/Unnamed\.FCStd\.'
    line=re.fullmatch(r'Sketch one (horizontal|vertical) (normal-geometry|construction) line segment ([0-9.]+) mm long in the XY plane\.'+suffix,text)
    circle=re.fullmatch(r'Sketch one normal-geometry circle with radius ([0-9.]+) mm in the XY plane\.'+suffix,text)
    torus=re.fullmatch(r'Create a torus with major radius ([0-9.]+) mm and minor radius ([0-9.]+) mm in FreeCAD, measure its surface area, include that measurement in the finished FreeCAD file, and save the completed document to /home/user/Unnamed\.FCStd\.',text)
    if not (line or circle or torus):return {'value':None,'reason':'unsupported_public_goal','source':'public_instruction_only'}
    sketches=[o for o in objects if o.get('type_id')=='Sketcher::SketchObject']
    if line or circle:
        geometries=[(o,g) for o in sketches for g in o.get('geometries',[])]
        passed=len(geometries)==1
        if passed:
            obj,g=geometries[0]
            normal=obj.get('plane_normal')
            if normal is None:return {'value':None,'reason':'world_plane_evidence_missing','source':'public_instruction_only'}
            passed=math.isclose(abs(normal[2]),1,abs_tol=1e-7)
            if line:
                a,b=g.get('world_start'),g.get('world_end')
                if a is None or b is None:return {'value':None,'reason':'world_geometry_evidence_missing','source':'public_instruction_only'}
                direction,kind,length=line.groups()
                passed=passed and g.get('type')=='LineSegment' and g.get('construction') is (kind=='construction')
                passed=passed and math.isclose(g.get('length',-1),float(length),abs_tol=1e-6)
                axis=0 if direction=='horizontal' else 1
                passed=passed and math.isclose(a[1-axis],b[1-axis],abs_tol=1e-6) and all(abs(p[2])<1e-6 for p in (a,b))
            else:
                center=g.get('world_center')
                if center is None:return {'value':None,'reason':'world_geometry_evidence_missing','source':'public_instruction_only'}
                passed=passed and g.get('type')=='Circle' and g.get('construction') is False
                passed=passed and math.isclose(g.get('radius',-1),float(circle[1]),abs_tol=1e-6) and abs(center[2])<1e-6
    else:
        candidates=[o for o in objects if o.get('type_id')=='Part::Torus']
        if not candidates:return {'value':None,'reason':'torus_representation_not_supported','source':'public_instruction_only'}
        passed=len(candidates)==1
        if passed:
            o=candidates[0];major,minor=map(float,torus.groups());params=o.get('parameters',{})
            area=4*math.pi**2*major*minor
            passed=o.get('shape_valid') is True and o.get('solids')==1
            passed=passed and math.isclose(params.get('Radius1',-1),major,abs_tol=1e-6) and math.isclose(params.get('Radius2',-1),minor,abs_tol=1e-6)
            passed=passed and math.isclose(o.get('surface_area',-1),area,rel_tol=1e-6)
            measurements=[v for item in objects for v in item.get('area_properties',{}).values()]
            if not measurements:return {'value':None,'reason':'typed_area_measurement_not_observed','source':'public_instruction_only'}
            passed=passed and any(math.isclose(v,area,rel_tol=1e-6) for v in measurements)
    return {'value':int(passed),'reason':'supported_public_goal_checked','source':'public_instruction_only'}


def validate_trace(events, tool_mode='native'):
    """Check linkage, ordering and accounting before using any conversation."""
    reasons=[];pending={};seen=set();turn=0;elapsed=-1.;tokens=0;models=0;errors=0
    for row in events:
        current=row.get('turn',0);seconds=row.get('elapsed_seconds',0)
        if not isinstance(current,int) or current<turn:reasons.append('nonmonotonic_turn')
        if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<elapsed:reasons.append('nonmonotonic_time')
        turn=current;elapsed=seconds
        if row.get('type')=='model':
            if pending:reasons.append('missing_tool_result')
            models+=1;usage=row.get('usage') or {}
            output=usage.get('completion_tokens');input_tokens=usage.get('prompt_tokens')
            if type(output) is not int or type(input_tokens) is not int or min(output,input_tokens)<0:
                reasons.append('usage_missing');output=0
            tokens+=output
            if row.get('cumulative_output_tokens')!=tokens:reasons.append('token_accounting_mismatch')
            for call in row.get('tool_calls') or []:
                ident=call.get('id');name=call.get('function',{}).get('name')
                if not ident or ident in seen:reasons.append('duplicate_or_missing_tool_id')
                seen.add(ident);pending[ident]=name
                try:args=json.loads(call['function']['arguments'])
                except (ValueError,KeyError,TypeError):reasons.append('invalid_tool_arguments');continue
                if name not in ('terminal','finish'):reasons.append('unknown_tool')
                if name=='terminal' and (not isinstance(args,dict) or not isinstance(args.get('script'),str)):
                    reasons.append('invalid_terminal_script')
        elif row.get('type')=='tool':
            name=row.get('tool_name');result=row.get('result',{})
            if tool_mode=='native' and pending.pop(row.get('tool_call_id'),None)!=name:reasons.append('orphan_tool_result')
            if result.get('status') in ('error','unknown'):reasons.append('execution_outcome_uncertain')
            if result.get('status')=='policy_error':reasons.append('terminal_policy_violation')
            if name=='terminal' and result.get('returncode') not in (0,None):errors+=1
        elif row.get('type') not in ('history_window',):reasons.append('unknown_trace_event')
    if pending:reasons.append('missing_tool_result')
    if not models:reasons.append('empty_trajectory')
    return {'reasons':sorted(set(reasons)),'model_calls':models,'output_tokens':tokens,'terminal_nonzero_exits':errors}


def training_reason(record):
    if record['quarantine_reasons']:return 'quarantined'
    if record['split']!='train':return 'not_train'
    if record['termination']!='finish':return 'incomplete_episode'
    if record['tool_mode']!='native':return 'unsupported_training_protocol'
    if record['instruction_image_count']:return 'image_transport_not_reconstructed'
    if record['history_windowed']:return 'request_context_windowed'
    if record['artifact_count']!=1:return 'missing_or_ambiguous_artifact'
    if record['native_status']!='PASS_NATIVE_ARTIFACT_AUDIT':return 'native_quality_unverified_or_failed'
    if record['parameter_editability']!='PASS':return 'editability_unverified_or_failed'
    if record['public_goal']['value']!=1:return 'public_goal_unverified_or_failed'
    return None


def reconstruct_messages(events, instruction, prompts):
    messages=[{'role':'system','content':prompts.SYSTEM_PROMPT},{'role':'user','content':prompts.task_prompt(instruction)}]
    for event in events:
        if event.get('type')=='model':
            calls=event.get('tool_calls') or []
            msg={'role':'assistant','content':event.get('content')}
            if calls:msg['tool_calls']=[{k:c[k] for k in ('id','type','function') if k in c} for c in calls]
            messages.append(msg)
            if not calls:messages.append({'role':'user','content':'Continue the task by calling terminal, or call finish if the artifact has already been saved and verified. Do not answer only with prose.'})
        elif event.get('type')=='tool':
            messages.append({'role':'tool','tool_call_id':event['tool_call_id'],'content':json.dumps(event['result'],ensure_ascii=False)})
    return messages


def build_dataset(root, manifest, output, *, verify_upstream=True):
    root=Path(root).resolve();output=Path(output);spec=json.loads(Path(manifest).read_text())
    if verify_upstream:verify_pin(root/'vendor/CADWORLD')
    if spec.get('schema_version')!=1:raise ValueError('unsupported CLI dataset manifest')
    output.mkdir(parents=True,exist_ok=False)
    audits={}
    for path in spec.get('native_audits',[]):
        path=root/path
        if not path.exists():continue
        audit=json.loads(path.read_text());digest=audit.get('artifact_sha256')
        if digest:audits[digest]=audit
    prompt_spec=importlib.util.spec_from_file_location('cadworld_cli_prompts',root/'vendor/CADWORLD/CLI/prompts.py')
    prompts=importlib.util.module_from_spec(prompt_spec);prompt_spec.loader.exec_module(prompts)
    rows=[];sft=[];rejected=[];seen=set();family_splits={}
    for run_path in spec['runs']:
        run=root/run_path
        if not run.exists():continue
        args=json.loads((run/'args.json').read_text())
        usage_path=root/spec.get('live_usage',{}).get(run.name,'missing_live_usage.jsonl')
        usage=[]
        if usage_path.exists():usage=[json.loads(l) for l in usage_path.read_text().splitlines() if l.strip()]
        live_verified=spec.get('origin')=='live' and any(e.get('event')=='model_dispatch' for e in usage)
        dispatched=sum(e.get('event')=='model_dispatch' for e in usage)
        measured=[e for e in usage if e.get('event')=='model_usage']
        usage_complete=dispatched==len(measured) and all(e.get('usage_available') is True for e in measured)
        for result_path in sorted(run.glob('*/result.json')):
            directory=result_path.parent;task_id=directory.name
            result=json.loads(result_path.read_text());task=json.loads((directory/'public_task.json').read_text())
            trace=directory/'trajectory.jsonl';events=[];issues=[]
            try:events=[json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
            except (FileNotFoundError,ValueError):issues.append('malformed_or_missing_trajectory')
            validation=validate_trace(events,args.get('tool_mode','native'));issues+=validation['reasons']
            if not live_verified:issues.append('unverified_live_origin')
            if not usage_complete:issues.append('provider_usage_incomplete')
            if any(e.get('event')=='model_error' for e in usage):issues.append('provider_request_error')
            if args.get('interaction')!='terminal_only':issues.append('non_cli_origin')
            if result.get('error') or (directory/'error.json').exists():issues.append('pipeline_error')
            if result.get('output_tokens')!=validation['output_tokens']:issues.append('result_token_accounting_mismatch')
            if result.get('termination')=='finish' and not (events and events[-1].get('type')=='tool' and events[-1].get('tool_name')=='finish' and events[-1].get('result',{}).get('status')=='accepted'):
                issues.append('finish_event_missing')
            for event in events:
                # Scan actual agent/tool content, never benchmark instructions or the system prompt.
                content=json.dumps({k:event.get(k) for k in ('content','tool_calls','result')},ensure_ascii=False)
                if re.search(r'evaluation_examples|evaluators/|evaluation\.json|reference[_ /-]solution|pyautogui|xdotool|/screenshot',content,re.I):issues.append('boundary_content_detected')
                if re.search(r'\b(?:sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,})\b',content):issues.append('possible_secret')
            fingerprint=hashlib.sha256(json.dumps(events,sort_keys=True).encode()).hexdigest()
            if fingerprint in seen:issues.append('duplicate_trajectory')
            seen.add(fingerprint)
            split=spec.get('task_splits',{}).get(task_id,'unassigned')
            family=spec.get('task_families',{}).get(task_id,task_id)
            family_splits.setdefault(family,set()).add(split)
            artifacts=sorted(directory.glob('*.FCStd'));digests=[sha256(p) for p in artifacts]
            audit=audits.get(digests[0],{}) if len(digests)==1 else {}
            goal=public_goal(task['instruction'],audit)
            row={'schema_version':1,'episode_id':run.name+'/'+task_id,'task_id':task_id,'family':family,'split':split,
                 'model':args.get('model'),'protocol':'cadworld_cli_tcg','source':str(directory.relative_to(root)),
                 'budget':{k:args.get(k) for k in ('max_turns','max_terminal_calls','total_output_tokens','per_turn_tokens','max_wall_seconds')},
                 'trace_sha256':sha256(trace) if trace.exists() else None,'instruction':task['instruction'],
                 'instruction_image_count':task.get('instruction_image_count',0),'tool_mode':args.get('tool_mode'),
                 'termination':result.get('termination'),'model_calls':validation['model_calls'],'output_tokens':validation['output_tokens'],
                 'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) or 0 for e in events if e.get('type')=='model'),
                 'terminal_nonzero_exits':validation['terminal_nonzero_exits'],'quarantine_reasons':sorted(set(issues)),
                 'history_windowed':any(e.get('type')=='history_window' for e in events),
                 'artifact_count':len(artifacts),'artifact_sha256':digests[0] if len(digests)==1 else None,
                 'native_status':audit.get('status'),'parameter_editability':audit.get('parameter_editability'),
                 'public_goal':goal,'reward':goal['value'] if audit.get('status')=='PASS_NATIVE_ARTIFACT_AUDIT' else None,
                 'reward_source':'public_instruction_and_native_audit_only','live_origin_verified':live_verified,
                 'provider_usage_sha256':sha256(usage_path) if usage_path.exists() else None,
                 'offline_evaluation':{'official_score':result.get('score'),'failure_reason':result.get('failure_reason')}}
            row['training_rejection']=training_reason(row);rows.append(row)
            if row['training_rejection']:rejected.append({'episode_id':row['episode_id'],'reason':row['training_rejection']})
            else:
                sft.append({'schema_version':1,'episode_id':row['episode_id'],'task_id':task_id,'split':split,
                            'model':row['model'],'artifact_sha256':row['artifact_sha256'],
                            'reward':1,'reward_source':row['reward_source'],
                            'tool_schema_source':'vendor/CADWORLD/CLI/terminal_agent.py:TOOLS','cadworld_commit':PIN,
                            'messages':reconstruct_messages(events,task['instruction'],prompts)})
    if any(len(splits)>1 for splits in family_splits.values()):raise ValueError('task family crosses dataset splits')
    for name,data in [('episodes',rows),('quarantine',[r for r in rows if r['quarantine_reasons']]),('sft',sft),('rejected_training',rejected)]:
        (output/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
    summary={'schema_version':1,'episodes':len(rows),'unique_tasks':len({r['task_id'] for r in rows}),
             'sft_rows':len(sft),'quarantine_rows':sum(bool(r['quarantine_reasons']) for r in rows),
             'training_rejections':dict(Counter(r['reason'] for r in rejected)),
             'model_calls':sum(r['model_calls'] for r in rows),'output_tokens':sum(r['output_tokens'] for r in rows),
             'official_score_is_training_reward':False,'rl_training_started':False}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build_dataset(args.root,args.manifest,args.output),ensure_ascii=False))


if __name__=='__main__':main()
