import base64,json,os,pathlib,signal,subprocess,hashlib
root=pathlib.Path('/home/user/.actc_gui_ready_vm_001')
if root.exists():raise RuntimeError('refuse GUI bootstrap replay')
root.mkdir()
autostart=pathlib.Path('/home/user/.config/autostart/freecad.desktop')
autostart_before=hashlib.sha256(autostart.read_bytes()).hexdigest() if autostart.exists() else None
autostart.parent.mkdir(parents=True,exist_ok=True)
autostart.write_text('[Desktop Entry]\nType=Application\nName=FreeCAD\nHidden=true\nX-GNOME-Autostart-enabled=false\n')
macro=root/'bootstrap.FCMacro';macro.write_bytes(base64.b64decode('aW1wb3J0IGpzb24sb3MsdGltZSx0cmFjZWJhY2sKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCnJvb3Q9UGF0aCgnL2hvbWUvdXNlci8uYWN0Y19ndWlfcmVhZHlfdm1fMDAxJykKcmVzdWx0PXsnY2xhc3NpZmljYXRpb24nOid0cnVzdGVkX2d1aV9yZWFkaW5lc3MnLCdtb2RlbF9jYWxscyc6MCwnYWdlbnRfZ2VuZXJhdGVkJzpGYWxzZX0Kc3RhcnRlZD10aW1lLm1vbm90b25pYygpCmRlZiBwaGFzZShuYW1lKToKIHdpdGggKHJvb3QvJ2d1aV9waGFzZXMuanNvbmwnKS5vcGVuKCdhJykgYXMgZjpmLndyaXRlKGpzb24uZHVtcHMoeydzdGFnZSc6bmFtZSwnZWxhcHNlZF9zZWNvbmRzJzp0aW1lLm1vbm90b25pYygpLXN0YXJ0ZWR9KSsnXG4nKQoocm9vdC8nZW50ZXJlZC5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKHsnZW50ZXJlZCc6VHJ1ZX0pKQp0cnk6CiBpbXBvcnQgRnJlZUNBRCBhcyBBcHAKIGltcG9ydCBGcmVlQ0FER3VpIGFzIEd1aQogR3VpLmFjdGl2YXRlV29ya2JlbmNoKCdQYXJ0RGVzaWduV29ya2JlbmNoJykKIEd1aS51cGRhdGVHdWkoKQogZG9jcz1saXN0KEFwcC5saXN0RG9jdW1lbnRzKCkpCiBpZiBkb2NzOnJhaXNlIFJ1bnRpbWVFcnJvcigncmVhZGluZXNzIHJlcXVpcmVzIGFuIGVtcHR5IGRvY3VtZW50IHNldCcpCiBpZiBUcnVlOgogIHBoYXNlKCdlbXB0eV9jYW52YXNfc3RhcnQnKQogIHdhcm1fZG9jPUFwcC5uZXdEb2N1bWVudCgnQUNUQ1JlbmRlcldhcm11cCcpCiAgR3VpLnVwZGF0ZUd1aSgpCiAgaWYgd2FybV9kb2MuT2JqZWN0czpyYWlzZSBSdW50aW1lRXJyb3IoJ3dhcm11cCBtdXN0IG5vdCBjcmVhdGUgdGFzayBnZW9tZXRyeScpCiAgR3VpLmFjdGl2ZURvY3VtZW50KCkuYWN0aXZlVmlldygpLnZpZXdUb3AoKQogIEd1aS5hY3RpdmVEb2N1bWVudCgpLmFjdGl2ZVZpZXcoKS5zYXZlSW1hZ2Uoc3RyKHJvb3QvJ2VtcHR5X2NhbnZhcy5wbmcnKSw2NDAsNDgwLCdXaGl0ZScpCiAgR3VpLnVwZGF0ZUd1aSgpO3BoYXNlKCdlbXB0eV9jYW52YXNfcmVuZGVyZWQnKQogIEFwcC5jbG9zZURvY3VtZW50KHdhcm1fZG9jLk5hbWUpO0d1aS51cGRhdGVHdWkoKQogIGRvY3M9bGlzdChBcHAubGlzdERvY3VtZW50cygpKQogIGlmIGRvY3M6cmFpc2UgUnVudGltZUVycm9yKCd3YXJtdXAgbXVzdCByZXN0b3JlIGVtcHR5IGRvY3VtZW50IHNldCcpCiAgcmVzdWx0LnVwZGF0ZShjYW52YXNfd2FybWVkPVRydWUsd2FybXVwX29iamVjdF9jb3VudD0wKQogIHBoYXNlKCdlbXB0eV9jYW52YXNfY2xvc2VkJykKIHJlc3VsdC51cGRhdGUoc3RhdHVzPSdQQVNTX0dVSV9SRUFEWScscGlkPW9zLmdldHBpZCgpLGZyZWVjYWRfdmVyc2lvbj1saXN0KEFwcC5WZXJzaW9uKCkpLGRvY3VtZW50cz1kb2NzLHdvcmtiZW5jaD1HdWkuYWN0aXZlV29ya2JlbmNoKCkubmFtZSgpLHdpbmRvd192aXNpYmxlPUd1aS5nZXRNYWluV2luZG93KCkuaXNWaXNpYmxlKCkpCmV4Y2VwdCBFeGNlcHRpb24gYXMgZXhjOgogcmVzdWx0LnVwZGF0ZShzdGF0dXM9J0ZBSUwnLGVycm9yPXR5cGUoZXhjKS5fX25hbWVfXyxtZXNzYWdlPXN0cihleGMpLHRyYWNlYmFjaz10cmFjZWJhY2suZm9ybWF0X2V4YygpKQoocm9vdC8nZ3VpX3JlYWR5Lmpzb24nKS53cml0ZV90ZXh0KGpzb24uZHVtcHMocmVzdWx0KSkK'))
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
