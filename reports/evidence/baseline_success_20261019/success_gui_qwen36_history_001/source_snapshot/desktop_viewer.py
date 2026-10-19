"""Read-only loopback viewer for a disposable VM's QMP framebuffer."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from .qemu_runtime import qmp

PAGE='''<!doctype html><meta charset="utf-8"><title>CADWorld 虚拟机桌面</title>
<style>body{margin:0;background:#181818;color:#eee;font:15px system-ui}p{margin:10px}img{max-width:100%;display:block}</style>
<p>CADWorld Linux 虚拟机 · 实时只读画面</p><img id="screen" alt="正在读取虚拟机画面">
<script>const s=document.querySelector('#screen');function frame(){s.src='/screen.png?t='+Date.now()}s.onload=()=>setTimeout(frame,3000);s.onerror=()=>setTimeout(frame,5000);frame()</script>'''


def serve(monitor,directory,port):
    directory=Path(directory);lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path=='/':data=PAGE.encode();kind='text/html; charset=utf-8'
                elif self.path.startswith('/screen.png'):
                    with lock:
                        path=directory/'viewer_frame.png'
                        qmp(monitor,'screendump',{'filename':str(path.resolve()),'format':'png'})
                        data=path.read_bytes()
                    kind='image/png'
                else:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',kind)
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            except (OSError,EOFError,RuntimeError):self.send_error(503,'VM display unavailable')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',type=Path,required=True);p.add_argument('--port',type=int,default=15011)
    p.add_argument('--seconds',type=int,default=900);a=p.parse_args()
    if not 1<=a.seconds<=1800:p.error('bounded viewer lifetime required')
    argv=json.loads(a.launch.read_text())['argv']
    monitor=Path(argv[argv.index('-qmp')+1].split('unix:',1)[1].split(',',1)[0])
    server=serve(monitor,a.launch.parent,a.port)
    try:
        started=time.monotonic()
        while time.monotonic()-started<a.seconds and monitor.exists():time.sleep(1)
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
