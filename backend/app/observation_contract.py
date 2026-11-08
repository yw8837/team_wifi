"""Candidate metadata-only observation contract; contains no request/member fields."""
import json
import re
from pathlib import Path

MAX_BYTES=4096
STAGES={'retrieval','tools','generation','validation','total'}
OUTCOMES={'generated','local_extractive','retrieval_only','abstained','error'}
STATES={'completed','skipped','error','unknown'}
TOOLS={'public_catalog','own_saved','own_preferences','public_community','public_groupbuys'}
ERRORS={'none','disabled','busy','timeout','unavailable','invalid_output','invalid_citation','no_supported_claims','non_extractive_text','unsafe_output','oversized_output','host_key_mismatch','invalid_configuration','invalid_request','quota','auth_changed','evidence_changed'}
QUALITY={'exact_public_citation','retrieval_only','abstained','not_assessed'}
SOURCE_MAP=Path(__file__).with_name('observation_sources.json')
COUNTERS={'received','queued','sdk_flushed','failed','dropped','rejected','pending'}


class ObservationError(Exception):
    pass


def source_map():
    try:
        with SOURCE_MAP.open('rb') as stream:raw=stream.read(65537)
        if len(raw)>65536:raise ValueError()
        data=json.loads(raw)
        if set(data)!={'schema_version','sources'} or type(data['schema_version']) is not int or data['schema_version']!=1 or not isinstance(data['sources'],dict):raise ValueError()
        if len(data['sources'])>200 or any(not isinstance(k,str) or not re.fullmatch(r'(guide|catalog|analysis|official):[a-z0-9-]{1,70}',k) or not isinstance(v,str) or not re.fullmatch(r'[0-9a-f]{64}',v) for k,v in data['sources'].items()):raise ValueError()
        return data['sources']
    except (OSError,ValueError,TypeError):raise ObservationError('invalid_configuration') from None


def validate(body):
    required={'schema_version','prompt_version','outcome','stages','public_sources','validation','error_code','tools'}
    if not isinstance(body,dict) or set(body)!=required:raise ObservationError('invalid_request')
    if type(body['schema_version']) is not int or body['schema_version']!=1 or body['prompt_version']!='extractive-group-v5':raise ObservationError('invalid_request')
    for key,allowed in [('outcome',OUTCOMES),('validation',QUALITY),('error_code',ERRORS)]:
        if not isinstance(body[key],str) or body[key] not in allowed:raise ObservationError('invalid_request')
    stages=body['stages']
    if not isinstance(stages,dict) or not set(stages)<=STAGES or 'total' not in stages:raise ObservationError('invalid_request')
    for value in stages.values():
        if not isinstance(value,dict) or set(value)!={'status','duration_ms'} or not isinstance(value['status'],str) or value['status'] not in STATES:raise ObservationError('invalid_request')
        duration=value['duration_ms']
        if type(duration) is not int or not 0<=duration<=120000:raise ObservationError('invalid_request')
    tools=body['tools']
    if not isinstance(tools,dict) or not set(tools)<=TOOLS or any(type(v) is not int or not 0<=v<=16 for v in tools.values()):raise ObservationError('invalid_request')
    sources=body['public_sources'];allowed=source_map()
    if not isinstance(sources,list) or len(sources)>5:raise ObservationError('invalid_request')
    seen=set()
    for source in sources:
        if not isinstance(source,dict) or set(source)!={'source_id','revision'}:raise ObservationError('invalid_request')
        identifier,revision=source['source_id'],source['revision']
        if not isinstance(identifier,str) or not isinstance(revision,str) or identifier in seen or allowed.get(identifier)!=revision:raise ObservationError('invalid_request')
        seen.add(identifier)
    if body['validation']=='exact_public_citation' and (not sources or body['outcome'] not in {'generated','local_extractive'}):raise ObservationError('invalid_request')
    try:raw=json.dumps(body,ensure_ascii=True,separators=(',',':')).encode('ascii')
    except (TypeError,ValueError):raise ObservationError('invalid_request') from None
    if len(raw)>MAX_BYTES:raise ObservationError('invalid_request')
    return body


def from_sanitized(metadata,*,error_code='none',tools=None,stage_status=None):
    stages={}
    for name,value in metadata.get('stages_ms',{}).items():
        if name not in STAGES or type(value) not in (int,float):continue
        try:duration=min(120000,max(0,int(value)))
        except (ValueError,OverflowError):raise ObservationError('invalid_request') from None
        stages[name]={'status':(stage_status or {}).get(name,'unknown'),'duration_ms':duration}
    stages.setdefault('total',{'status':'unknown','duration_ms':0})
    # Request UUID is intentionally omitted. No member/user/conversation identifier is accepted.
    outcome=metadata['outcome'];sources=metadata.get('public_sources',[])
    validation='exact_public_citation' if outcome in {'generated','local_extractive'} and sources else 'retrieval_only' if outcome=='retrieval_only' else 'abstained' if outcome=='abstained' else 'not_assessed'
    return validate({'schema_version':1,'prompt_version':'extractive-group-v5','outcome':outcome,'stages':stages,'public_sources':sources,'validation':validation,'error_code':error_code,'tools':tools or {}})


def validate_ack(value):
    if not isinstance(value,dict) or set(value)!={'accepted','reason','delivery'} or type(value['accepted']) is not bool or not isinstance(value['reason'],str) or value['reason'] not in {'queued','busy','unavailable','invalid_request'}:raise ObservationError('invalid_output')
    counts=value['delivery']
    if not isinstance(counts,dict) or set(counts)!=COUNTERS|{'persistence_verified','scope'}:raise ObservationError('invalid_output')
    if counts['persistence_verified'] is not False or counts['scope']!='process_lifetime':raise ObservationError('invalid_output')
    if any(type(counts[key]) is not int or not 0<=counts[key]<=2**63-1 for key in COUNTERS):raise ObservationError('invalid_output')
    if value['accepted']!=(value['reason']=='queued'):raise ObservationError('invalid_output')
    return value
