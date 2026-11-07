"""Delivery failure accounting must not turn partial telemetry into success."""
import queue
from types import SimpleNamespace

import pytest
from app import observability as obs


@pytest.fixture
def telemetry(monkeypatch):
    monkeypatch.setenv('ASSISTANT_OPIK_ENABLED', 'true')
    monkeypatch.setenv('OPIK_URL_OVERRIDE', 'http://127.0.0.1:15173/api')
    monkeypatch.setattr(obs, '_QUEUE', queue.Queue(maxsize=1))
    monkeypatch.setattr(obs, '_STATS', dict.fromkeys(obs._STATS, 0))
    monkeypatch.setattr(obs, '_failed', False)
    monkeypatch.setattr(obs,'_LAST_REMOTE_DELIVERY',None)
    monkeypatch.setattr(obs, '_worker', SimpleNamespace(is_alive=lambda: True))


def test_failure_then_success_still_reports_partial_delivery(telemetry, monkeypatch):
    monkeypatch.setattr(obs, '_send', lambda _: (_ for _ in ()).throw(RuntimeError('not logged')))
    obs._deliver({})
    monkeypatch.setattr(obs, '_send', lambda _: None)
    obs._deliver({})
    report = obs.delivery_snapshot()
    assert report['failed'] == 1 and report['sdk_flushed'] == 1
    assert report['persistence_verified'] is False
    assert obs.drain(timeout=0) is False


def test_full_queue_drop_survives_later_drain(telemetry, monkeypatch):
    obs.record('a'*32, {'total': 1}, [], 'retrieval_only')
    obs.record('b'*32, {'total': 1}, [], 'retrieval_only')
    assert obs.delivery_snapshot()['dropped'] == 1
    metadata = obs._QUEUE.get_nowait()
    monkeypatch.setattr(obs, '_send', lambda _: None)
    obs._deliver(metadata)
    obs._QUEUE.task_done()
    assert obs.delivery_snapshot()['pending'] == 0
    assert obs.drain(timeout=0) is False


def test_successful_flush_does_not_claim_server_persistence(telemetry, monkeypatch):
    obs.record('a'*32, {'total': 1}, [], 'retrieval_only')
    assert obs.drain(timeout=0) is False
    metadata = obs._QUEUE.get_nowait()
    monkeypatch.setattr(obs, '_send', lambda _: None)
    obs._deliver(metadata)
    obs._QUEUE.task_done()
    assert obs.drain(timeout=0) is True
    assert obs.delivery_snapshot() == {
        'enqueued': 1, 'sdk_flushed': 1, 'remote_accepted':0, 'remote_delivery':None, 'failed': 0, 'dropped': 0,
        'rejected': 0, 'pending': 0, 'persistence_verified': False,
        'scope': 'process_lifetime',
    }
