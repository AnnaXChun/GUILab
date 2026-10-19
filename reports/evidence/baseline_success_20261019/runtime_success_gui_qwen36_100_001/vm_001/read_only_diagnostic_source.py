import subprocess,json,pathlib,os
rows={}
for n,cmd in [('windows',['wmctrl','-lp']),('active',['xprop','-root','_NET_ACTIVE_WINDOW']),('processes',['ps','-eLo','pid,tid,stat,pcpu,wchan:30,comm'])]:
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
  value=p.stdout
  if n=='processes':value='\n'.join(l for l in value.splitlines() if any(t in l for t in ['FreeCAD','llvmpipe','WebEngine','QXcb','PID']))
  rows[n]={'returncode':p.returncode,'stdout':value,'stderr':p.stderr}
 except Exception as e:rows[n]={'error':str(e)}
print(json.dumps(rows))
