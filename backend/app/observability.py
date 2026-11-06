"""Optional genuine Opik SDK tracing of strictly allowlisted, non-member metadata."""
import importlib.util
import os
import queue
import re
import threading
import time
from urllib.parse import urlsplit

from . import observation_contract, remote_inference

_QUEUE = queue.Queue(maxsize=32)
_WORKER_LOCK = threading.Lock()
_worker = None
_failed = False
_client = None
_LAST_REMOTE_DELIVERY = None
_STATS_LOCK = threading.Lock()
_STATS = {'enqueued': 0, 'sdk_flushed': 0, 'remote_accepted': 0, 'failed': 0, 'dropped': 0, 'rejected': 0}
_ALLOWED_STAGES = {'retrieval', 'tools', 'generation', 'validation', 'total'}
_ALLOWED_OUTCOMES = {'generated', 'local_extractive', 'retrieval_only', 'abstained', 'error'}


def configured():
    if os.getenv('ASSISTANT_OPIK_ENABLED', '').lower() != 'true':
        return False
    if os.getenv('ASSISTANT_SSH_OBSERVE_ENABLED','').lower()=='true':
        return os.getenv('ASSISTANT_SSH_ENABLED','').lower()=='true'
    url = urlsplit(os.getenv('OPIK_URL_OVERRIDE', ''))
    return (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1') and
            not url.username and not url.password and not url.query and not url.fragment)


def status():
    if os.getenv('ASSISTANT_OPIK_ENABLED', '').lower() != 'true':
        return 'disabled'
    try:
        if os.getenv('ASSISTANT_SSH_OBSERVE_ENABLED','').lower()=='true':
            return 'configured' if configured() and not _failed else 'unavailable'
        return 'configured' if configured() and importlib.util.find_spec('opik') and not _failed else 'unavailable'
    except (ImportError, ValueError):
        return 'unavailable'


def sanitize(request_id, timings, sources, outcome):
    # There is deliberately no question, user, conversation, token, exception, or answer argument.
    if not re.fullmatch(r'[0-9a-f]{32}', request_id) or outcome not in _ALLOWED_OUTCOMES:
        return None
    public_sources = []
    for source in sources[:5]:
        if (isinstance(source, dict) and re.fullmatch(r'(?:guide|catalog|analysis):[a-z0-9-]{1,70}', str(source.get('source_id', ''))) and
                re.fullmatch(r'[0-9a-f]{64}', str(source.get('revision', '')))):
            public_sources.append({'source_id': source['source_id'], 'revision': source['revision']})
    stages = {key: round(min(120000., max(0., float(value))), 2) for key, value in timings.items()
              if key in _ALLOWED_STAGES and isinstance(value, (int, float))}
    return {'request_id': request_id, 'stages_ms': stages, 'public_sources': public_sources,
            'outcome': outcome, 'prompt_version': 'extractive-group-v5', 'capture_input': False, 'capture_output': False}


def _send(metadata):
    global _client, _LAST_REMOTE_DELIVERY
    if '_observation' in metadata:
        result=remote_inference.observe(metadata['_observation'])
        with _STATS_LOCK:_LAST_REMOTE_DELIVERY=dict(result['delivery'])
        if not result['accepted']:raise RuntimeError('remote_observation_rejected')
        return 'remote_accepted'
    if _client is None:
        from opik import Opik
        # Explicit loopback host prevents a configured cloud default from receiving data.
        _client = Opik(project_name=os.getenv('OPIK_PROJECT_NAME', 'moduyuga-public-assistant'),
                       host=os.environ['OPIK_URL_OVERRIDE'], batching=False)
    trace = _client.trace(name='assistant.request', input=None, output=None, metadata=metadata)
    trace.end()
    # This worker may block; it never blocks the member request or grows an unbounded queue.
    if _client.flush(timeout=2) is False:
        raise RuntimeError('trace_flush_failed')


def _count(key):
    with _STATS_LOCK:
        _STATS[key] += 1


def delivery_snapshot():
    """Process totals only. A successful SDK flush is not proof of persistence."""
    with _STATS_LOCK:
        counts = dict(_STATS)
        remote_delivery=dict(_LAST_REMOTE_DELIVERY) if _LAST_REMOTE_DELIVERY is not None else None
    return {**counts, 'remote_delivery':remote_delivery, 'pending': _QUEUE.unfinished_tasks,
            'persistence_verified': False, 'scope': 'process_lifetime'}


def _deliver(metadata):
    global _failed
    try:
        delivered=_send(metadata)
        _count('remote_accepted' if delivered=='remote_accepted' else 'sdk_flushed')
    except Exception:
        # A later successful trace must not erase an earlier delivery failure.
        _failed = True
        _count('failed')


def _run():
    while True:
        metadata = _QUEUE.get()
        try:
            _deliver(metadata)
        finally:
            _QUEUE.task_done()


def record(request_id, timings, sources, outcome, *, error_code='none', tools=None, stage_status=None):
    global _worker
    try:
        if not configured():
            return
        metadata = sanitize(request_id, timings, sources, outcome)
        if not metadata:
            _count('rejected')
            return
        if os.getenv('ASSISTANT_SSH_OBSERVE_ENABLED','').lower()=='true':
            try:metadata={'_observation':observation_contract.from_sanitized(metadata,error_code=error_code,tools=tools,stage_status=stage_status)}
            except observation_contract.ObservationError:
                _count('rejected');return
        with _WORKER_LOCK:
            if _worker is None or not _worker.is_alive():
                _worker = threading.Thread(target=_run, name='assistant-opik', daemon=True)
                _worker.start()
        _QUEUE.put_nowait(metadata)
        _count('enqueued')
    except Exception:
        # Misconfiguration, a full queue or SDK failure cannot change a user response.
        _count('dropped')
        return


def drain(timeout=5):
    """Bounded shutdown/evaluation hook; this is SDK delivery, not server verification."""
    if not configured():
        return False
    deadline = time.monotonic()+min(10., max(0., timeout))
    while _QUEUE.unfinished_tasks and time.monotonic() < deadline:
        time.sleep(.02)
    totals = delivery_snapshot()
    return totals['pending'] == 0 and totals['failed'] == 0 and totals['dropped'] == 0 and totals['rejected'] == 0
