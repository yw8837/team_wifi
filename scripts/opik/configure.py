"""Generate private loopback configuration for the isolated native Opik instance."""
import copy
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

PORTS={'backend':18080,'backend_admin':18081,'frontend':15173,'mysql':13306,'redis':16379,'zookeeper':12181,'clickhouse_http':18123,'clickhouse_native':19090,'clickhouse_replication':19091,'minio':19000,'minio_console':19001}
REVISION='80b3a887a9cf8daaf61cae01b1d2ee7342e47c75'


def find(root,pattern):
    found=sorted(root.glob(pattern))
    if not found:raise RuntimeError('Missing native artifact '+str(root)+' '+pattern)
    return found[0]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value);path.chmod(0o600)


def configure(root):
    root=Path(root);runtime=root/'.runtime/opik';images=runtime/'images';conf=runtime/'conf';data=runtime/'data'
    os.umask(0o077)
    for name in ['mysql','redis','zookeeper','clickhouse','minio','clickhouse-user-files','clickhouse-format-schemas']:(data/name).mkdir(parents=True,exist_ok=True)
    for name in ['clickhouse','zookeeper']:(runtime/'tmp'/name).mkdir(parents=True,exist_ok=True)
    secretfile=conf/'secrets.json'
    credentials=json.loads(secretfile.read_text()) if secretfile.exists() else {'mysql':secrets.token_urlsafe(30),'redis':secrets.token_urlsafe(30),'clickhouse':secrets.token_urlsafe(30),'minio_user':'opik'+secrets.token_hex(8),'minio_password':secrets.token_urlsafe(30)}
    credentials.setdefault('mysql_root',secrets.token_urlsafe(30))
    write(secretfile,json.dumps(credentials,indent=2)+'\n')
    backend=images/'backend';mysql=images/'mysql';redis=images/'redis';zk=images/'zookeeper';ch=images/'clickhouse';minio=images/'minio'
    java=find(backend,'usr/lib/jvm/*/bin/java')
    zkjava=find(zk,'opt/java/openjdk/bin/java') if (zk/'opt/java/openjdk/bin/java').exists() else java
    mysqlserver=find(mysql,'usr/sbin/mysqld');mysqlclient=find(mysql,'usr/bin/mysql')
    # Use the host glibc; expose only supplemental libraries from the pinned image.
    lib=runtime/'mysql-libs';lib.mkdir(exist_ok=True)
    forbidden=('libc.','libm.','libpthread.','libdl.','librt.','libresolv.','libnss_','ld-linux','libutil.','libanl.')
    for item in (mysql/'usr/lib64').glob('*.so*'):
        if not item.name.startswith(forbidden) and item.is_file():
            target=lib/item.name
            if not target.exists():target.symlink_to(item.resolve())
    mysqlenv={'LD_LIBRARY_PATH':str(lib)+':'+str(mysql/'usr/lib64/mysql/private')}
    message=find(mysql,'usr/share/mysql*/english/errmsg.sys').parent.parent
    plugin=find(mysql,'usr/lib64/mysql/plugin')
    write(conf/'mysql.cnf',f'''[mysqld]
basedir={mysql}/usr
datadir={data}/mysql
socket={runtime}/run/mysql.sock
pid-file={runtime}/run/mysql.pid
port={PORTS['mysql']}
bind-address=127.0.0.1
mysqlx=0
innodb_buffer_pool_size=512M
max_connections=20
performance_schema=OFF
secure-file-priv=NULL
local-infile=0
skip-name-resolve=ON
lc-messages-dir={message}
plugin-dir={plugin}
log-error={runtime}/logs/mysql-error.log
skip-log-bin
tmpdir={runtime}/tmp
''')
    write(conf/'redis.conf',f'''bind 127.0.0.1
protected-mode yes
port {PORTS['redis']}
requirepass {credentials['redis']}
dir {data}/redis
appendonly yes
maxmemory 134217728
maxmemory-policy noeviction
save 60 1
''')
    write(conf/'zoo.cfg',f'''tickTime=2000
dataDir={data}/zookeeper
clientPort={PORTS['zookeeper']}
clientPortAddress=127.0.0.1
maxClientCnxns=20
admin.enableServer=false
autopurge.snapRetainCount=3
autopurge.purgeInterval=1
4lw.commands.whitelist=ruok,srvr
''')
    additional_url=f'https://raw.githubusercontent.com/comet-ml/opik/{REVISION}/deployment/docker-compose/clickhouse_config/additional_config.xml'
    with urllib.request.urlopen(additional_url,timeout=30) as response:additional=ET.fromstring(response.read())
    additional.find('zookeeper/node/host').text='127.0.0.1';additional.find('zookeeper/node/port').text=str(PORTS['zookeeper'])
    replica=additional.find('remote_servers/cluster/shard/replica')
    replica.find('host').text='127.0.0.1';replica.find('port').text=str(PORTS['clickhouse_native']);replica.find('password').text=credentials['clickhouse']
    configuration=ET.Element('clickhouse')
    settings={'http_port':PORTS['clickhouse_http'],'tcp_port':PORTS['clickhouse_native'],'interserver_http_port':PORTS['clickhouse_replication'],'interserver_http_host':'127.0.0.1','listen_host':'127.0.0.1','path':str(data/'clickhouse')+'/',
              'tmp_path':str(runtime/'tmp/clickhouse')+'/','user_files_path':str(data/'clickhouse-user-files')+'/',
              'format_schema_path':str(data/'clickhouse-format-schemas')+'/', 'max_server_memory_usage':2147483648,
              'memory_worker_use_cgroup':0,'max_thread_pool_size':256,'max_io_thread_pool_size':16,'max_io_thread_pool_free_size':8,'background_pool_size':2,'background_schedule_pool_size':4,
              'background_message_broker_schedule_pool_size':1,'background_distributed_schedule_pool_size':1,
              'background_fetches_pool_size':2,'background_move_pool_size':2,'max_connections':100}
    for key,value in settings.items():ET.SubElement(configuration,key).text=str(value)
    interserver=ET.SubElement(configuration,'interserver_http_credentials')
    ET.SubElement(interserver,'user').text='opik'
    ET.SubElement(interserver,'password').text=credentials['clickhouse']
    ET.SubElement(interserver,'allow_empty').text='false'
    logger=ET.SubElement(configuration,'logger')
    for key,value in {'level':'warning','log':str(runtime/'logs/clickhouse.log'),'errorlog':str(runtime/'logs/clickhouse-error.log'),'size':'10M','count':'3'}.items():ET.SubElement(logger,key).text=value
    directories=ET.SubElement(configuration,'user_directories');users_xml=ET.SubElement(directories,'users_xml');ET.SubElement(users_xml,'path').text=str(conf/'clickhouse-users.xml')
    local=ET.SubElement(directories,'local_directory');ET.SubElement(local,'path').text=str(data/'clickhouse/access')+'/'
    merge=ET.SubElement(configuration,'merge_tree')
    for key in ['number_of_free_entries_in_pool_to_execute_mutation','number_of_free_entries_in_pool_to_execute_optimize_entire_partition','number_of_free_entries_in_pool_to_lower_max_size_of_merge']:
        ET.SubElement(merge,key).text='0'
    for child in additional:configuration.append(copy.deepcopy(child))
    write(conf/'clickhouse.xml',ET.tostring(configuration,encoding='unicode'))
    users=ET.Element('clickhouse');profiles=ET.SubElement(users,'profiles');default=ET.SubElement(profiles,'default')
    for key,value in {'max_threads':'2','max_memory_usage':'1073741824','enable_time_time64_type':'1','prefer_localhost_replica':'0','distributed_background_insert_batch':'1','distributed_background_insert_split_batch_on_failure':'1'}.items():ET.SubElement(default,key).text=value
    allusers=ET.SubElement(users,'users')
    for name,password in [('default',credentials['clickhouse']),('opik',credentials['clickhouse'])]:
        user=ET.SubElement(allusers,name);ET.SubElement(user,'password').text=password
        network=ET.SubElement(user,'networks');ET.SubElement(network,'ip').text='127.0.0.1'
        ET.SubElement(user,'profile').text='default';ET.SubElement(user,'quota').text='default';ET.SubElement(user,'access_management').text='1'
    quotas=ET.SubElement(users,'quotas');ET.SubElement(quotas,'default')
    write(conf/'clickhouse-users.xml',ET.tostring(users,encoding='unicode'))
    material=(backend/'opt/opik/config.yml').read_text()
    material=material.replace('      port: ${SERVER_APPLICATION_PORT:-8080}','      port: ${SERVER_APPLICATION_PORT:-8080}\n      bindHost: 127.0.0.1').replace('      port: ${SERVER_ADMIN_PORT:-8081}','      port: ${SERVER_ADMIN_PORT:-8081}\n      bindHost: 127.0.0.1')
    write(conf/'backend.yml',material)
    backendenv={'JAVA_HOME':str(java.parent.parent),'OPIK_VERSION':'2.2.142','STATE_DB_PROTOCOL':'jdbc:mysql://','STATE_DB_URL':f"127.0.0.1:{PORTS['mysql']}/opik?createDatabaseIfNotExist=true&rewriteBatchedStatements=true&connectionTimeZone=UTC&forceConnectionTimeZoneToSession=true",'STATE_DB_DATABASE_NAME':'opik','STATE_DB_USER':'opik','STATE_DB_PASS':credentials['mysql'],
                'ANALYTICS_DB_MIGRATIONS_URL':f"jdbc:clickhouse://127.0.0.1:{PORTS['clickhouse_http']}",'ANALYTICS_DB_MIGRATIONS_USER':'opik','ANALYTICS_DB_MIGRATIONS_PASS':credentials['clickhouse'],
                'ANALYTICS_DB_PROTOCOL':'HTTP','ANALYTICS_DB_HOST':'127.0.0.1','ANALYTICS_DB_PORT':str(PORTS['clickhouse_http']),'ANALYTICS_DB_DATABASE_NAME':'opik','ANALYTICS_DB_USERNAME':'opik','ANALYTICS_DB_PASS':credentials['clickhouse'],
                'REDIS_URL':f"redis://:{credentials['redis']}@127.0.0.1:{PORTS['redis']}/0",'SERVER_APPLICATION_PORT':str(PORTS['backend']),'SERVER_ADMIN_PORT':str(PORTS['backend_admin']),
                'S3_URL':f"http://127.0.0.1:{PORTS['minio']}",'S3_BUCKET':'public','IS_MINIO':'true','AWS_ACCESS_KEY_ID':credentials['minio_user'],'AWS_SECRET_ACCESS_KEY':credentials['minio_password'],'AWS_REGION':'us-east-1','S3_REGION':'us-east-1',
                'AUTH_ENABLED':'false','OPIK_USAGE_REPORT_ENABLED':'false','OPIK_ANALYTICS_ENABLED':'false','OPIK_OTEL_SDK_ENABLED':'false','TOGGLE_OPIK_AI_ENABLED':'false','TOGGLE_GUARDRAILS_ENABLED':'false','TOGGLE_OLLIE_ENABLED':'false','TOGGLE_CUSTOM_CHARTS_ENABLED':'false','OPTIMIZATION_LOGS_ENABLED':'false','PYTHON_EVALUATOR_URL':'http://127.0.0.1:18000',
                'JAVA_TOOL_OPTIONS':f'-XX:ActiveProcessorCount=2 -Xms256m -Xmx1536m -XX:MaxDirectMemorySize=256m -Djava.io.tmpdir={runtime}/tmp -Duser.home={runtime}/home'}
    jar=find(backend,'opt/opik/opik-backend-*.jar')
    musl=find(redis,'lib/ld-musl-*.so.1')
    redisbin=find(redis,'usr/local/bin/redis-server')
    zkscript=find(zk,'apache-zookeeper-*/bin/zkServer.sh')
    chbin=find(ch,'usr/bin/clickhouse')
    miniobin=find(minio,'usr/bin/minio')
    launches={
        'mysql':{'command':[str(mysqlserver),'--defaults-file='+str(conf/'mysql.cnf')],'env':mysqlenv},
        'redis':{'command':[str(musl),'--library-path',str(redis/'lib')+':'+str(redis/'usr/lib'),str(redisbin),str(conf/'redis.conf')]},
        'zookeeper':{'command':['/bin/bash',str(zkscript),'start-foreground',str(conf/'zoo.cfg')],'env':{'JAVA_HOME':str(zkjava.parent.parent),'JVMFLAGS':f'-Xmx384m -XX:ActiveProcessorCount=2 -Djava.io.tmpdir={runtime}/tmp -Duser.home={runtime}/home','JMXDISABLE':'true','ZOO_LOG_DIR':str(runtime/'logs'),'ZOO_LOG4J_PROP':'WARN,CONSOLE'}},
        'clickhouse':{'command':[str(chbin),'server','--config-file='+str(conf/'clickhouse.xml')]},
        'minio':{'command':[str(miniobin),'server',str(data/'minio'),'--address','127.0.0.1:'+str(PORTS['minio']),'--console-address','127.0.0.1:'+str(PORTS['minio_console'])], 'env':{'MINIO_ROOT_USER':credentials['minio_user'],'MINIO_ROOT_PASSWORD':credentials['minio_password'],'GOMEMLIMIT':'256MiB','GOMAXPROCS':'2','MINIO_BROWSER':'off'}},
        'backend':{'command':[str(java),'-Dliquibase.propertySubstitutionEnabled=true','-jar',str(jar),'server',str(conf/'backend.yml')],'env':backendenv,'cwd':str(backend/'opt/opik')},
        'frontend':{'command':[str(root/'.venv/bin/python'),str(root/'scripts/opik/frontend_proxy.py'),str(images/'frontend/usr/share/nginx/html'),str(PORTS['frontend']),str(PORTS['backend'])]},
        'guard':{'command':[str(root/'.venv/bin/python'),str(root/'scripts/opik/memory_guard.py'),str(runtime)]}}
    write(conf/'launch.json',json.dumps(launches,indent=2)+'\n')
    supervisor=f'''[unix_http_server]
file={runtime}/run/supervisor.sock
chmod=0600
[supervisord]
logfile={runtime}/logs/supervisord.log
pidfile={runtime}/run/supervisord.pid
childlogdir={runtime}/logs
nodaemon=false
minfds=1024
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix://{runtime}/run/supervisor.sock
'''
    for index,name in enumerate(launches):
        supervisor+=f'''\n[program:opik-{name}]
command={root}/.venv/bin/python {root}/scripts/opik/launch_component.py {runtime} {name}
directory={runtime}
autostart={'true' if name=='guard' else 'false'}
autorestart=unexpected
startsecs=3
startretries=1
stopasgroup=true
killasgroup=true
priority={10+index*10}
stdout_logfile={runtime}/logs/{name}-stdout.log
stderr_logfile={runtime}/logs/{name}-stderr.log
stdout_logfile_maxbytes=5MB
stderr_logfile_maxbytes=5MB
stdout_logfile_backups=2
stderr_logfile_backups=2
'''
    write(conf/'supervisord.conf',supervisor)
    write(conf/'mysql-tools.json',json.dumps({'server':str(mysqlserver),'client':str(mysqlclient),'env':mysqlenv,'basedir':str(mysql/'usr'),'messages':str(message),'plugin':str(plugin)},indent=2))
    print('Configured private native Opik runtime; secrets omitted',flush=True)


if __name__=='__main__':configure(Path(__file__).resolve().parents[2])
