"""Local-only transport adversarial tests; sockets, SSH and HTTP are mocked."""
import base64
from contextlib import nullcontext
import importlib.util
import io
import json
from pathlib import Path
import socket
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import remote_inference as remote

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('restricted_gateway',ROOT/'scripts/serve-restricted-inference.py')
gateway=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)
PIN=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+b'x'*32


def payload():
    return {'model':remote.MODEL_ID,'temperature':0,'max_tokens':400,'stream':False,
        'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object'},
        'messages':[{'role':'system','content':'fixed grounding instructions'},
                    {'role':'user','content':'local fixture question'}]}


def failure(code,fn,*args):
    with pytest.raises(remote.TransportError) as caught:fn(*args)
    assert caught.value.code==code
    assert str(caught.value)==code


@pytest.fixture
def configured(monkeypatch,tmp_path):
    key=tmp_path/'dedicated-test-key'
    key.write_text('SYNTHETIC TEST KEY ONLY',encoding='ascii')
    key.chmod(0o600)
    for name,value in {'ENABLED':'true','HOST':'example.invalid','USER':'inference',
        'PRIVATE_KEY_PATH':str(key),'HOST_KEY':'ssh-ed25519 '+base64.b64encode(PIN).decode()}.items():
        monkeypatch.setenv('ASSISTANT_SSH_'+name,value)
    monkeypatch.delenv('ASSISTANT_SSH_PORT',raising=False)
    return remote.settings()


def test_default_disabled_never_connects(monkeypatch):
    monkeypatch.delenv('ASSISTANT_SSH_ENABLED',raising=False)
    connect=Mock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(remote.socket,'create_connection',connect)
    failure('disabled',remote.infer,payload())
    assert remote.health() is False
    connect.assert_not_called()


@pytest.mark.parametrize('change',[
    {'model':'moduyuga-qwen3-4b'}, {'stream':True}, {'tools':[]}, {'url':'http://other'},
    {'temperature':True}, {'temperature':float('nan')}, {'max_tokens':True}, {'max_tokens':401},
    {'max_tokens':0}, {'chat_template_kwargs':{'enable_thinking':0}},
    {'chat_template_kwargs':{'enable_thinking':False,'other':False}},
    {'response_format':{'type':'text'}}, {'messages':[{'role':'user','content':'q'}]},
    {'messages':[{'role':'system','content':'x'*6001},{'role':'user','content':'q'}]},
    {'messages':[{'role':'system','content':'s'},{'role':'user','content':'가'*8001}]},
])
def test_rejects_caller_capability_expansion(change):
    value=payload();value.update(change)
    failure('unsupported_model' if 'model' in change else 'invalid_request',remote.validate_payload,value)


@pytest.mark.parametrize('raw',[
    b'{"version":1,"version":1}',b'{"x":NaN}',b'{"x":Infinity}',b'\xff',b'[]',
    b'{"version":true,"operation":"health","timeout_seconds":2}',
    b'{"version":1,"operation":"health","timeout_seconds":true}',
    b'{"version":1,"operation":"health","timeout_seconds":2,"port":8092}',
    b'{"version":1,"operation":"exec","timeout_seconds":2}', b'x'*32769,
])
def test_strict_envelope(raw):failure('invalid_request',remote.decode_envelope,raw)


def test_utf8_envelope_total_bound():
    value=payload();value['messages'][0]['content']='\x01'*6000
    value['messages'][1]['content']='\x01'*24000
    failure('invalid_request',remote.envelope,'infer',value,25)
    assert remote.decode_envelope(remote.envelope('infer',payload(),400))['timeout_seconds']==40


@pytest.mark.parametrize('pin',['rsa AAAA','ssh-ed25519 AAAA','ssh-ed25519 !!!!',
    'ssh-ed25519 '+base64.b64encode(PIN).decode()+' extra',None])
def test_invalid_pin(pin):failure('invalid_configuration',remote.host_pin,pin)


@pytest.mark.parametrize('name,value', [('HOST','host;command'),('USER','root:bad'),('PORT','0'),
    ('PRIVATE_KEY_PATH','relative-key'),('HOST_KEY','invalid')])
def test_invalid_settings(configured,monkeypatch,name,value):
    monkeypatch.setenv('ASSISTANT_SSH_'+name,value)
    failure('invalid_configuration',remote.settings)


def test_key_file_size_and_posix_permissions(configured,monkeypatch):
    paramiko=SimpleNamespace(Ed25519Key=SimpleNamespace(from_private_key=Mock(return_value='key')))
    configured.private_key.write_text('x'*16385)
    failure('invalid_configuration',remote._private_key,configured,paramiko)
    configured.private_key.write_text('synthetic')
    with monkeypatch.context() as context:
        context.setattr(remote,'os',SimpleNamespace(name='posix'))
        context.setattr(type(configured.private_key),'stat',lambda self:SimpleNamespace(st_size=9,st_mode=0o644))
        failure('invalid_configuration',remote._private_key,configured,paramiko)
    paramiko.Ed25519Key.from_private_key.assert_not_called()


class Channel:
    def __init__(self,output,stderr=b'',exit_code=0):
        self.output=bytearray(output);self.stderr=bytearray(stderr);self.exit_code=exit_code
        self.closed=False;self.command=None;self.sent=None;self.eof=False
    def settimeout(self,value):assert 0<value<=3
    def exec_command(self,value):self.command=value
    def sendall(self,value):self.sent=value
    def shutdown_write(self):self.eof=True
    def recv_ready(self):return bool(self.output)
    def recv(self,size):result=bytes(self.output[:size]);del self.output[:size];return result
    def recv_stderr_ready(self):return bool(self.stderr)
    def recv_stderr(self,size):result=bytes(self.stderr[:size]);del self.stderr[:size];return result
    def exit_status_ready(self):return True
    def recv_exit_status(self):return self.exit_code
    def close(self):self.closed=True


def fake_ssh(monkeypatch,output,pin=PIN,stderr=b'',exit_code=0):
    channel=Channel(output,stderr,exit_code)
    transport=Mock()
    transport.get_remote_server_key.return_value=SimpleNamespace(get_name=lambda:'ssh-ed25519',asbytes=lambda:pin)
    transport.is_authenticated.return_value=True
    transport.open_session.return_value=channel
    sock=Mock()
    connect=Mock(return_value=sock)
    factory=Mock(return_value=transport)
    paramiko=SimpleNamespace(Transport=factory)
    monkeypatch.setattr(remote,'_paramiko',lambda:paramiko)
    monkeypatch.setattr(remote,'_private_key',lambda *_:'synthetic-key')
    monkeypatch.setattr(remote.socket,'create_connection',connect)
    return transport,channel,sock,connect


def response(result=None,**changes):
    value={'version':1,'ok':True,'operation':'infer','result':result or {'model':remote.MODEL_ID,'choices':[]}}
    value.update(changes)
    return json.dumps(value).encode()


def test_host_pin_checked_before_auth(configured,monkeypatch):
    transport,channel,sock,_=fake_ssh(monkeypatch,response(),pin=PIN[:-1]+b'y')
    failure('host_key_mismatch',remote.infer,payload(),3)
    transport.auth_publickey.assert_not_called();transport.open_session.assert_not_called()
    transport.close.assert_called();sock.close.assert_called();assert not channel.closed


def test_static_command_and_deterministic_auth(configured,monkeypatch):
    transport,channel,sock,connect=fake_ssh(monkeypatch,response())
    assert json.loads(remote.infer(payload(),3))['model']==remote.MODEL_ID
    connect.assert_called_once_with(('example.invalid',22),timeout=pytest.approx(3,abs=.02))
    transport.auth_publickey.assert_called_once_with('inference','synthetic-key')
    assert transport.get_security_options().key_types==('ssh-ed25519',)
    assert channel.command=='moduyuga-inference-v1' and channel.eof
    assert remote.decode_envelope(channel.sent)['request']==payload()
    assert channel.closed;transport.close.assert_called();sock.close.assert_called()
    assert not any(name in {'open_channel','request_port_forward','open_sftp_client'} for name,_,_ in transport.method_calls)


@pytest.mark.parametrize('output,stderr,exit_code,code',[
    (b'x'*65537,b'',0,'oversized_output'),(response(),b'x'*2049,0,'invalid_output'),
    (response(),b'',1,'unavailable'),(response(version=True),b'',0,'invalid_output'),
    (response(operation='health'),b'',0,'invalid_output'),
    (response({'model':'moduyuga-qwen3-4b','choices':[]}),b'',0,'invalid_output'),
    (b'{"version":1,"ok":false,"error":"busy"}',b'',0,'busy'),
])
def test_remote_failures_cleanup(configured,monkeypatch,output,stderr,exit_code,code):
    transport,channel,sock,_=fake_ssh(monkeypatch,output,stderr=stderr,exit_code=exit_code)
    failure(code,remote.infer,payload(),3)
    assert channel.closed;transport.close.assert_called();sock.close.assert_called()


def test_timeout_cleanup(configured,monkeypatch):
    transport,channel,sock,_=fake_ssh(monkeypatch,response())
    transport.start_client.side_effect=socket.timeout('private diagnostic must not escape')
    failure('timeout',remote.infer,payload(),3)
    transport.close.assert_called();sock.close.assert_called()


def test_busy_gate_shared_by_health_and_inference(configured,monkeypatch):
    exchange=Mock(side_effect=AssertionError('must not execute'))
    monkeypatch.setattr(remote,'_exchange',exchange)
    assert remote._GATE.acquire(blocking=False)
    try:
        failure('busy',remote.infer,payload(),3)
        assert remote.health() is False
    finally:remote._GATE.release()
    exchange.assert_not_called()


@pytest.mark.parametrize('available',[False,1,'true',None])
def test_health_requires_strict_boolean(configured,monkeypatch,available):
    monkeypatch.setattr(remote,'_exchange',lambda *_:{'operation':'health','result':{'available':available,'model':remote.MODEL_ID}})
    assert remote.health() is False


@pytest.mark.parametrize('port',[8091,8092])
def test_gateway_fixed_health_paths(port,monkeypatch):
    monkeypatch.setattr(gateway,'_slot',nullcontext)
    http=Mock(side_effect=[{'status':'ok'},{'data':[{'id':remote.MODEL_ID}]}])
    monkeypatch.setattr(gateway,'_http',http)
    value=json.loads(gateway.handle(remote.envelope('health',None,3),port))
    assert value['result']=={'available':True,'model':remote.MODEL_ID}
    assert [(args[0],args[1],args[2]) for args,_ in http.call_args_list]==[(port,'/health',None),(port,'/v1/models',None)]


def test_gateway_no_model_or_port_fallback(monkeypatch):
    monkeypatch.setattr(gateway,'_slot',nullcontext)
    http=Mock(return_value={'model':'moduyuga-qwen3-4b','choices':[]})
    monkeypatch.setattr(gateway,'_http',http)
    failure('unsupported_model',gateway.handle,remote.envelope('infer',payload(),3),8092)
    assert http.call_count==1 and http.call_args.args[0:2]==(8092,'/v1/chat/completions')
    failure('invalid_configuration',gateway.handle,remote.envelope('health',None,3),9999)


@pytest.mark.parametrize('port,path',[(80,'/health'),(8091,'/arbitrary'),(8092,'https://elsewhere')])
def test_gateway_blocks_other_http_destinations(monkeypatch,port,path):
    connect=Mock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(gateway.http.client,'HTTPConnection',connect)
    failure('invalid_configuration',gateway._http,port,path,None,100)
    connect.assert_not_called()


@pytest.mark.parametrize('status,raw,code',[(302,b'{}','unavailable'),(500,b'{}','unavailable'),
    (200,b'x'*60001,'oversized_output'),(200,b'{"x":1,"x":2}','invalid_output')])
def test_gateway_http_bounds_no_redirects(monkeypatch,status,raw,code):
    client=Mock();reply=Mock(status=status);reply.read.return_value=raw;client.getresponse.return_value=reply
    factory=Mock(return_value=client)
    monkeypatch.setattr(gateway.http.client,'HTTPConnection',factory)
    failure(code,gateway._http,8091,'/health',None,gateway.time.monotonic()+3)
    assert factory.call_args.args==('127.0.0.1',8091)
    assert client.request.call_count==1
    client.close.assert_called()


@pytest.mark.parametrize('original',['','bash','scp -t /tmp/x','internal-sftp','moduyuga-inference-v1 other'])
def test_gateway_rejects_other_original_commands(monkeypatch,original):
    monkeypatch.setattr(gateway,'os',SimpleNamespace(name='posix',environ=gateway.os.environ,umask=Mock()))
    monkeypatch.setattr(gateway.signal,'ITIMER_REAL',0,raising=False)
    monkeypatch.setenv('SSH_ORIGINAL_COMMAND',original)
    monkeypatch.setattr(gateway.sys,'argv',['gateway'])
    stdout=SimpleNamespace(buffer=io.BytesIO())
    monkeypatch.setattr(gateway.sys,'stdout',stdout)
    monkeypatch.setattr(gateway.signal,'setitimer',Mock(),raising=False)
    assert gateway.main()==0
    assert json.loads(stdout.buffer.getvalue())=={'version':1,'ok':False,'error':'invalid_request'}


def test_gateway_expired_operation_has_output_deadline(monkeypatch):
    monkeypatch.setattr(gateway,'os',SimpleNamespace(name='posix',environ=gateway.os.environ,umask=Mock()))
    monkeypatch.setattr(gateway.signal,'ITIMER_REAL',0,raising=False)
    monkeypatch.setenv('SSH_ORIGINAL_COMMAND',remote.COMMAND)
    monkeypatch.setattr(gateway.sys,'argv',['gateway'])
    monkeypatch.setattr(gateway.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(remote.envelope('health',None,3))))
    stdout=SimpleNamespace(buffer=io.BytesIO());monkeypatch.setattr(gateway.sys,'stdout',stdout)
    monkeypatch.setattr(gateway.signal,'SIGALRM',14,raising=False)
    monkeypatch.setattr(gateway.signal,'ITIMER_REAL',0,raising=False)
    monkeypatch.setattr(gateway.signal,'signal',Mock())
    alarm=Mock();monkeypatch.setattr(gateway.signal,'setitimer',alarm,raising=False)
    monkeypatch.setattr(gateway,'handle',Mock(side_effect=remote.TransportError('timeout')))
    assert gateway.main()==0
    assert json.loads(stdout.buffer.getvalue())['error']=='timeout'
    assert [call.args[1] for call in alarm.call_args_list]==[5,4,1,0]


@pytest.mark.parametrize('error',[{},[],None,123,'private traceback'])
def test_error_codes_are_sanitized(error):assert str(remote.TransportError(error))=='unavailable'


def test_lone_unicode_surrogate_rejected():
    value=payload();value['messages'][1]['content']='\ud800'
    failure('invalid_request',remote.validate_payload,value)


@pytest.mark.parametrize('output',[b'private raw diagnostic',b'{"version":1,"version":1}',b'{"x":NaN}'])
def test_remote_malformed_json_is_output_error(configured,monkeypatch,output):
    transport,channel,sock,_=fake_ssh(monkeypatch,output)
    failure('invalid_output',remote.infer,payload(),3)
    assert channel.closed;transport.close.assert_called();sock.close.assert_called()


def test_deadline_timer_closes_transport_and_is_cancelled(configured,monkeypatch):
    transport,_,_,_=fake_ssh(monkeypatch,response())
    timer=Mock();factory=Mock(return_value=timer)
    monkeypatch.setattr(remote.threading,'Timer',factory)
    remote.infer(payload(),3)
    assert 0<factory.call_args.args[0]<=3
    assert factory.call_args.args[1]==transport.close
    assert timer.daemon is True
    timer.start.assert_called_once();timer.cancel.assert_called_once()
    factory.call_args.args[1]()
    assert transport.close.call_count==2


@pytest.mark.parametrize('busy',[False,True])
def test_gateway_cross_process_lock_contract(monkeypatch,busy):
    import sys
    fcntl=SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=Mock())
    if busy:fcntl.flock.side_effect=BlockingIOError()
    monkeypatch.setitem(sys.modules,'fcntl',fcntl)
    handle=Mock();handle.fileno.return_value=9
    context=Mock();context.__enter__=Mock(return_value=handle);context.__exit__=Mock(return_value=False)
    opened=Mock(return_value=9)
    monkeypatch.setattr(gateway,'os',SimpleNamespace(name='posix',open=opened,
        O_RDWR=2,O_CREAT=64,O_NOFOLLOW=131072,fdopen=Mock(return_value=context)))
    if busy:
        with pytest.raises(remote.TransportError) as caught:
            with gateway._slot():pytest.fail('busy lock entered')
        assert caught.value.code=='busy'
    else:
        with gateway._slot():pass
        assert fcntl.flock.call_args_list[1].args==(9,fcntl.LOCK_UN)
    assert opened.call_args.args==(gateway.ROOT/'.runtime/restricted-inference.lock',131138,0o600)
    assert fcntl.flock.call_args_list[0].args==(9,fcntl.LOCK_EX|fcntl.LOCK_NB)
    context.__exit__.assert_called_once()


def test_huge_json_numbers_fail_closed_without_float_overflow():
    value=payload();value['temperature']=10**1000
    failure('invalid_request',remote.validate_payload,value)
    failure('invalid_request',remote.decode_envelope,json.dumps({'version':1,'operation':'health','timeout_seconds':10**1000}).encode())
    failure('invalid_configuration',remote._call,'health',None,10**1000)
    assert remote.decode_envelope(remote.envelope('health',None,10**1000))['timeout_seconds']==40
