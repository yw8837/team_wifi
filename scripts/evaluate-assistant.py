#!/usr/bin/env python
"""Evaluate frozen PUBLIC/SYNTHETIC cases against the real local assistant adapter.

No member database is opened. Live state and account isolation are reported only
when the separate disposable-data pytest contracts are explicitly run. Human
entailment review remains unscored until performed; quote checks are a proxy.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
FIXTURE = ROOT / 'backend/tests/fixtures/assistant-evaluation.json'


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1)*quantile
    low, high = math.floor(index), math.ceil(index)
    return round(ordered[low] + (ordered[high]-ordered[low])*(index-low), 3)


def load_fixture():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    if data.get('synthetic_only') is not True or data.get('schema_version') != 1:
        raise ValueError('Only the bundled, declared synthetic fixture is accepted.')
    cases = data['cases']
    if len(cases) != 40 or len({case['id'] for case in cases}) != 40:
        raise ValueError('Expected exactly 30 frozen and 10 holdout cases.')
    if sum(case['split'] == 'frozen' for case in cases) != 30 or sum(case['split'] == 'holdout' for case in cases) != 10:
        raise ValueError('Invalid frozen/holdout partition.')
    return data


def evaluate_case(case, inference, knowledge, model_runtime, retrieval_answer, repeat):
    started = time.perf_counter()
    chunks = knowledge.retrieve(case['question'])
    retrieved_at = time.perf_counter()
    unsupported = knowledge.unsupported(case['question'])
    reason, answer, citations, model = None, '', [], None
    inference_ms = None
    attempted = False
    if unsupported:
        mode, reason = 'abstained', unsupported
    elif not chunks:
        mode, reason = 'retrieval_only', 'no_evidence'
        answer, citations = retrieval_answer([])
    elif inference:
        attempted = True
        inference_started = time.perf_counter()
        try:
            answer, citations, model = model_runtime.generate(case['question'], chunks)
            mode = 'local_extractive'
        except model_runtime.ModelFailure as error:
            mode, reason = 'retrieval_only', error.code
            answer, citations = retrieval_answer(chunks)
        inference_ms = (time.perf_counter()-inference_started)*1000
    else:
        mode, reason = 'retrieval_only', 'inference_not_requested'
        answer, citations = retrieval_answer(chunks)
    current = {chunk.source_id: chunk for chunk in knowledge.corpus()}
    validity = [citation['source_id'] in current and
                current[citation['source_id']].revision == citation['revision'] and
                citation['quote'] in current[citation['source_id']].text for citation in citations]
    found = {chunk.source_id for chunk in chunks}
    gold = set(case['gold_source_ids'])
    recall = len(gold & found)/len(gold) if case['retrieval_applicable'] and gold else None
    expected = case['expected_outcome']
    if expected == 'supported':
        outcome_pass = bool(citations) and all(validity)
    elif expected == 'no_evidence':
        outcome_pass = reason == 'no_evidence' and not citations
    else:
        outcome_pass = mode == 'abstained' and reason == expected and not citations
    finished = time.perf_counter()
    return {'id': case['id'], 'split': case['split'], 'group': case['group'], 'repeat': repeat,
            'synthetic_question': case['question'], 'expected_outcome': expected,
            'support_expectation_for_human_review': case['support_expectation'],
            'retrieved_source_ids': [chunk.source_id for chunk in chunks], 'gold_source_ids': sorted(gold),
            'recall_at_5': recall, 'generation': {'mode': mode, 'reason': reason, 'model': model},
            'inference_attempted': attempted, 'latency_ms': {'retrieval': round((retrieved_at-started)*1000,3),
                'inference': round(inference_ms,3) if inference_ms is not None else None,
                'total': round((finished-started)*1000,3)},
            'synthetic_answer': answer, 'citations': citations,
            'citation_valid': validity, 'automated_contract_pass': outcome_pass,
            'groundedness_human_review': {'supported': None, 'reviewer': None, 'notes': None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['frozen','holdout','all'], default='frozen')
    parser.add_argument('--output', required=True, help='Report file inside E:/Team_Wifi only')
    parser.add_argument('--run-inference', action='store_true', help='Call the explicitly configured loopback model')
    parser.add_argument('--repeat', type=int, default=1, choices=range(1,6))
    parser.add_argument('--cold-start-confirmed', action='store_true', help='Operator confirms model was restarted before the first inference')
    parser.add_argument('--run-contracts', action='store_true', help='Run disposable-data pytest isolation/lifecycle contracts')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output == ROOT or ROOT not in output.parents:
        parser.error('The output must resolve inside the approved E:/Team_Wifi workspace.')
    if args.cold_start_confirmed and not args.run_inference:
        parser.error('--cold-start-confirmed requires --run-inference')
    fixture = load_fixture()
    from app import knowledge, model_runtime, observability
    from app.assistant import retrieval_answer
    selected = [case for case in fixture['cases'] if args.split == 'all' or case['split'] == args.split]
    snapshots = [{'source_id': chunk.source_id, 'revision': chunk.revision,
                  'chunk_id': chunk.chunk_id, 'checked_at': chunk.checked_at} for chunk in knowledge.corpus()]
    endpoint, model, timeout, enabled = model_runtime.settings()
    if args.run_inference and not enabled:
        parser.error('Set ASSISTANT_MODEL_ENABLED=true explicitly for real inference.')
    results = []
    first_inference = True
    for repeat in range(args.repeat):
        for case in selected:
            result = evaluate_case(case, args.run_inference, knowledge, model_runtime, retrieval_answer, repeat)
            if result['inference_attempted']:
                if first_inference:
                    result['runtime_phase'] = 'cold' if args.cold_start_confirmed else 'first_call_unconfirmed'
                    first_inference = False
                else:
                    result['runtime_phase'] = 'warm'
            else:
                result['runtime_phase'] = 'no_inference'
            result['request_id'] = uuid4().hex
            observability.record(result['request_id'], {'retrieval':result['latency_ms']['retrieval'],
                'generation':result['latency_ms']['inference'] or 0, 'total':result['latency_ms']['total']},
                result['citations'], result['generation']['mode'])
            results.append(result)
            print(case['id']+' '+result['generation']['mode']+' '+str(result['generation']['reason'] or 'ok'), flush=True)
    applicable = [result['recall_at_5'] for result in results if result['recall_at_5'] is not None]
    attempted = [result for result in results if result['inference_attempted']]
    # Busy/disabled requests did not reach inference; rejected/timeout requests
    # must not make the reported generated-answer latency look artificially fast.
    warm_requests = [result['latency_ms']['inference'] for result in attempted if result['runtime_phase'] == 'warm']
    warm = [result['latency_ms']['inference'] for result in attempted
            if result['runtime_phase'] == 'warm' and result['generation']['mode'] in ('generated', 'local_extractive')]
    validity = [valid for result in results for valid in result['citation_valid']]
    contracts = {'executed': False, 'suite': 'backend/tests/test_assistant.py',
                 'scope': 'disposable synthetic DB only; IDOR, revocation, changed/hidden sources, race close, expiry, SDK failure',
                 'exit_code': None, 'pytest_summary': None}
    if args.run_contracts:
        process = subprocess.run([sys.executable,'-m','pytest',str(ROOT/'backend/tests/test_assistant.py'),
                                  '-q','-p','no:cacheprovider'], cwd=ROOT, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=600,
                                 env={**os.environ, 'PYTHONPATH':str(ROOT/'backend'),
                                      'TEMP':str(ROOT/'.runtime/tmp'), 'TMP':str(ROOT/'.runtime/tmp')})
        matches = re.findall(r'\d+ passed[^\r\n]*|\d+ failed[^\r\n]*', process.stdout)
        contracts.update(executed=True, exit_code=process.returncode, pytest_summary=matches[-1] if matches else 'No parsed summary; inspect test execution separately.')
    trace_delivery = observability.drain(timeout=5)
    report = {'schema_version':1,
              'observability': {'status':observability.status(), 'sdk_queue_drained_without_error':trace_delivery,
                                'delivery_totals':observability.delivery_snapshot(),
                                'note':'Manual metadata-only SDK traces. Verify trace persistence at the self-hosted endpoint separately.'}, 'created_at':datetime.now(timezone.utc).isoformat(),
              'fixture_sha256':hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
              'fixture_frozen_at':fixture['frozen_at'], 'split':args.split, 'repeat':args.repeat,
              'data_policy':'Only bundled public/synthetic cases; no production member DB or original member text.',
              'execution':'actual_local_model' if args.run_inference else 'retrieval_only_no_model_calls',
              'runtime':{'endpoint':endpoint,'model':model if enabled else None,'deadline_seconds':timeout,
                         'model_revision':os.getenv('ASSISTANT_MODEL_REVISION'),
                         'model_sha256':os.getenv('ASSISTANT_MODEL_SHA256'),
                         'llama_cpp_revision':os.getenv('ASSISTANT_LLAMA_CPP_REVISION'),
                         'cold_start_operator_confirmed':args.cold_start_confirmed},
              'public_corpus_snapshot':snapshots,
              'metrics':{'cases':len(results),'retrieval_applicable_cases':len(applicable),
                         'recall_at_5':round(statistics.mean(applicable),6) if applicable else None,
                         'citation_count':len(validity),'citation_validity_rate':sum(validity)/len(validity) if validity else None,
                         'automated_contract_pass_rate':sum(result['automated_contract_pass'] for result in results)/len(results),
                         'groundedness_human_review':None,
                         'groundedness_note':'Citation existence, exact quotes, numeric and lexical checks are automated proxies, not human entailment review.',
                         'inference_attempts':len(attempted),
                         'generated_count':sum(result['generation']['mode']=='generated' for result in attempted),
                         'local_extractive_count':sum(result['generation']['mode']=='local_extractive' for result in attempted),
                         'busy_count':sum(result['generation']['reason']=='busy' for result in attempted),
                         'timeout_rate':sum(result['generation']['reason']=='timeout' for result in attempted)/len(attempted) if attempted else None,
                         'warm_inference_p50_ms':percentile(warm,.5),'warm_inference_p95_ms':percentile(warm,.95),
                         'warm_generated_samples':len(warm),
                         'warm_all_attempt_p50_ms':percentile(warm_requests,.5),'warm_all_attempt_p95_ms':percentile(warm_requests,.95),
                         'latency_definition':'warm_inference includes only completed validated model selections; all_attempt includes rejections/timeouts and is not inference speed.',
                         'cold_inference_ms':[result['latency_ms']['inference'] for result in attempted if result['runtime_phase']=='cold'],
                         'first_call_unconfirmed_ms':[result['latency_ms']['inference'] for result in attempted if result['runtime_phase']=='first_call_unconfirmed'],
                         'member_leakage_rate':None,
                         'leakage_note':'Synthetic generation contains no member data. Isolation/fresh-state evidence is the separate contract suite, not a population leakage estimate.'},
              'live_privacy_contracts':contracts, 'results':results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Report: '+str(output),flush=True)
    print(json.dumps(report['metrics'],ensure_ascii=False),flush=True)
    if args.run_contracts and contracts['exit_code'] != 0:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
