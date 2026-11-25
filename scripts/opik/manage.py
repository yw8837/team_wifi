"""Manage only the dedicated Opik supervisor; existing supervisor/API/model are untouched."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import urllib.parse
import base64
from configure import PORTS,configure,find

ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT/'.runtime/opik';CONF=RUNTIME/'conf'


def command(args,env=None,timeout=120,log=None,input=None,check=True):
    environ={**os.environ,'HOME':str(RUNTIME/'home'),'TMPDIR':str(RUNTIME/'tmp'),**(env or {})}
    result=subprocess.run(list(map(str,args)),cwd=RUNTIME,env=environ,input=input,capture_output=True,text=True,timeout=timeout)
    if log:(RUNTIME/'logs'/log).write_text(result.stdout+result.stderr)
    if result.returncode and check:
        raise RuntimeError('Command failed: '+Path(str(args[0])).name+' exit '+str(result.returncode)+'; inspect private '+str(log or 'supervisor logs'))
    return result.stdout


def ctl(*args):
    return command([ROOT/'.venv/bin/supervisorctl','-c',CONF/'supervisord.conf',*args],check=args[0]!='status')


def wait_port(port,seconds=60):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=1):return
        except OSError:time.sleep(.5)
    raise RuntimeError('Opik loopback port did not become ready: '+str(port))


def http(path,port=18080,credentials=None,data=None):
    headers={}
    if credentials:headers['Authorization']='Basic '+base64.b64encode(credentials.encode()).decode()
    request=urllib.request.Request('http://127.0.0.1:'+str(port)+path,headers=headers,data=data)
    with urllib.request.urlopen(request,timeout=10) as response:return response.status,response.read(2_000_000)


def wait_http(path,port,seconds=90):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            if http(path,port)[0]==200:return
        except Exception:time.sleep(1)
    raise RuntimeError('Opik HTTP health not ready on '+str(port))


def start_infrastructure():
    launches=json.loads((CONF/'launch.json').read_text());tools=json.loads((CONF/'mysql-tools.json').read_text())
    if not (RUNTIME/'data/mysql/mysql').exists():
        print('Initializing isolated MySQL datadir',flush=True)
        command([tools['server'],'--no-defaults','--initialize-insecure','--basedir='+tools['basedir'],
                 '--datadir='+str(RUNTIME/'data/mysql'),'--lc-messages-dir='+tools['messages'],
                 '--plugin-dir='+tools['plugin']],env=tools['env'],timeout=180,log='mysql-initialize.log')
    if not (RUNTIME/'run/supervisor.sock').exists():
        command([ROOT/'.venv/bin/supervisord','-c',CONF/'supervisord.conf'])
    for name,port in [('mysql',PORTS['mysql']),('redis',PORTS['redis']),('zookeeper',PORTS['zookeeper']),('clickhouse',PORTS['clickhouse_http']),('minio',PORTS['minio'])]:
        status=ctl('status','opik-'+name)
        if 'RUNNING' not in status:print(ctl('start','opik-'+name).strip(),flush=True)
        wait_port(port)
    credentials=json.loads((CONF/'secrets.json').read_text())
    sql='CREATE DATABASE IF NOT EXISTS opik;\n'
    for host in ['localhost','127.0.0.1']:
        sql+="CREATE USER IF NOT EXISTS 'opik'@'"+host+"' IDENTIFIED BY '"+credentials['mysql']+"';\nGRANT ALL ON opik.* TO 'opik'@'"+host+"';\n"
    secured=CONF/'mysql-root-secured'
    mysqlenv={**tools['env'],**({'MYSQL_PWD':credentials['mysql_root']} if secured.exists() else {})}
    sql+="ALTER USER 'root'@'localhost' IDENTIFIED BY '"+credentials['mysql_root']+"';\n"
    command([tools['client'],'--no-defaults','--socket='+str(RUNTIME/'run/mysql.sock'),'--user=root'],env=mysqlenv,input=sql,log='mysql-bootstrap.log')
    secured.write_text('secured\n');secured.chmod(0o600)
    http('/?query=CREATE%20DATABASE%20IF%20NOT%20EXISTS%20opik',PORTS['clickhouse_http'],credentials='opik:'+credentials['clickhouse'],data=b'')
    wait_http('/minio/health/live',PORTS['minio'])
    mc=find(RUNTIME/'images/minio','usr/bin/mc')
    mcenv={'MC_HOST_opik':'http://'+credentials['minio_user']+':'+credentials['minio_password']+'@127.0.0.1:'+str(PORTS['minio']),'MC_CONFIG_DIR':str(RUNTIME/'home/mc')}
    command([mc,'mb','--ignore-existing','opik/public'],env=mcenv,log='minio-bootstrap.log')
    print('Native infrastructure health and isolated DB/bucket bootstrap passed',flush=True)


def align_native_journal_location():
    # Official historical migration 000017 explicitly transforms default.* journals.
    # Repair only journals from this newly initialized native instance; keep rows.
    credentials=json.loads((CONF/'secrets.json').read_text())
    def query(sql):
        return http('/?query='+urllib.parse.quote(sql),PORTS['clickhouse_http'],
                    credentials='opik:'+credentials['clickhouse'],data=b'')[1].decode().strip()
    for name in ['DATABASECHANGELOG','DATABASECHANGELOGLOCK']:
        source=query('EXISTS TABLE opik.'+name)=='1'
        target=query('EXISTS TABLE default.'+name)=='1'
        if source and not target:
            query('RENAME TABLE opik.'+name+' TO default.'+name)
            print('Aligned native Liquibase journal '+name+' with official default database',flush=True)


def migrate():
    entry=json.loads((CONF/'launch.json').read_text())['backend']
    for name in ['db','dbAnalytics']:
        if name=='dbAnalytics':align_native_journal_location()
        print('Running pinned '+name+' migrations',flush=True)
        command(entry['command'][:-2]+[name,'migrate',str(CONF/'backend.yml')],env=entry['env'],timeout=600,log=name+'-migration.log')
    print('MySQL and ClickHouse migrations passed',flush=True)


def start_application():
    for name in ['backend','frontend']:
        if 'RUNNING' not in ctl('status','opik-'+name):print(ctl('start','opik-'+name).strip(),flush=True)
        wait_http('/health-check' if name=='backend' else '/health',PORTS[name],seconds=180)
    print('Native Opik backend and frontend health passed',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['configure','infra','migrate','application','status'])
    phase=parser.parse_args().phase
    if phase=='configure':configure(ROOT)
    elif phase=='infra':start_infrastructure()
    elif phase=='migrate':migrate()
    elif phase=='application':start_application()
    elif phase=='status':print(ctl('status'))
