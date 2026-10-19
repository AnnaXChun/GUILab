import base64,json,os,pathlib,signal,subprocess,hashlib
root=pathlib.Path('/home/user/.actc_gui_ready_vm_001')
if root.exists():raise RuntimeError('refuse GUI bootstrap replay')
root.mkdir()
autostart=pathlib.Path('/home/user/.config/autostart/freecad.desktop')
autostart_before=hashlib.sha256(autostart.read_bytes()).hexdigest() if autostart.exists() else None
autostart.parent.mkdir(parents=True,exist_ok=True)
autostart.write_text('[Desktop Entry]\nType=Application\nName=FreeCAD\nHidden=true\nX-GNOME-Autostart-enabled=false\n')
macro=root/'bootstrap.FCMacro';macro.write_bytes(base64.b64decode('aW1wb3J0IGpzb24sb3MsdGltZSx0cmFjZWJhY2sKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCnJvb3Q9UGF0aCgnL2hvbWUvdXNlci8uYWN0Y19ndWlfcmVhZHlfdm1fMDAxJykKcmVzdWx0PXsnY2xhc3NpZmljYXRpb24nOid0cnVzdGVkX2d1aV9yZWFkaW5lc3MnLCdtb2RlbF9jYWxscyc6MCwnYWdlbnRfZ2VuZXJhdGVkJzpGYWxzZX0Kc3RhcnRlZD10aW1lLm1vbm90b25pYygpCmRlZiBwaGFzZShuYW1lKToKIHdpdGggKHJvb3QvJ2d1aV9waGFzZXMuanNvbmwnKS5vcGVuKCdhJykgYXMgZjpmLndyaXRlKGpzb24uZHVtcHMoeydzdGFnZSc6bmFtZSwnZWxhcHNlZF9zZWNvbmRzJzp0aW1lLm1vbm90b25pYygpLXN0YXJ0ZWR9KSsnXG4nKQoocm9vdC8nZW50ZXJlZC5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKHsnZW50ZXJlZCc6VHJ1ZX0pKQp0cnk6CiBpbXBvcnQgRnJlZUNBRCBhcyBBcHAKIGltcG9ydCBGcmVlQ0FER3VpIGFzIEd1aQogR3VpLmFjdGl2YXRlV29ya2JlbmNoKCdQYXJ0RGVzaWduV29ya2JlbmNoJykKIEd1aS51cGRhdGVHdWkoKQogZG9jcz1saXN0KEFwcC5saXN0RG9jdW1lbnRzKCkpCiBpZiBkb2NzOnJhaXNlIFJ1bnRpbWVFcnJvcigncmVhZGluZXNzIHJlcXVpcmVzIGFuIGVtcHR5IGRvY3VtZW50IHNldCcpCiBpZiBGYWxzZToKICBwaGFzZSgnZW1wdHlfY2FudmFzX3N0YXJ0JykKICB3YXJtX2RvYz1BcHAubmV3RG9jdW1lbnQoJ0FDVENSZW5kZXJXYXJtdXAnKQogIEd1aS51cGRhdGVHdWkoKQogIGlmIHdhcm1fZG9jLk9iamVjdHM6cmFpc2UgUnVudGltZUVycm9yKCd3YXJtdXAgbXVzdCBub3QgY3JlYXRlIHRhc2sgZ2VvbWV0cnknKQogIEd1aS5hY3RpdmVEb2N1bWVudCgpLmFjdGl2ZVZpZXcoKS52aWV3VG9wKCkKICBHdWkuYWN0aXZlRG9jdW1lbnQoKS5hY3RpdmVWaWV3KCkuc2F2ZUltYWdlKHN0cihyb290LydlbXB0eV9jYW52YXMucG5nJyksNjQwLDQ4MCwnV2hpdGUnKQogIEd1aS51cGRhdGVHdWkoKTtwaGFzZSgnZW1wdHlfY2FudmFzX3JlbmRlcmVkJykKICBBcHAuY2xvc2VEb2N1bWVudCh3YXJtX2RvYy5OYW1lKTtHdWkudXBkYXRlR3VpKCkKICBkb2NzPWxpc3QoQXBwLmxpc3REb2N1bWVudHMoKSkKICBpZiBkb2NzOnJhaXNlIFJ1bnRpbWVFcnJvcignd2FybXVwIG11c3QgcmVzdG9yZSBlbXB0eSBkb2N1bWVudCBzZXQnKQogIHJlc3VsdC51cGRhdGUoY2FudmFzX3dhcm1lZD1UcnVlLHdhcm11cF9vYmplY3RfY291bnQ9MCkKICBwaGFzZSgnZW1wdHlfY2FudmFzX2Nsb3NlZCcpCiByZXN1bHQudXBkYXRlKHN0YXR1cz0nUEFTU19HVUlfUkVBRFknLHBpZD1vcy5nZXRwaWQoKSxmcmVlY2FkX3ZlcnNpb249bGlzdChBcHAuVmVyc2lvbigpKSxkb2N1bWVudHM9ZG9jcyx3b3JrYmVuY2g9R3VpLmFjdGl2ZVdvcmtiZW5jaCgpLm5hbWUoKSx3aW5kb3dfdmlzaWJsZT1HdWkuZ2V0TWFpbldpbmRvdygpLmlzVmlzaWJsZSgpKQpleGNlcHQgRXhjZXB0aW9uIGFzIGV4YzoKIHJlc3VsdC51cGRhdGUoc3RhdHVzPSdGQUlMJyxlcnJvcj10eXBlKGV4YykuX19uYW1lX18sbWVzc2FnZT1zdHIoZXhjKSx0cmFjZWJhY2s9dHJhY2ViYWNrLmZvcm1hdF9leGMoKSkKKHJvb3QvJ2d1aV9yZWFkeS5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKHJlc3VsdCkpCg=='))
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
print(json.dumps({'pid':p.pid,'executable':str(snap/'usr/bin/FreeCAD'),'terminated_startup_freecad_pids':terminated,'home_overridden':False,'autostart_disabled':True,'autostart_before_sha256':autostart_before}))
