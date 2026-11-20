"""Candidate local collector. Disabled unless explicitly enabled by its operator.

One SDK worker, bounded admission/queue, metadata-only input, no model/member data.
"""
from collections import deque
import json
import logging
import os
from pathlib import Path
import queue
import signal
import socket
import stat
import struct
import threading
import time
from urllib.parse import urlsplit

from . import observation_contract as contract

ROOT=Path(__file__).resolve().parents[2]
SOCKET_PATH=ROOT/'.runtime/assistant-observe/collector.sock'
MAX_QUEUE=32
MAX_PER_MINUTE=30


class SDKSender:
    def __init__(self,host):
        url=urlsplit(host)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.username or url.password or url.query or url.fragment:raise ValueError('invalid_configuration')
        self.host=host;self.client=None

    def __call__(self,metadata):
        if self.client is None:
            # Never inherit cloud defaults or install automatic input/output integrations.
            os.environ['OPIK_ANALYTICS_ENABLE']='false'
            logger=logging.getLogger('opik');logger.disabled=True
            from opik import Opik
            self.client=Opik(host=self.host,project_name='moduyuga-public-requests',workspace='default',batching=False)
        trace=self.client.trace(name='assistant.public_request',input=None,output=None,
            metadata={**metadata,'capture_input':False,'capture_output':False,'record_kind':'public_runtime'})
        trace.end()
        if self.client.flush(timeout=2) is False:raise RuntimeError('delivery_failed')


class Collector:
    def __init__(self,sender,clock=time.monotonic):
        self.sender=sender;self.clock=clock;self.queue=queue.Queue(maxsize=MAX_QUEUE)
        self.lock=threading.RLock();self.rate=deque();self.failed=False
        self.counts={name:0 for name in contract.COUNTERS if name!='pending'}

    def count(self,name):
        self.counts[name]=min(2**63-1,self.counts[name]+1)

    def snapshot(self):
        with self.lock:return {**self.counts,'pending':self.queue.unfinished_tasks,'persistence_verified':False,'scope':'process_lifetime'}

    def ack(self,accepted,reason):
        return {'accepted':accepted,'reason':reason,'delivery':self.snapshot()}

    def admit(self,body):
        with self.lock:
            self.count('received')
            try:contract.validate(body)
            except contract.ObservationError:
                self.count('rejected');return self.ack(False,'invalid_request')
            if self.failed:
                self.count('dropped');return self.ack(False,'unavailable')
            stamp=self.clock()
            while self.rate and self.rate[0]<=stamp-60:self.rate.popleft()
            if len(self.rate)>=MAX_PER_MINUTE:
                self.count('dropped');return self.ack(False,'busy')
            # Copy the validated bounded event; later mutation cannot change queued data.
            try:self.queue.put_nowait(json.loads(json.dumps(body)))
            except queue.Full:
                self.count('dropped');return self.ack(False,'busy')
            self.rate.append(stamp);self.count('queued');return self.ack(True,'queued')

    def deliver_one(self,body):
        with self.lock:
            if self.failed:self.count('dropped');return
        try:self.sender(body)
        except Exception:
            with self.lock:self.failed=True;self.count('failed')
        else:
            with self.lock:self.count('sdk_flushed')

    def run(self):
        while True:
            body=self.queue.get()
            try:self.deliver_one(body)
            finally:self.queue.task_done()


def read_frame(channel,deadline):
    def receive(size):
        output=bytearray()
        while len(output)<size:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError()
            channel.settimeout(remaining)
            block=channel.recv(size-len(output))
            if not block:raise ValueError('invalid_request')
            output.extend(block)
        return bytes(output)
    size=struct.unpack('>I',receive(4))[0]
    if not 1<=size<=contract.MAX_BYTES:raise ValueError('invalid_request')
    raw=receive(size)
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('invalid_request')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _value:(_ for _ in ()).throw(ValueError('invalid_request')))


def exchange(body,deadline):
    contract.validate(body)
    if os.name!='posix':raise contract.ObservationError('unavailable')
    path=SOCKET_PATH;deadline=min(deadline,time.monotonic()+.5)
    try:
        metadata=path.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid!=os.getuid() or stat.S_IMODE(metadata.st_mode)!=0o600:raise ValueError()
        raw=json.dumps(body,separators=(',',':')).encode('ascii')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
            channel.settimeout(min(.5,max(.001,deadline-time.monotonic())));channel.connect(str(path))
            channel.sendall(struct.pack('>I',len(raw))+raw)
            ack=read_frame(channel,deadline)
        return contract.validate_ack(ack)
    except contract.ObservationError:raise
    except Exception:raise contract.ObservationError('unavailable') from None


def serve(collector):
    if os.name!='posix':raise ValueError('unavailable')
    path=SOCKET_PATH;directory=path.parent
    if directory.is_symlink():raise ValueError('invalid_configuration')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    if directory.stat().st_uid!=os.getuid():raise ValueError('invalid_configuration')
    directory.chmod(0o700)
    if path.exists() or path.is_symlink():
        metadata=path.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid!=os.getuid():raise ValueError('invalid_configuration')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as probe:
            probe.settimeout(.1)
            try:probe.connect(str(path))
            except (ConnectionRefusedError,FileNotFoundError):path.unlink()
            else:raise ValueError('busy')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        listener.bind(str(path));path.chmod(0o600);listener.listen(4)
        worker=threading.Thread(target=collector.run,name='public-observe-sdk',daemon=True);worker.start()
        try:
            while True:
                channel,_=listener.accept()
                with channel:
                    try:ack=collector.admit(read_frame(channel,time.monotonic()+.5))
                    except Exception:
                        with collector.lock:collector.count('rejected')
                        ack=collector.ack(False,'invalid_request')
                    try:
                        raw=json.dumps(ack,separators=(',',':')).encode('ascii');channel.settimeout(.2)
                        channel.sendall(struct.pack('>I',len(raw))+raw)
                    except OSError:pass
        finally:path.unlink(missing_ok=True)


def main():
    if os.getenv('ASSISTANT_OBSERVE_COLLECTOR_ENABLED','').lower()!='true':raise SystemExit('Observation collector is disabled.')
    try:
        contract.source_map()
        sender=SDKSender(os.getenv('ASSISTANT_OPIK_LOCAL_URL','http://127.0.0.1:15173/api'))
        serve(Collector(sender))
    except Exception:raise SystemExit('Observation collector stopped.') from None
