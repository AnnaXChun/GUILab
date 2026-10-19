import base64,json,os,pathlib,signal,subprocess
root=pathlib.Path('/home/user/.actc_gui_ready_vm_001')
if root.exists():raise RuntimeError('refuse GUI bootstrap replay')
root.mkdir()
macro=root/'bootstrap.FCMacro';macro.write_bytes(base64.b64decode('aW1wb3J0IGpzb24sb3MsdGltZSx0cmFjZWJhY2sKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCnJvb3Q9UGF0aCgnL2hvbWUvdXNlci8uYWN0Y19ndWlfcmVhZHlfdm1fMDAxJykKcmVzdWx0PXsnY2xhc3NpZmljYXRpb24nOid0cnVzdGVkX2d1aV9yZWFkaW5lc3MnLCdtb2RlbF9jYWxscyc6MCwnYWdlbnRfZ2VuZXJhdGVkJzpGYWxzZX0KKHJvb3QvJ2VudGVyZWQuanNvbicpLndyaXRlX3RleHQoanNvbi5kdW1wcyh7J2VudGVyZWQnOlRydWV9KSkKdHJ5OgogaW1wb3J0IEZyZWVDQUQgYXMgQXBwCiBpbXBvcnQgRnJlZUNBREd1aSBhcyBHdWkKIEd1aS5hY3RpdmF0ZVdvcmtiZW5jaCgnUGFydERlc2lnbldvcmtiZW5jaCcpCiBHdWkudXBkYXRlR3VpKCkKIGRvY3M9bGlzdChBcHAubGlzdERvY3VtZW50cygpKQogaWYgZG9jczpyYWlzZSBSdW50aW1lRXJyb3IoJ3JlYWRpbmVzcyByZXF1aXJlcyBhbiBlbXB0eSBkb2N1bWVudCBzZXQnKQogcmVzdWx0LnVwZGF0ZShzdGF0dXM9J1BBU1NfR1VJX1JFQURZJyxwaWQ9b3MuZ2V0cGlkKCksZnJlZWNhZF92ZXJzaW9uPWxpc3QoQXBwLlZlcnNpb24oKSksZG9jdW1lbnRzPWRvY3Msd29ya2JlbmNoPUd1aS5hY3RpdmVXb3JrYmVuY2goKS5uYW1lKCksd2luZG93X3Zpc2libGU9R3VpLmdldE1haW5XaW5kb3coKS5pc1Zpc2libGUoKSkKZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiByZXN1bHQudXBkYXRlKHN0YXR1cz0nRkFJTCcsZXJyb3I9dHlwZShleGMpLl9fbmFtZV9fLG1lc3NhZ2U9c3RyKGV4YyksdHJhY2ViYWNrPXRyYWNlYmFjay5mb3JtYXRfZXhjKCkpCihyb290LydndWlfcmVhZHkuanNvbicpLndyaXRlX3RleHQoanNvbi5kdW1wcyhyZXN1bHQpKQo='))
env=dict(os.environ)
env['DISPLAY']=':0';env['XAUTHORITY']='/run/user/1000/gdm/Xauthority';env['QT_QPA_PLATFORM']='xcb'
for k in ('WAYLAND_DISPLAY','QT_PLUGIN_PATH','QML2_IMPORT_PATH'):env.pop(k,None)
snap=pathlib.Path('/snap/freecad/current').resolve();kf=pathlib.Path('/snap/kf6-core24/current').resolve()
env['PATH']=str(snap/'usr/bin')+':'+env.get('PATH','')
env['PYTHONPATH']=str(snap/'usr/lib')+':'+str(snap/'usr/Mod')
env['LD_LIBRARY_PATH']=':'.join([str(snap/'usr/lib'),str(snap/'usr/lib/x86_64-linux-gnu'),str(kf/'usr/lib/x86_64-linux-gnu')])
terminated=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if (p/'comm').read_text().strip()=='FreeCAD' and '/snap/freecad/' in (p/'cmdline').read_bytes().decode(errors='replace'):
   os.kill(int(p.name),signal.SIGTERM);terminated.append(p.name)
 except (PermissionError,FileNotFoundError,ProcessLookupError):pass
with (root/'stdout.txt').open('w') as log:
 p=subprocess.Popen([str(snap/'usr/bin/FreeCAD'),str(macro)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'pid':p.pid,'executable':str(snap/'usr/bin/FreeCAD'),'terminated_startup_freecad_pids':terminated,'home_overridden':False}))
