"""Real ASGI rejection boundaries emit one metadata record, never request data."""
import json

import pytest
from fastapi import HTTPException

from app import config, main, observability


@pytest.fixture(autouse=True)
def public_route(monkeypatch):
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    # This suite tests HTTP boundaries on SQLite; real quota concurrency has a PG gate.
    monkeypatch.setattr(config, 'deployed', lambda: False)


def test_validation_rejection_is_observed_without_submitted_values(setup, monkeypatch):
    client, _, _ = setup
    events = []
    monkeypatch.setattr(observability, 'record', lambda *args, **kwargs: events.append((args, kwargs)))
    response = client.post('/api/release/assistant/ask', json={'question': '', 'email': 'private@example.test'})
    assert response.status_code == 422
    assert len(events) == 1
    args, kwargs = events[0]
    assert args[2:] == ([], 'error')
    assert kwargs == {'error_code': 'invalid_request', 'tools': {}, 'stage_status': {'total': 'error'}}
    assert 'private@example.test' not in json.dumps(events)


@pytest.mark.parametrize('status,code', [(429, 'quota'), (503, 'unavailable')])
def test_guard_rejection_preserves_http_error_and_records_once(setup, monkeypatch, status, code):
    client, _, _ = setup
    events = []
    monkeypatch.setattr(config, 'deployed', lambda: True)
    def rejected(_request):
        raise HTTPException(status, 'guard response remains intact', headers={'Retry-After': '10'})
    monkeypatch.setattr(main, 'beta_write_guard', rejected)
    monkeypatch.setattr(observability, 'record', lambda *args, **kwargs: events.append((args, kwargs)))
    response = client.post('/api/release/assistant/ask', json={'question': 'private arbitrary question'})
    assert response.status_code == status and response.headers['Retry-After'] == '10'
    assert response.json()['detail'] == 'guard response remains intact'
    assert len(events) == 1 and events[0][1]['error_code'] == code
    assert 'private arbitrary question' not in json.dumps(events)


def test_observation_failure_does_not_replace_http_error(setup, monkeypatch):
    client, _, _ = setup
    def broken(*args, **kwargs):
        raise RuntimeError('synthetic private failure')
    monkeypatch.setattr(observability, 'record', broken)
    response = client.post('/api/release/assistant/ask', json={'question': ''})
    assert response.status_code == 422 and 'synthetic private failure' not in response.text


def test_route_error_is_not_recorded_twice_by_outer_boundary(setup, monkeypatch):
    client, _, _ = setup
    events = []
    monkeypatch.setattr(observability, 'record', lambda *args, **kwargs: events.append((args, kwargs)))
    response = client.post('/api/release/assistant/ask', json={'question': '젖병 비교', 'remember': True})
    assert response.status_code == 401
    assert len(events) == 1 and events[0][1]['error_code'] == 'auth_changed'
