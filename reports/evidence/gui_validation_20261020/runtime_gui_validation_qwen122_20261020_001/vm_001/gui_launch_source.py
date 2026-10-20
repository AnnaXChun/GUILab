import base64,json,os,pathlib,signal,subprocess,hashlib
root=pathlib.Path('/home/user/.actc_gui_ready_vm_001')
if root.exists():raise RuntimeError('refuse GUI bootstrap replay')
root.mkdir()
autostart=pathlib.Path('/home/user/.config/autostart/freecad.desktop')
autostart_before=hashlib.sha256(autostart.read_bytes()).hexdigest() if autostart.exists() else None
autostart.parent.mkdir(parents=True,exist_ok=True)
autostart.write_text('[Desktop Entry]\nType=Application\nName=FreeCAD\nHidden=true\nX-GNOME-Autostart-enabled=false\n')
macro=root/'bootstrap.FCMacro';macro.write_bytes(base64.b64decode('aW1wb3J0IGpzb24sb3MsdGltZSx0cmFjZWJhY2sKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCnJvb3Q9UGF0aCgnL2hvbWUvdXNlci8uYWN0Y19ndWlfcmVhZHlfdm1fMDAxJykKcmVzdWx0PXsnY2xhc3NpZmljYXRpb24nOid0cnVzdGVkX2d1aV9yZWFkaW5lc3MnLCdtb2RlbF9jYWxscyc6MCwnYWdlbnRfZ2VuZXJhdGVkJzpGYWxzZX0Kc3RhcnRlZD10aW1lLm1vbm90b25pYygpCmRlZiBwaGFzZShuYW1lKToKIHdpdGggKHJvb3QvJ2d1aV9waGFzZXMuanNvbmwnKS5vcGVuKCdhJykgYXMgZjpmLndyaXRlKGpzb24uZHVtcHMoeydzdGFnZSc6bmFtZSwnZWxhcHNlZF9zZWNvbmRzJzp0aW1lLm1vbm90b25pYygpLXN0YXJ0ZWR9KSsnXG4nKQoocm9vdC8nZW50ZXJlZC5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKHsnZW50ZXJlZCc6VHJ1ZX0pKQp0cnk6CiBpbXBvcnQgRnJlZUNBRCBhcyBBcHAKIGltcG9ydCBGcmVlQ0FER3VpIGFzIEd1aQogd2luZG93PUd1aS5nZXRNYWluV2luZG93KCkKIHdpbmRvdy5zaG93TWF4aW1pemVkKCkKIHdpbmRvdy5yYWlzZV8oKQogd2luZG93LmFjdGl2YXRlV2luZG93KCkKIEd1aS5hY3RpdmF0ZVdvcmtiZW5jaCgnUGFydERlc2lnbldvcmtiZW5jaCcpCiBHdWkudXBkYXRlR3VpKCkKIGRvY3M9bGlzdChBcHAubGlzdERvY3VtZW50cygpKQogaWYgZG9jczpyYWlzZSBSdW50aW1lRXJyb3IoJ3JlYWRpbmVzcyByZXF1aXJlcyBhbiBlbXB0eSBkb2N1bWVudCBzZXQnKQogaWYgRmFsc2U6CiAgcGhhc2UoJ2VtcHR5X2NhbnZhc19zdGFydCcpCiAgd2FybV9kb2M9QXBwLm5ld0RvY3VtZW50KCdBQ1RDUmVuZGVyV2FybXVwJykKICBHdWkudXBkYXRlR3VpKCkKICBpZiB3YXJtX2RvYy5PYmplY3RzOnJhaXNlIFJ1bnRpbWVFcnJvcignd2FybXVwIG11c3Qgbm90IGNyZWF0ZSB0YXNrIGdlb21ldHJ5JykKICBHdWkuYWN0aXZlRG9jdW1lbnQoKS5hY3RpdmVWaWV3KCkudmlld1RvcCgpCiAgR3VpLmFjdGl2ZURvY3VtZW50KCkuYWN0aXZlVmlldygpLnNhdmVJbWFnZShzdHIocm9vdC8nZW1wdHlfY2FudmFzLnBuZycpLDY0MCw0ODAsJ1doaXRlJykKICBHdWkudXBkYXRlR3VpKCk7cGhhc2UoJ2VtcHR5X2NhbnZhc19yZW5kZXJlZCcpCiAgQXBwLmNsb3NlRG9jdW1lbnQod2FybV9kb2MuTmFtZSk7R3VpLnVwZGF0ZUd1aSgpCiAgZG9jcz1saXN0KEFwcC5saXN0RG9jdW1lbnRzKCkpCiAgaWYgZG9jczpyYWlzZSBSdW50aW1lRXJyb3IoJ3dhcm11cCBtdXN0IHJlc3RvcmUgZW1wdHkgZG9jdW1lbnQgc2V0JykKICByZXN1bHQudXBkYXRlKGNhbnZhc193YXJtZWQ9VHJ1ZSx3YXJtdXBfb2JqZWN0X2NvdW50PTApCiAgcGhhc2UoJ2VtcHR5X2NhbnZhc19jbG9zZWQnKQogZnJhbWU9d2luZG93LmZyYW1lR2VvbWV0cnkoKQogcmVzdWx0LnVwZGF0ZShzdGF0dXM9J1BBU1NfR1VJX1JFQURZJyxwaWQ9b3MuZ2V0cGlkKCksZnJlZWNhZF92ZXJzaW9uPWxpc3QoQXBwLlZlcnNpb24oKSksZG9jdW1lbnRzPWRvY3Msd29ya2JlbmNoPUd1aS5hY3RpdmVXb3JrYmVuY2goKS5uYW1lKCksd2luZG93X3Zpc2libGU9d2luZG93LmlzVmlzaWJsZSgpLHdpbmRvd19tYXhpbWl6ZWQ9d2luZG93LmlzTWF4aW1pemVkKCksd2luZG93X2FjdGl2ZT13aW5kb3cuaXNBY3RpdmVXaW5kb3coKSx3aW5kb3dfZnJhbWU9eyd4JzpmcmFtZS54KCksJ3knOmZyYW1lLnkoKSwnd2lkdGgnOmZyYW1lLndpZHRoKCksJ2hlaWdodCc6ZnJhbWUuaGVpZ2h0KCl9KQpleGNlcHQgRXhjZXB0aW9uIGFzIGV4YzoKIHJlc3VsdC51cGRhdGUoc3RhdHVzPSdGQUlMJyxlcnJvcj10eXBlKGV4YykuX19uYW1lX18sbWVzc2FnZT1zdHIoZXhjKSx0cmFjZWJhY2s9dHJhY2ViYWNrLmZvcm1hdF9leGMoKSkKKHJvb3QvJ2d1aV9yZWFkeS5qc29uJykud3JpdGVfdGV4dChqc29uLmR1bXBzKHJlc3VsdCkpCg=='))
env=dict(os.environ)
env['DISPLAY']=':0';env['XAUTHORITY']='/run/user/1000/gdm/Xauthority';env['QT_QPA_PLATFORM']='xcb'
for k in ('WAYLAND_DISPLAY','QT_PLUGIN_PATH','QML2_IMPORT_PATH'):env.pop(k,None)
desktop_policy={'requested_alive_timeout_ms':600000,'changed':False}
if desktop_policy['requested_alive_timeout_ms'] is not None:
 settings_env=dict(env,DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
 def setting(operation,*args):
  response=subprocess.run(['/usr/bin/gsettings',operation,'org.gnome.mutter','check-alive-timeout',*args],env=settings_env,capture_output=True,text=True,timeout=15)
  if response.returncode:raise RuntimeError('GNOME alive policy '+operation+' failed: '+response.stderr)
  return response.stdout.strip()
 desktop_policy.update(schema='org.gnome.mutter',key='check-alive-timeout',supported_range=setting('range'),before=setting('get'))
 (root/'desktop_policy.json').write_text(json.dumps(desktop_policy))
 setting('set',str(600000))
 desktop_policy['after']=setting('get')
 if desktop_policy['after']!='uint32 600000':raise RuntimeError('GNOME alive policy readback mismatch')
 desktop_policy['changed']=desktop_policy['before']!=desktop_policy['after']
 (root/'desktop_policy.json').write_text(json.dumps(desktop_policy))
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
print(json.dumps({'pid':p.pid,'executable':str(snap/'usr/bin/FreeCAD'),'terminated_startup_freecad_pids':terminated,'home_overridden':False,'autostart_disabled':True,'autostart_before_sha256':autostart_before,'desktop_policy':desktop_policy}))
