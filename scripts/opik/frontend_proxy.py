"""Loopback-only static Opik frontend and /api reverse proxy for a native sandbox."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import mimetypes
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit, unquote

ROOT=Path(sys.argv[1]).resolve()
PORT=int(sys.argv[2]);BACKEND=int(sys.argv[3])

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def handle_request(self):
        if self.path.startswith('/api/'):
            length=int(self.headers.get('Content-Length','0'))
            if length>2_000_000:self.send_error(413);return
            connection=http.client.HTTPConnection('127.0.0.1',BACKEND,timeout=30)
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','connection','transfer-encoding')}
            try:
                connection.request(self.command,self.path[4:],body=self.rfile.read(length) if length else None,headers=headers)
                response=connection.getresponse();body=response.read(16_000_000)
                self.send_response(response.status)
                for key,value in response.getheaders():
                    if key.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(key,value)
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                if self.command!='HEAD':self.wfile.write(body)
            except (OSError,http.client.HTTPException):self.send_error(502,'Opik backend unavailable')
            finally:connection.close()
            return
        if self.path=='/health':body=b'healthy\n';content_type='text/plain'
        else:
            target=(ROOT/unquote(urlsplit(self.path).path).lstrip('/')).resolve()
            if ROOT not in target.parents and target!=ROOT:self.send_error(403);return
            if not target.is_file():target=ROOT/'index.html'
            try:body=target.read_bytes()
            except OSError:self.send_error(404);return
            content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        self.send_response(200);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
    do_GET=do_POST=do_PATCH=do_DELETE=do_PUT=do_OPTIONS=do_HEAD=handle_request

class BoundedServer(ThreadingHTTPServer):
    daemon_threads=True
    slots=threading.BoundedSemaphore(8)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            request.close();return
        try:super().process_request(request,address)
        except Exception:
            self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

BoundedServer(('127.0.0.1',PORT),Handler).serve_forever()
