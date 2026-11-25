"""Optional pinned-host SSH transport. No agent, shell, forwarding or key discovery.

Disabled by default. Only a dedicated, explicitly approved forced-command key may
be configured. Paramiko is imported lazily; no private payload is logged.
"""
import base64
from dataclasses import dataclass
import hmac
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
import socket
import struct
import threading
import time

from . import observation_contract

COMMAND='moduyuga-inference-v1'
MODEL_ID='moduyuga-qwen3-1.7b'
MAX_REQUEST_BYTES=32768
MAX_RESPONSE_BYTES=65536
MAX_HTTP_BYTES=60000
MAX_TIMEOUT=40
ERRORS={'disabled','invalid_configuration','host_key_mismatch','unavailable','timeout','busy','invalid_request','invalid_output','oversized_output','unsupported_model'}
_GATE=threading.BoundedSemaphore(1)
_OBSERVE_GATE=threading.BoundedSemaphore(1)


class TransportError(Exception):
    def __init__(self,code):
        self.code=code if isinstance(code,str) and code in ERRORS else 'unavailable'
        super().__init__(self.code)


def decode_json(raw,limit):
    if not isinstance(raw,bytes) or not raw or len(raw)>limit:raise TransportError('invalid_request')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate')
            result[key]=value
        return result
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError,RecursionError):raise TransportError('invalid_request') from None


def validate_payload(body):
    required={'model','temperature','max_tokens','stream','chat_template_kwargs','response_format','messages'}
    if not isinstance(body,dict) or set(body)!=required:raise TransportError('invalid_request')
    if body['model']!=MODEL_ID:raise TransportError('unsupported_model')
    if type(body['temperature']) not in (int,float) or body['temperature']!=0:raise TransportError('invalid_request')
    if type(body['max_tokens']) is not int or not 1<=body['max_tokens']<=400 or body['stream'] is not False:raise TransportError('invalid_request')
    if not isinstance(body['chat_template_kwargs'],dict) or set(body['chat_template_kwargs'])!={'enable_thinking'} or body['chat_template_kwargs']['enable_thinking'] is not False or body['response_format']!={'type':'json_object'}:raise TransportError('invalid_request')
    messages=body['messages']
    if not isinstance(messages,list) or len(messages)!=2:raise TransportError('invalid_request')
    for item,role,bound in zip(messages,['system','user'],[6000,24000]):
        if not isinstance(item,dict) or set(item)!={'role','content'} or item['role']!=role or not isinstance(item['content'],str):raise TransportError('invalid_request')
        try:size=len(item['content'].encode('utf-8'))
        except UnicodeError:raise TransportError('invalid_request') from None
        if not 1<=size<=bound:raise TransportError('invalid_request')
    return body


def envelope(operation,payload,timeout):
    if operation not in ('health','infer','observe') or type(timeout) not in (int,float) or (type(timeout) is float and not math.isfinite(timeout)):raise TransportError('invalid_request')
    if operation=='infer':validate_payload(payload)
    elif operation=='observe':validate_observation(payload)
    elif payload is not None:raise TransportError('invalid_request')
    value={'version':1,'operation':operation,'timeout_seconds':min(MAX_TIMEOUT,max(1,timeout))}
    if operation=='infer':value['request']=payload
    elif operation=='observe':value['observation']=payload
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_REQUEST_BYTES:raise TransportError('invalid_request')
    return raw


def decode_envelope(raw):
    value=decode_json(raw,MAX_REQUEST_BYTES)
    if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1:raise TransportError('invalid_request')
    operation=value.get('operation');keys={'version','operation','timeout_seconds'}|({'request'} if operation=='infer' else {'observation'} if operation=='observe' else set())
    if set(value)!=keys:raise TransportError('invalid_request')
    timeout=value['timeout_seconds']
    if type(timeout) not in (float,int) or not 1<=timeout<=MAX_TIMEOUT:raise TransportError('invalid_request')
    if operation=='infer':validate_payload(value['request'])
    elif operation=='observe':validate_observation(value['observation'])
    elif operation!='health':raise TransportError('invalid_request')
    return value


def validate_observation(body):
    try:return observation_contract.validate(body)
    except observation_contract.ObservationError as error:raise TransportError(str(error)) from None


def host_pin(text):
    try:
        if not isinstance(text,str):raise ValueError()
        kind,encoded=text.split()
        raw=base64.b64decode(encoded,validate=True)
        if kind!='ssh-ed25519' or len(raw)!=51 or raw[:4]!=struct.pack('>I',11) or raw[4:15]!=b'ssh-ed25519' or raw[15:19]!=struct.pack('>I',32):raise ValueError()
        return raw
    except (ValueError,TypeError):raise TransportError('invalid_configuration') from None


@dataclass(frozen=True)
class Settings:
    host:str
    port:int
    username:str
    private_key:Path
    pinned_key:bytes


def settings():
    if os.getenv('ASSISTANT_SSH_ENABLED','').lower()!='true':raise TransportError('disabled')
    try:
        host=os.environ['ASSISTANT_SSH_HOST'];username=os.environ['ASSISTANT_SSH_USER'];port=int(os.getenv('ASSISTANT_SSH_PORT','22'))
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}',host) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',username) or not 1<=port<=65535:raise ValueError()
        key=Path(os.environ['ASSISTANT_SSH_PRIVATE_KEY_PATH'])
        if not key.is_absolute():raise ValueError()
        return Settings(host,port,username,key,host_pin(os.environ['ASSISTANT_SSH_HOST_KEY']))
    except (KeyError,ValueError,TypeError):raise TransportError('invalid_configuration') from None


def _paramiko():
    try:import paramiko;return paramiko
    except ImportError:raise TransportError('unavailable') from None


def _private_key(config,paramiko):
    try:
        metadata=config.private_key.stat()
        if metadata.st_size>16384 or (os.name=='posix' and metadata.st_mode&0o077):raise ValueError()
        return paramiko.Ed25519Key.from_private_key(StringIO(config.private_key.read_text(encoding='ascii')))
    except Exception:raise TransportError('invalid_configuration') from None


def _exchange(config,raw,timeout):
    paramiko=_paramiko();key=_private_key(config,paramiko)
    deadline=time.monotonic()+timeout;transport=sock=channel=timer=None
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:raise TransportError('timeout')
        return value
    try:
        sock=socket.create_connection((config.host,config.port),timeout=min(3,remaining()))
        transport=paramiko.Transport(sock);transport.set_hexdump(False)
        transport.get_security_options().key_types=('ssh-ed25519',)
        timer=threading.Timer(remaining(),transport.close);timer.daemon=True;timer.start()
        transport.start_client(timeout=min(5,remaining()))
        observed=transport.get_remote_server_key()
        if observed.get_name()!='ssh-ed25519' or not hmac.compare_digest(observed.asbytes(),config.pinned_key):raise TransportError('host_key_mismatch')
        transport.auth_timeout=remaining();transport.auth_publickey(config.username,key)
        if not transport.is_authenticated():raise TransportError('unavailable')
        channel=transport.open_session(timeout=remaining());channel.settimeout(remaining());channel.exec_command(COMMAND)
        channel.sendall(raw);channel.shutdown_write()
        output=bytearray();errors=0
        while True:
            remaining()
            if channel.recv_ready():
                block=channel.recv(4096)
                if not block:break
                output.extend(block)
                if len(output)>MAX_RESPONSE_BYTES:raise TransportError('oversized_output')
            elif channel.recv_stderr_ready():
                errors+=len(channel.recv_stderr(1024))
                if errors>2048:raise TransportError('invalid_output')
            elif channel.exit_status_ready():break
            else:time.sleep(min(.01,remaining()))
        if channel.recv_exit_status()!=0:raise TransportError('unavailable')
        try:value=decode_json(bytes(output),MAX_RESPONSE_BYTES)
        except TransportError:raise TransportError('invalid_output') from None
        if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1:raise TransportError('invalid_output')
        if value.get('ok') is False:
            if set(value)!={'version','ok','error'}:raise TransportError('invalid_output')
            raise TransportError(value.get('error'))
        if value.get('ok') is not True or set(value)!={'version','ok','operation','result'}:raise TransportError('invalid_output')
        return value
    except TransportError:raise
    except (socket.timeout,TimeoutError):raise TransportError('timeout') from None
    except Exception:
        raise TransportError('timeout' if time.monotonic()>=deadline else 'unavailable') from None
    finally:
        if timer:timer.cancel()
        if channel:channel.close()
        if transport:transport.close()
        if sock:sock.close()


def _call(operation,payload,timeout):
    if type(timeout) not in (int,float) or not 1<=timeout<=45:raise TransportError('invalid_configuration')
    if operation=='observe' and os.getenv('ASSISTANT_SSH_OBSERVE_ENABLED','').lower()!='true':raise TransportError('disabled')
    config=settings();raw=envelope(operation,payload,min(MAX_TIMEOUT,max(1,timeout-2)))
    gate=_OBSERVE_GATE if operation=='observe' else _GATE
    if not gate.acquire(blocking=False):raise TransportError('busy')
    try:
        result=_exchange(config,raw,timeout)
        if result['operation']!=operation:raise TransportError('invalid_output')
        return result['result']
    finally:gate.release()


def infer(payload,timeout=25):
    result=_call('infer',payload,timeout)
    if not isinstance(result,dict) or result.get('model')!=MODEL_ID or not isinstance(result.get('choices'),list):raise TransportError('invalid_output')
    return json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def health(timeout=3):
    try:
        result=_call('health',None,timeout)
        return isinstance(result,dict) and set(result)=={'available','model'} and result['available'] is True and result['model']==MODEL_ID
    except TransportError:return False


def observe(metadata,timeout=8):
    """Candidate-only channel. Requires its separate explicit activation flag."""
    result=_call('observe',metadata,timeout)
    try:return observation_contract.validate_ack(result)
    except observation_contract.ObservationError:raise TransportError('invalid_output') from None
