"""Read actual Opik SDK traces for a frozen synthetic evaluation; never prints captured content."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'.runtime/opik'
FROZEN_SHA='73d03184ced03cc8ab8e83c5356aa6d8787c4439ddec72979652d9f7dcd50f97'
KEYS={'request_id','stages_ms','public_sources','outcome','prompt_version','capture_input','capture_output'}
STAGES={'retrieval','tools','generation','validation','total'}


def metadata_errors(metadata,allowed_sources):
    errors=[]
    if not isinstance(metadata,dict):return ['metadata_not_object']
    if set(metadata)-KEYS:errors.append('unexpected_metadata_keys')
    if not re.fullmatch('[0-9a-f]{32}',str(metadata.get('request_id',''))):errors.append('invalid_request_id')
    if metadata.get('capture_input') is not False or metadata.get('capture_output') is not False:errors.append('capture_not_disabled')
    if metadata.get('outcome') not in {'generated','local_extractive','retrieval_only','abstained','error'}:errors.append('invalid_outcome')
    stages=metadata.get('stages_ms',{})
    if not isinstance(stages,dict) or set(stages)-STAGES:errors.append('invalid_stage_keys')
    elif any(not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=120000 for value in stages.values()):errors.append('invalid_stage_value')
    sources=metadata.get('public_sources',[])
    if not isinstance(sources,list) or len(sources)>5:errors.append('invalid_public_sources')
    else:
        for source in sources:
            if not isinstance(source,dict) or set(source)!={'source_id','revision'}:
                errors.append('invalid_source_shape');continue
            if (source['source_id'],source['revision']) not in allowed_sources:errors.append('unapproved_source_version')
    if 'prompt_version' in metadata and not re.fullmatch('[a-z0-9-]{1,80}',str(metadata['prompt_version'])):errors.append('invalid_prompt_version')
    return sorted(set(errors))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation-report',required=True)
    parser.add_argument('--host',default='http://127.0.0.1:15173/api')
    parser.add_argument('--project',default='moduyuga-public-assistant')
    parser.add_argument('--expected-count',type=int,default=40)
    parser.add_argument('--output',default=str(RUNTIME/'evaluation-traces-verification.json'))
    args=parser.parse_args()
    host=urlsplit(args.host)
    if host.scheme!='http' or host.hostname not in {'127.0.0.1','localhost','::1'} or host.username or host.password or host.query or host.fragment or host.path not in {'','/api','/api/'}:parser.error('Only a loopback Opik endpoint is allowed')
    if not re.fullmatch('[a-zA-Z0-9_.-]{1,100}',args.project):parser.error('Invalid project name')
    output=Path(args.output).resolve()
    if RUNTIME.resolve() not in output.parents:parser.error('Output must be under the private Opik runtime')
    evaluation=json.loads(Path(args.evaluation_report).read_text(encoding='utf-8'))
    if evaluation.get('fixture_sha256')!=FROZEN_SHA:parser.error('The report must use the frozen synthetic fixture hash')
    cases=evaluation.get('results',[])
    expected={case.get('request_id'):case.get('generation',{}).get('mode') for case in cases}
    if len(cases)!=args.expected_count or len(expected)!=args.expected_count or not all(re.fullmatch('[0-9a-f]{32}',str(key)) for key in expected):parser.error('Expected unique synthetic request IDs do not match --expected-count')
    approved={(source['source_id'],source['revision']) for source in evaluation.get('public_corpus_snapshot',[])}
    os.environ.update({'HOME':str(RUNTIME/'home'),'TMPDIR':str(RUNTIME/'tmp'),'NO_PROXY':'127.0.0.1,localhost,::1'})
    from opik import Opik
    import importlib.metadata
    client=Opik(host=args.host,project_name=args.project,workspace='default',batching=False)
    # Search is explicitly non-truncated; then get each matching full trace again.
    traces=client.search_traces(project_name=args.project,max_results=1000,truncate=False,wait_for_timeout=20)
    found={key:[] for key in expected};checks=[]
    for summary in traces:
        metadata=getattr(summary,'metadata',None)
        request_id=metadata.get('request_id') if isinstance(metadata,dict) else None
        if request_id not in expected:continue
        trace=client.get_trace_content(id=str(summary.id))
        metadata=getattr(trace,'metadata',None)
        errors=metadata_errors(metadata,approved)
        input_null=getattr(trace,'input',None) is None
        output_null=getattr(trace,'output',None) is None
        if not input_null:errors.append('captured_input_present')
        if not output_null:errors.append('captured_output_present')
        if isinstance(metadata,dict) and metadata.get('outcome')!=expected[request_id]:errors.append('outcome_mismatch')
        found[request_id].append(str(trace.id))
        checks.append({'request_id':request_id,'trace_id':str(trace.id),'input_null':input_null,'output_null':output_null,'metadata_allowlist_valid':not metadata_errors(metadata,approved),'errors':sorted(set(errors))})
    missing=[key for key,values in found.items() if not values]
    duplicates=[key for key,values in found.items() if len(values)>1]
    report={'schema_version':1,'fixture_sha256':FROZEN_SHA,'sdk_version':importlib.metadata.version('opik'),
            'host':args.host,'project':args.project,'expected_count':args.expected_count,
            'matched_request_count':len(expected)-len(missing),'matched_trace_count':len(checks),
            'missing_request_ids':missing,'duplicate_request_ids':duplicates,'checks':checks,
            'passed':not missing and not duplicates and all(not check['errors'] for check in checks),
            'data_policy':'Read-only SDK verification. Captured input/output contents are never copied or printed.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');output.chmod(0o600)
    client.end()
    print(json.dumps({key:report[key] for key in ['expected_count','matched_request_count','matched_trace_count','passed']}))
    print('Private verification report: '+str(output))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
