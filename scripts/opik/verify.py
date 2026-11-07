"""Actual SDK trace persistence and loopback/resource verification, synthetic metadata only."""
import json
import ipaddress
import os
from pathlib import Path
import re
import time
import urllib.request
from uuid import uuid4

from manage import ROOT,RUNTIME,PORTS,ctl,http,wait_http


def service_rss():
    supervisor=int((RUNTIME/'run/supervisord.pid').read_text())
    pending=[supervisor];pids=[]
    while pending:
        pid=pending.pop()
        if pid in pids:continue
        pids.append(pid)
        path=Path('/proc')/str(pid)/'task'/str(pid)/'children'
        try:pending.extend(map(int,path.read_text().split()))
        except (FileNotFoundError,ProcessLookupError):pass
    rss=0
    for pid in pids:
        try:rss+=int((Path('/proc')/str(pid)/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except (FileNotFoundError,ProcessLookupError):pass
    return {'process_count':len(pids),'rss_bytes':rss,'rss_mib':round(rss/1024**2,2)}


def is_loopback(address,family):
    raw=bytes.fromhex(address)
    if family=='tcp':raw=raw[::-1]
    else:raw=b''.join(raw[index:index+4][::-1] for index in range(0,16,4))
    parsed=ipaddress.ip_address(raw)
    return parsed.is_loopback or bool(getattr(parsed,'ipv4_mapped',None) and parsed.ipv4_mapped.is_loopback)


def bindings():
    rows=[]
    for name in ['tcp','tcp6']:
        for line in Path('/proc/net/'+name).read_text().splitlines()[1:]:
            parts=line.split()
            if parts[3]!='0A':continue
            address,port=parts[1].split(':');port=int(port,16)
            if port in PORTS.values():rows.append({'port':port,'address_hex':address,'family':name})
    if any(not is_loopback(row['address_hex'],row['family']) for row in rows):
        raise RuntimeError('Native Opik listener is not loopback-only')
    return rows


def get_trace(identifier):
    request=urllib.request.Request('http://127.0.0.1:'+str(PORTS['frontend'])+'/api/v1/private/traces/'+identifier,
                                   headers={'Comet-Workspace':'default'})
    with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)


def verify():
    os.environ.update({'HOME':str(RUNTIME/'home'),'TMPDIR':str(RUNTIME/'tmp'),
                       'OPIK_URL_OVERRIDE':'http://127.0.0.1:'+str(PORTS['frontend'])+'/api',
                       'OPIK_PROJECT_NAME':'moduyuga-native-validation'})
    from opik import Opik
    import importlib.metadata
    request_id=uuid4().hex
    client=Opik(host=os.environ['OPIK_URL_OVERRIDE'],project_name='moduyuga-native-validation',workspace='default',batching=False)
    trace=client.trace(name='validation.metadata_only',input=None,output=None,metadata={
        'request_id':request_id,'stages_ms':{},'public_sources':[],'outcome':'retrieval_only',
        'capture_input':False,'capture_output':False})
    identifier=trace.id;trace.end()
    if not client.flush(timeout=15):raise RuntimeError('Actual Opik SDK flush failed')
    deadline=time.monotonic()+30
    while True:
        try:
            before=get_trace(identifier)
            if before.get('metadata',{}).get('request_id')==request_id:break
        except Exception:
            if time.monotonic()>deadline:raise
        if time.monotonic()>deadline:raise RuntimeError('Actual SDK trace was not retrievable')
        time.sleep(1)
    if before.get('input') not in (None,{}) or before.get('output') not in (None,{}):raise RuntimeError('Unexpected captured input/output')
    listeners=bindings();memory=service_rss()
    if memory['rss_bytes']>8*1024**3:
        ctl('stop','all')
        raise RuntimeError('Dedicated Opik exceeded the 8GiB service RSS budget; stopped only Opik services')
    print('SDK metadata-only trace created and fetched through frontend /api',flush=True)
    ctl('restart','opik-backend')
    wait_http('/health-check',PORTS['backend'],seconds=180)
    after=get_trace(identifier)
    if after.get('metadata',{}).get('request_id')!=request_id:raise RuntimeError('Trace missing after backend restart')
    if after.get('input') not in (None,{}) or after.get('output') not in (None,{}):raise RuntimeError('Unexpected persisted input/output')
    final_memory=service_rss()
    if final_memory['rss_bytes']>8*1024**3:
        ctl('stop','opik-backend','opik-clickhouse','opik-mysql','opik-redis','opik-zookeeper','opik-minio','opik-frontend')
        raise RuntimeError('Dedicated Opik exceeded RSS budget after restart')
    report={'schema_version':1,'checked_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'release':'2.2.142','source_revision':'80b3a887a9cf8daaf61cae01b1d2ee7342e47c75',
            'sdk_version':importlib.metadata.version('opik'),'sdk_host':os.environ['OPIK_URL_OVERRIDE'],
            'backend_health':http('/health-check',PORTS['backend'])[0],
            'frontend_health':http('/health',PORTS['frontend'])[0],
            'frontend_html':b'<html' in http('/',PORTS['frontend'])[1].lower(),
            'trace_id':identifier,'request_id':request_id,'retrieved_before_restart':True,
            'retrieved_after_backend_restart':True,'input_output_capture':False,
            'data':'Synthetic metadata only; no model inference or member text in this validation.',
            'listeners':listeners,'memory_before_restart':memory,'memory_after_restart':final_memory,
            'rss_budget_bytes':8*1024**3,'provenance':json.loads((RUNTIME/'provenance.json').read_text()),
            'services':ctl('status').splitlines()}
    path=RUNTIME/'verification.json';path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
    print(json.dumps({key:report[key] for key in ['checked_at','sdk_version','sdk_host','backend_health','frontend_health','frontend_html','trace_id','retrieved_after_backend_restart','input_output_capture','memory_after_restart']}),flush=True)
    client.end()
    return report


if __name__=='__main__':verify()
