"""Disabled candidate observation channel: privacy, admission and inference isolation."""
from copy import deepcopy
import json
import queue
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import observation_contract as contract, observation_collector as collector
from app import observability as obs, remote_inference as remote
from test_remote_inference import gateway, payload as inference_payload


def event():
    identifier,revision=next(iter(contract.source_map().items()))
    return {'schema_version':1,'prompt_version':'extractive-group-v5','outcome':'local_extractive',
        'stages':{'total':{'status':'completed','duration_ms':50}},'public_sources':[{'source_id':identifier,'revision':revision}],
        'validation':'exact_public_citation','error_code':'none','tools':{'public_catalog':1}}


def ack(accepted=True,reason='queued'):
    counts={key:0 for key in contract.COUNTERS}
    return {'accepted':accepted,'reason':reason,'delivery':{**counts,'persistence_verified':False,'scope':'process_lifetime'}}


def test_default_disabled_never_connects_or_discovers_credentials(monkeypatch):
    monkeypatch.delenv('ASSISTANT_SSH_OBSERVE_ENABLED',raising=False)
    network=Mock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(remote,'settings',network)
    with pytest.raises(remote.TransportError,match='disabled'):remote.observe(event())
    network.assert_not_called()


@pytest.mark.parametrize('name,value',[
    ('question','SYNTHETIC_PRIVATE_CANARY'),('answer','private answer'),('email','private@example.test'),
    ('nickname','private nickname'),('user_id','123'),('conversation_id','abc'),('request_id','a'*32),
    ('socket_path','/other/socket'),('url','https://example.test'),('metadata',{'private':'value'}),
])
def test_no_freeform_or_member_fields(name,value):
    body=event();body[name]=value
    with pytest.raises(contract.ObservationError,match='invalid_request'):contract.validate(body)


@pytest.mark.parametrize('updates',[
    {'schema_version':True},{'schema_version':2},{'prompt_version':'private'},
    {'outcome':'private text'},{'error_code':'private traceback'},{'validation':'human_verified'},
    {'stages':{'total':{'status':'private secret','duration_ms':1}}},
    {'stages':{'total':{'status':'completed','duration_ms':True}}},
    {'stages':{'total':{'status':'completed','duration_ms':1.5}}},
    {'stages':{'total':{'status':'completed','duration_ms':float('nan')}}},
    {'stages':{'total':{'status':'completed','duration_ms':120001}}},
    {'stages':{'total':{'status':'completed','duration_ms':-1}}},
    {'stages':{'private':{'status':'completed','duration_ms':1}}},
    {'tools':{'private account':1}},{'tools':{'own_saved':True}},{'tools':{'own_saved':17}},
    {'public_sources':[{'source_id':'member:private','revision':'a'*64}]},
    {'public_sources':[{'source_id':'guide:compare-unit','revision':'a'*64}]},
    {'public_sources':[]},
])
def test_strict_enums_numbers_and_static_source_revision(updates):
    body=event();body.update(updates)
    with pytest.raises(contract.ObservationError):contract.validate(body)


def test_duplicate_public_sources_and_extra_source_text_rejected():
    body=event();body['public_sources']*=2
    with pytest.raises(contract.ObservationError):contract.validate(body)
    body=event();body['public_sources'][0]['quote']='private question'
    with pytest.raises(contract.ObservationError):contract.validate(body)


def test_local_sanitized_record_discards_request_id():
    body=event()
    value=contract.from_sanitized({'request_id':'a'*32,'stages_ms':{'total':1.7},'public_sources':body['public_sources'],'outcome':'local_extractive'})
    assert 'request_id' not in json.dumps(value) and value['stages']['total']['duration_ms']==1
    assert value['stages']['total']['status']=='unknown'


def test_observation_has_a_separate_gate_from_inference(monkeypatch):
    monkeypatch.setenv('ASSISTANT_SSH_OBSERVE_ENABLED','true')
    monkeypatch.setattr(remote,'settings',lambda:object())
    def exchange(_config,raw,_timeout):
        decoded=json.loads(raw);operation=decoded['operation']
        return {'operation':operation,'result':ack() if operation=='observe' else {'model':remote.MODEL_ID,'choices':[]}}
    monkeypatch.setattr(remote,'_exchange',exchange)
    assert remote._GATE.acquire(blocking=False)
    try:assert remote.observe(event())['accepted']
    finally:remote._GATE.release()
    assert remote._OBSERVE_GATE.acquire(blocking=False)
    try:assert json.loads(remote.infer(inference_payload()))['model']==remote.MODEL_ID
    finally:remote._OBSERVE_GATE.release()


def test_gateway_observe_requires_explicit_operator_switch(monkeypatch):
    raw=remote.envelope('observe',event(),3)
    send=Mock(return_value=ack())
    monkeypatch.setattr(collector,'exchange',send)
    monkeypatch.setattr(gateway,'_http',Mock(side_effect=AssertionError('model HTTP forbidden')))
    monkeypatch.setattr(gateway,'_slot',Mock(side_effect=AssertionError('model lock forbidden')))
    with pytest.raises(remote.TransportError,match='disabled'):gateway.handle(raw)
    send.assert_not_called()
    value=json.loads(gateway.handle(raw,allow_observe=True))
    assert value['operation']=='observe' and value['result']['accepted']
    send.assert_called_once()


def test_collector_rate_queue_and_copy_boundaries():
    clock=[0.0];instance=collector.Collector(Mock(),clock=lambda:clock[0]);body=event()
    for _ in range(30):assert instance.admit(body)['accepted']
    body['error_code']='private secret'
    first=instance.queue.queue[0];assert first['error_code']=='none'
    assert not instance.admit(event())['accepted']
    assert instance.snapshot()['queued']==30 and instance.snapshot()['dropped']==1
    clock[0]=61
    assert instance.admit(event())['accepted'] and instance.admit(event())['accepted']
    assert not instance.admit(event())['accepted']
    assert instance.queue.qsize()==32


def test_collector_failure_sticks_and_stops_sdk_backlog_growth():
    sender=Mock(side_effect=RuntimeError('private exception never emitted'));instance=collector.Collector(sender)
    instance.deliver_one(event());instance.deliver_one(event())
    sender.assert_called_once()
    assert instance.snapshot()['failed']==1 and instance.snapshot()['dropped']==1
    assert instance.admit(event())['reason']=='unavailable'
    assert instance.snapshot()['persistence_verified'] is False


def test_collector_success_is_sdk_flush_not_persistence():
    instance=collector.Collector(Mock());assert instance.admit(event())['accepted']
    body=instance.queue.get_nowait();instance.deliver_one(body);instance.queue.task_done()
    assert instance.snapshot()['sdk_flushed']==1 and instance.snapshot()['pending']==0
    assert instance.snapshot()['persistence_verified'] is False
    contract.validate_ack(instance.ack(True,'queued'))


def test_sdk_call_has_no_inputs_outputs_request_or_member_ids(monkeypatch):
    import sys
    client=Mock();client.flush.return_value=True;factory=Mock(return_value=client)
    monkeypatch.setitem(sys.modules,'opik',SimpleNamespace(Opik=factory))
    sender=collector.SDKSender('http://127.0.0.1:15173/api');sender(event())
    assert factory.call_args.kwargs['host']=='http://127.0.0.1:15173/api'
    assert factory.call_args.kwargs['project_name']=='moduyuga-public-requests'
    fields=client.trace.call_args.kwargs
    assert fields['input'] is None and fields['output'] is None
    assert fields['metadata']['capture_input'] is False and fields['metadata']['capture_output'] is False
    assert 'request_id' not in fields['metadata'] and 'user_id' not in fields['metadata']
    client.flush.assert_called_once_with(timeout=2)


@pytest.mark.parametrize('url',['https://example.test/api','http://user:pass@127.0.0.1/api','http://127.0.0.1/api?token=x'])
def test_collector_never_defaults_to_cloud_or_arbitrary_destination(url):
    with pytest.raises(ValueError):collector.SDKSender(url)


class Frame:
    def __init__(self,raw):self.raw=bytearray(raw);self.read_sizes=[]
    def settimeout(self,value):assert value>0
    def recv(self,size):
        self.read_sizes.append(size);out=bytes(self.raw[:min(size,3)]);del self.raw[:len(out)];return out


@pytest.mark.parametrize('size',[0,4097,2**32-1])
def test_frame_rejects_oversized_length_before_reading_body(size):
    channel=Frame(struct.pack('>I',size))
    with pytest.raises(ValueError):collector.read_frame(channel,collector.time.monotonic()+1)
    assert max(channel.read_sizes)<=4


def test_frame_duplicate_keys_are_invalid():
    raw=b'{"schema_version":1,"schema_version":1}'
    with pytest.raises(ValueError):collector.read_frame(Frame(struct.pack('>I',len(raw))+raw),collector.time.monotonic()+1)


@pytest.mark.parametrize('change',[{'accepted':1},{'reason':{}},{'extra':'private'}, {'delivery':{'private':'text'}}])
def test_ack_is_bounded_and_not_a_freeform_return_channel(change):
    value=ack();value.update(change)
    with pytest.raises(contract.ObservationError):contract.validate_ack(value)


@pytest.fixture
def remote_telemetry(monkeypatch):
    monkeypatch.setenv('ASSISTANT_OPIK_ENABLED','true');monkeypatch.setenv('ASSISTANT_SSH_ENABLED','true');monkeypatch.setenv('ASSISTANT_SSH_OBSERVE_ENABLED','true')
    monkeypatch.setattr(obs,'_QUEUE',queue.Queue(maxsize=1));monkeypatch.setattr(obs,'_STATS',dict.fromkeys(obs._STATS,0));monkeypatch.setattr(obs,'_LAST_REMOTE_DELIVERY',None);monkeypatch.setattr(obs,'_failed',False)
    monkeypatch.setattr(obs,'_worker',SimpleNamespace(is_alive=lambda:True))


def test_remote_record_is_nonblocking_and_ack_not_called_persistence(remote_telemetry,monkeypatch):
    sender=Mock(return_value=ack());monkeypatch.setattr(remote,'observe',sender)
    source=event()['public_sources']
    obs.record('a'*32,{'total':1},source,'local_extractive',tools={'public_groupbuys':1},stage_status={'total':'completed'})
    sender.assert_not_called()
    metadata=obs._QUEUE.get_nowait();assert 'request_id' not in json.dumps(metadata)
    obs._deliver(metadata);obs._QUEUE.task_done()
    counts=obs.delivery_snapshot()
    assert counts['remote_accepted']==1 and counts['sdk_flushed']==0 and counts['remote_delivery']['persistence_verified'] is False
    assert obs.drain(timeout=0) is True


def test_unlisted_sources_or_private_fields_are_rejected_before_queue(remote_telemetry):
    obs.record('a'*32,{'total':1},[{'source_id':'guide:made-up-private','revision':'a'*64}],'local_extractive')
    assert obs.delivery_snapshot()['rejected']==1 and obs._QUEUE.empty()
    assert not obs.drain(timeout=0)


def test_observation_failure_never_changes_caller_return(remote_telemetry,monkeypatch):
    monkeypatch.setattr(remote,'observe',Mock(side_effect=remote.TransportError('disabled')))
    obs.record('a'*32,{'total':1},event()['public_sources'],'local_extractive')
    metadata=obs._QUEUE.get_nowait();obs._deliver(metadata);obs._QUEUE.task_done()
    assert obs.delivery_snapshot()['failed']==1 and obs.status()=='unavailable'


def test_tool_capture_keeps_attempted_query_on_failure_and_resets():
    from app import assistant_tools
    database=Mock();database.scalars.side_effect=RuntimeError('private database detail')
    captured={}
    with pytest.raises(RuntimeError):
        with assistant_tools.capture_tool_calls(captured):assistant_tools.live_read(database,None,'기저귀 공구')
    assert captured=={'public_community':1}
    assert assistant_tools._TOOL_CALLS.get() is None


def test_tool_capture_is_separate_for_concurrent_requests():
    from app import assistant_tools
    from concurrent.futures import ThreadPoolExecutor
    def capture(name):
        with assistant_tools.capture_tool_calls() as counts:
            assistant_tools._tool_call(name,{})
            return dict(counts)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(capture,['own_saved','public_groupbuys']))
    assert results==[{'own_saved':1},{'public_groupbuys':1}]
    assert assistant_tools._TOOL_CALLS.get() is None


def test_disabled_collector_never_starts_socket_or_sdk(monkeypatch):
    monkeypatch.delenv('ASSISTANT_OBSERVE_COLLECTOR_ENABLED',raising=False)
    server=Mock(side_effect=AssertionError('must not start'))
    monkeypatch.setattr(collector,'serve',server)
    with pytest.raises(SystemExit,match='disabled'):collector.main()
    server.assert_not_called()


def test_deployment_source_map_matches_current_public_corpus():
    from app import knowledge
    assert contract.source_map()=={chunk.source_id:chunk.revision for chunk in knowledge.corpus()}
