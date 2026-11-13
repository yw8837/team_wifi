"""Request hook tests use synthetic SQLite state; never enable an observation transport."""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app import assistant, knowledge, model_runtime, observation_contract, observability, release
from app.db import Record, SessionLocal, Token
from test_assistant import chat, ask


@pytest.fixture
def observations(monkeypatch):
    records = []
    def capture(identifier, timings, sources, outcome, **extra):
        metadata = observability.sanitize(identifier, timings, sources, outcome)
        records.append(observation_contract.from_sanitized(metadata, **extra))
    monkeypatch.setattr(observability, 'record', capture)
    return records


def one(records, *, outcome, error='none'):
    assert len(records) == 1
    result = records[0]
    assert result['outcome'] == outcome and result['error_code'] == error
    assert result['stages']['total']['status'] == ('error' if outcome == 'error' else 'completed')
    assert set(result) == {'schema_version','prompt_version','outcome','stages','public_sources','validation','error_code','tools'}
    assert all(type(stage['duration_ms']) is int and stage['duration_ms'] >= 0 for stage in result['stages'].values())
    return result


def test_disabled_model_keeps_safe_fallback_and_one_record(chat, observations):
    c, p, _ = chat
    response = ask(c, p['buyer']['headers'], question='내 저장 목록과 내 관심 분야 젖병', remember=True)
    assert response.status_code == 200
    result = one(observations, outcome='retrieval_only', error='disabled')
    assert result['stages']['generation']['status'] == 'skipped'
    assert result['stages']['retrieval']['status'] == 'completed'
    assert result['stages']['tools']['status'] == 'completed'
    assert result['tools']['own_saved'] == result['tools']['own_preferences'] == 2
    assert result['tools']['public_catalog'] == result['tools']['public_community'] == 2
    serialized = json.dumps(result, ensure_ascii=False)
    for value in [p['buyer']['id'], response.json()['conversation_id'], response.json()['request_id'],
                  '내 저장 목록과 내 관심 분야 젖병', response.json()['answer'], 'buyer@example.com', 'buyer']:
        assert value not in serialized
    assert 'catalog:bottle' not in serialized  # Non-static synthetic source never crosses the contract.


@pytest.mark.parametrize('code', ['timeout','busy','invalid_citation','unsafe_output','unavailable'])
def test_model_failure_records_enum_and_generation_error(chat, observations, monkeypatch, code):
    def fail(*args):raise model_runtime.ModelFailure(code)
    monkeypatch.setattr(model_runtime, 'generate', fail)
    c, _, _ = chat
    assert ask(c).status_code == 200
    result = one(observations, outcome='retrieval_only', error=code)
    assert result['stages']['generation']['status'] == 'error'
    assert result['stages']['validation']['status'] == 'completed'


def test_no_evidence_records_skipped_generation(chat, observations, monkeypatch):
    monkeypatch.setattr(knowledge, 'retrieve', lambda question: [])
    c, _, _ = chat
    response = ask(c)
    assert response.status_code == 200 and response.json()['generation']['reason'] == 'no_evidence'
    result = one(observations, outcome='retrieval_only')
    assert result['stages']['retrieval']['status'] == 'completed'
    assert result['stages']['generation']['status'] == 'skipped'
    assert result['public_sources'] == []


@pytest.mark.parametrize('question,reason', [('아기 열이 나는데 약 복용량 알려줘','medical'), ('그건 어때?','clarification_needed')])
def test_abstention_records_skipped_generation(chat, observations, question, reason):
    c, _, _ = chat
    response = ask(c, question=question)
    assert response.status_code == 200 and response.json()['generation']['reason'] == reason
    result = one(observations, outcome='abstained')
    assert result['stages']['retrieval']['status'] == result['stages']['generation']['status'] == 'skipped'
    if reason == 'clarification_needed':
        assert result['tools'] == {} and result['stages']['tools']['status'] == 'skipped'


def test_initial_authorization_failure_is_observed_once(chat, observations):
    c, _, _ = chat
    assert ask(c, remember=True).status_code == 401
    result = one(observations, outcome='error', error='auth_changed')
    assert result['stages']['validation']['status'] == 'error'
    assert result['stages']['retrieval']['status'] == result['stages']['generation']['status'] == 'skipped'
    assert result['tools'] == {} and result['public_sources'] == []


def test_actual_failed_tool_keeps_count_without_error_text(chat, observations, monkeypatch):
    def fail(*args):raise HTTPException(503, 'PRIVATE@example.com UUID-PRIVATE DB failure')
    monkeypatch.setattr(release, 'saved_ids', fail)
    c, p, _ = chat
    assert ask(c, p['buyer']['headers'], question='내 저장 목록 젖병', remember=True).status_code == 503
    result = one(observations, outcome='error', error='unavailable')
    assert result['tools'] == {'public_catalog': 1, 'own_saved': 1}
    assert result['stages']['tools']['status'] == result['stages']['validation']['status'] == 'error'
    assert 'PRIVATE' not in json.dumps(result)
    with SessionLocal() as db:
        assert not list(db.scalars(select(Record).where(Record.kind == assistant.CHAT)))


def test_final_auth_change_is_observed_and_pending_text_is_removed(chat, observations, monkeypatch):
    c, p, _ = chat
    def revoke(question, chunks):
        with SessionLocal() as db:
            db.execute(delete(Token).where(Token.user_id == p['buyer']['id']));db.commit()
        raise model_runtime.ModelFailure('disabled')
    monkeypatch.setattr(model_runtime, 'generate', revoke)
    assert ask(c, p['buyer']['headers'], remember=True).status_code == 401
    result = one(observations, outcome='error', error='auth_changed')
    assert result['stages']['validation']['status'] == 'error'
    with SessionLocal() as db:
        assert not list(db.scalars(select(Record).where(Record.kind == assistant.CHAT)))


def test_changed_evidence_is_distinguished_from_generation_failure(chat, observations, monkeypatch):
    c, _, _ = chat
    def generated(question, chunks):return 'synthetic safe answer', [], 'local-model'
    monkeypatch.setattr(model_runtime, 'generate', generated)
    monkeypatch.setattr(knowledge, 'revalidate', lambda chunks: [])
    assert ask(c).status_code == 200
    result = one(observations, outcome='retrieval_only', error='evidence_changed')
    assert result['stages']['generation']['status'] == 'completed'
    assert result['stages']['validation']['status'] == 'error'


def test_unexpected_generation_error_has_no_exception_content(chat, observations, monkeypatch):
    c, _, _ = chat
    def fail(*args):raise RuntimeError('private@example.com question answer')
    monkeypatch.setattr(model_runtime, 'generate', fail)
    with pytest.raises(RuntimeError):ask(c)
    result = one(observations, outcome='error', error='unavailable')
    assert result['stages']['generation']['status'] == 'error'
    assert 'private@example.com' not in json.dumps(result)


def test_only_exact_static_public_sources_are_passed_to_record(monkeypatch, observations):
    allowed = observation_contract.source_map()
    identifier, revision = next(iter(allowed.items()))
    observation = assistant.RequestObservation()
    observation.citations([{'source_id':identifier, 'revision':revision, 'quote':'PRIVATE@example.com'}]*2)
    observation.outcome = 'local_extractive'
    observation.finish()
    result = one(observations, outcome='local_extractive')
    assert result['public_sources'] == [{'source_id':identifier, 'revision':revision}]
    assert result['validation'] == 'exact_public_citation'
    observation = assistant.RequestObservation()
    observation.citations([{'source_id':identifier, 'revision':'f'*64}])
    assert observation.sources == []
