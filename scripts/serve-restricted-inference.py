#!/usr/bin/env python3
"""Forced-command inference gateway. No shell/URL/file arguments from the peer.

Do not install or authorize a key without the user's separate explicit approval.
The only remote URLs are fixed loopback health/models/chat paths on 8091 or 8092.
"""
import argparse
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.remote_inference import (COMMAND,MODEL_ID,MAX_REQUEST_BYTES,MAX_RESPONSE_BYTES,
    MAX_HTTP_BYTES,TransportError,decode_envelope,decode_json)


def _http(port,path,body,deadline):
    if port not in (8091,8092) or path not in ('/health','/v1/models','/v1/chat/completions'):raise TransportError('invalid_configuration')
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TransportError('timeout')
    client=http.client.HTTPConnection('127.0.0.1',port,timeout=remaining);client.set_debuglevel(0)
    try:
        encoded=None if body is None else json.dumps(body,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        client.request('GET' if body is None else 'POST',path,body=encoded,headers={} if body is None else {'Content-Type':'application/json'})
        response=client.getresponse()
        if response.status!=200:raise TransportError('unavailable')
        raw=response.read(MAX_HTTP_BYTES+1)
        if len(raw)>MAX_HTTP_BYTES:raise TransportError('oversized_output')
        if time.monotonic()>=deadline:raise TransportError('timeout')
        try:return decode_json(raw,MAX_HTTP_BYTES)
        except TransportError:raise TransportError('invalid_output') from None
    except TransportError:raise
    except TimeoutError:raise TransportError('timeout') from None
    except Exception:raise TransportError('unavailable') from None
    finally:client.close()


@contextmanager
def _slot():
    if os.name!='posix':raise TransportError('unavailable')
    import fcntl
    lock=ROOT/'.runtime/restricted-inference.lock'
    try:
        fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a+b') as handle:
            try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise TransportError('busy') from None
            try:yield
            finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except TransportError:raise
    except OSError:raise TransportError('unavailable') from None


def handle(raw,port=8091,*,allow_observe=False):
    request=decode_envelope(raw)
    if port not in (8091,8092):raise TransportError('invalid_configuration')
    deadline=time.monotonic()+request['timeout_seconds']
    if request['operation']=='observe':
        if not allow_observe:raise TransportError('disabled')
        from app import observation_collector,observation_contract
        try:result=observation_collector.exchange(request['observation'],min(deadline,time.monotonic()+1))
        except observation_contract.ObservationError as error:raise TransportError(str(error)) from None
        return json.dumps({'version':1,'ok':True,'operation':'observe','result':result},separators=(',',':')).encode('ascii')
    with _slot():
        if request['operation']=='health':
            _http(port,'/health',None,deadline)
            models=_http(port,'/v1/models',None,deadline)
            if not isinstance(models,dict) or not any(isinstance(item,dict) and item.get('id')==MODEL_ID for item in models.get('data',[])):
                raise TransportError('unsupported_model')
            result={'available':True,'model':MODEL_ID}
        else:
            result=_http(port,'/v1/chat/completions',request['request'],deadline)
            if not isinstance(result,dict) or result.get('model')!=MODEL_ID or not isinstance(result.get('choices'),list):
                raise TransportError('unsupported_model')
    value={'version':1,'ok':True,'operation':request['operation'],'result':result}
    encoded=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(encoded)>MAX_RESPONSE_BYTES:raise TransportError('oversized_output')
    return encoded


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,choices=(8091,8092),default=8091)
    parser.add_argument('--enable-observe',action='store_true',help='Candidate permission expansion; separate approval required.')
    args=parser.parse_args()
    def timeout(*_):raise TransportError('timeout')
    output=None
    try:
        if os.name!='posix' or os.environ.get('SSH_ORIGINAL_COMMAND')!=COMMAND:raise TransportError('invalid_request')
        os.umask(0o077)
        signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,5)
        raw=sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
        request=decode_envelope(raw)
        signal.setitimer(signal.ITIMER_REAL,min(42,request['timeout_seconds']+1))
        output=handle(raw,args.port,allow_observe=args.enable_observe)
    except TransportError as error:
        output=json.dumps({'version':1,'ok':False,'error':error.code},separators=(',',':')).encode('utf-8')
    except Exception:
        output=b'{"version":1,"ok":false,"error":"unavailable"}'
    # Give even an expired-operation error a bounded output window.
    if os.name=='posix':signal.setitimer(signal.ITIMER_REAL,1)
    try:sys.stdout.buffer.write(output+b'\n');sys.stdout.buffer.flush()
    except (BrokenPipeError,OSError,TransportError):pass
    finally:
        if os.name=='posix':signal.setitimer(signal.ITIMER_REAL,0)
    return 0


if __name__=='__main__':raise SystemExit(main())
