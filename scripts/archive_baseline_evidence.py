#!/usr/bin/env python3
"""Export selected local evidence, with private service data and binary payloads excluded."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

TEXT_SUFFIXES={'.json','.jsonl','.log','.txt','.py','.FCMacro','.md','.sh'}
PRIVATE_FILES={'models.json','viewer_frame.png'}
INDEX_DIAGNOSTICS=('index_refresh','index_changes','full_index','main_index')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sanitize(data,private):
    content=data.decode('utf-8')
    content=re.sub(r'(advertised models:)[^\n]*',r'\1 [PRIVATE DIRECTORY EXCLUDED]',content)
    for value in sorted(set(private),key=len,reverse=True):
        if value:content=content.replace(value,'[REDACTED]')
    # ZIP magic in an encoded artifact must not bypass the binary exclusion.
    if re.search(r'UEsDB[A-Za-z0-9+/=]{100,}',content):
        raise ValueError('encoded ZIP artifact found; export only its digest')
    return content.encode('utf-8')


def ledger_summary(path):
    with sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True) as db:
        if not db.execute("SELECT count(*) FROM sqlite_master WHERE name='dispatch'").fetchone()[0]:return None
        rows=[{'execution_id':key,'state':state,'payload_sha256':digest(payload.encode()),'payload_excluded':True}
              for key,payload,state in db.execute('SELECT key,payload,state FROM dispatch ORDER BY rowid')]
    return {'classification':'at_most_once_dispatch_audit','payload_policy':'digest only; action text remains in original agent trajectory',
            'source_sha256':digest(path.read_bytes()),'rows':rows}


def export(root,sources,output,private=()):
    root=Path(root).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    index=[];omitted=[]
    for source in sources:
        source=(root/source).resolve()
        source.relative_to(root/'results')  # Explicit run paths only, never a home/repository scan.
        if not source.exists():raise FileNotFoundError(source)
        paths=sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in paths:
            if not path.is_file():continue
            rel=path.relative_to(root/'results');target=output/rel
            if path.name in PRIVATE_FILES or any(term in path.name for term in INDEX_DIAGNOSTICS):continue
            if path.suffix=='.sqlite':
                record=ledger_summary(path)
                if record is None:continue
                target=target.with_suffix('.dispatch.json');raw=json.dumps(record,indent=2).encode()+b'\n'
            elif path.suffix=='.png':
                match=re.match(r'step_(\d+)_',path.name)
                if match and int(match[1]) not in (1,2,10,20,24,25,50,100):
                    omitted.append({'path':str(rel),'sha256':digest(path.read_bytes()),'reason':'screenshot sample; full local image retained'})
                    continue
                if path.name not in ('initial_state.png','reset.png','ready.png','final.png','empty_canvas.png',
                                     'welcome_done.png','new_document.png','new_body.png','new_sketch.png',
                                     'select_xy.png','confirm_xy.png','leave_edit.png','save_dialog.png',
                                     'save.png','close.png','open_dialog.png','reopen.png','live_http_002.png') and not match:continue
                raw=path.read_bytes()
            elif path.suffix in TEXT_SUFFIXES:raw=path.read_bytes()
            else:continue
            data=raw if target.suffix=='.png' else sanitize(raw,private)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            index.append({'path':str(target.relative_to(output)),'source':str(path.relative_to(root)),
                          'source_sha256':digest(path.read_bytes()),'sha256':digest(data),'redacted':data!=raw,
                          'derived':path.suffix=='.sqlite'})
    record={'classification':'sanitized_baseline_success_and_failure_evidence',
            'excluded':['.env','API keys','private endpoint/hostname','full model directory','SQLite','qcow2','firmware','FCStd','encoded artifacts','MCP indexes/diagnostics'],
            'files':index,'omitted_screenshots':omitted,'complete_agent_jsonl':True}
    (output/'INDEX.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    from dotenv import dotenv_values
    values={**dotenv_values(root/'.env'),**os.environ}
    private=[values.get(name) or '' for name in ('CADWORLD_API_KEY','OPENAI_API_KEY','GEMINI_API_KEY')]
    endpoint=values.get('CADWORLD_API_BASE_URL') or ''
    private.extend((endpoint,urlsplit(endpoint).hostname or ''))
    record=export(root,args.source,args.output,private)
    print(json.dumps({'files':len(record['files']),'sampled_out_screenshots':len(record['omitted_screenshots']),'private_values_printed':False}))


if __name__=='__main__':main()
