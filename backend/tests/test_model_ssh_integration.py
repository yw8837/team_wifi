"""Both transports must share evidence validation and never silently fail over."""
import json
import pytest
from app import knowledge, model_runtime as model, remote_inference as remote


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MODEL_ENABLED', 'true')
    monkeypatch.setenv('ASSISTANT_SSH_ENABLED', 'true')
    monkeypatch.setenv('ASSISTANT_MODEL_URL', 'http://127.0.0.1:8091/v1/chat/completions')
    monkeypatch.setattr(model.httpx, 'Client', lambda **_: pytest.fail('SSH must not silently use HTTP'))


def test_ssh_payload_and_evidence_validation_are_the_same(configured, monkeypatch):
    chunks=knowledge.retrieve('기저귀 단가를 배송비까지 어떻게 비교하나요?')
    assert chunks
    seen=[]
    def infer(payload, timeout):
        remote.validate_payload(payload)
        seen.append(payload)
        source=json.loads(payload['messages'][1]['content'])['evidence'][0]
        content=json.dumps({'claims':[{'source_id':source['source_id'],'group_index':0}]})
        return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':content}}]}).encode()
    monkeypatch.setattr(remote, 'infer', infer)
    answer,citations,_=model.generate('기저귀 단가를 배송비까지 어떻게 비교하나요?',chunks)
    assert citations and answer==citations[0]['quote']
    assert seen[0]['max_tokens']==400 and seen[0]['stream'] is False


@pytest.mark.parametrize('code',['host_key_mismatch','timeout','busy','unavailable'])
def test_transport_failure_remains_explicit_without_fallback(configured, monkeypatch, code):
    def fail(*args,**kwargs):raise remote.TransportError(code)
    monkeypatch.setattr(remote,'infer',fail)
    with pytest.raises(model.ModelFailure,match=code):
        model.generate('기저귀 단가 비교',knowledge.retrieve('기저귀 단가 비교'))


def test_status_is_passive_and_uses_only_recent_inference(configured, monkeypatch):
    monkeypatch.setattr(remote,'health',lambda **_:pytest.fail('public status must never connect'))
    monkeypatch.setattr(model,'_LAST_OUTCOME',{'at':None,'available':False})
    assert model.status()['availability_basis']=='no_recent_request'
    assert model.status()['available'] is False
    model._record_outcome(True)
    for _ in range(100):
        assert model.status()['available'] is True
    monkeypatch.setattr(model,'_LAST_OUTCOME',{'at':model.time.monotonic()-61,'available':True})
    assert model.status()['available'] is False
    assert model.status()['availability_basis']=='no_recent_request'
    model._record_outcome(True)
    assert model.status()['available'] is True
    monkeypatch.setenv('ASSISTANT_MODEL_ENABLED','false')
    monkeypatch.setattr(remote,'health',lambda **_:pytest.fail('disabled'))
    assert model.status()['available'] is False


def test_ssh_output_still_rejects_invented_citation(configured, monkeypatch):
    content=json.dumps({'claims':[{'source_id':'catalog:invented','group_index':0}]})
    monkeypatch.setattr(remote,'infer',lambda *a,**k:json.dumps({'choices':[{'message':{'content':content}}]}).encode())
    with pytest.raises(model.ModelFailure,match='invalid_citation'):
        model.generate('기저귀 단가 비교',knowledge.retrieve('기저귀 단가 비교'))
