"""Read-only exported-snapshot backup; restore only into a new owned localhost DB.

All member bytes, credentials and raw diagnostics stay in an ACL-restricted,
gitignored directory. Standard output and the separate result contain safe check
names, hashes and times only. Never restores into the source connection.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import traceback
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT=Path(__file__).resolve().parents[1]
FLAGS=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
PSHOST=shutil.which('pwsh') or shutil.which('powershell')


class BackupFailure(Exception):pass


def run(command,log,env=None,timeout=180):
    with log.open('ab') as output:
        result=subprocess.run([str(value) for value in command],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                              stdout=output,stderr=output,timeout=timeout,creationflags=FLAGS)
    if result.returncode:raise BackupFailure('private_command_failed')


def private_directory(path):
    if os.name!='nt':raise BackupFailure('Windows_ACL_workflow_requires_explicit_port')
    path.mkdir(parents=True,exist_ok=False)
    sid=subprocess.check_output([PSHOST,'-NoProfile','-NonInteractive','-Command',
        '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],cwd=ROOT,text=True,creationflags=FLAGS).strip()
    result=subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F',
                          '*S-1-5-18:(OI)(CI)F'],cwd=ROOT,capture_output=True,creationflags=FLAGS)
    if result.returncode:raise BackupFailure('private_ACL_failed')
    if subprocess.run(['git','check-ignore','--quiet','--',str(path)],cwd=ROOT).returncode:
        raise BackupFailure('private_directory_not_gitignored')
    return sid


def verify_acl(path,sid):
    script='''
$allowed=@($env:BACKUP_OWNER_SID,'S-1-5-18')
$items=@(Get-Item -LiteralPath $env:BACKUP_ACL_PATH -Force)+@(Get-ChildItem -LiteralPath $env:BACKUP_ACL_PATH -Force -Recurse -ErrorAction Stop)
$valid=$true
foreach($item in $items){
 $acl=Get-Acl -LiteralPath $item.FullName -ErrorAction Stop
 $ownerFound=$false
 foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($rule.IdentityReference.Value -eq $env:BACKUP_OWNER_SID){$ownerFound=$true}
  if($rule.IdentityReference.Value -notin $allowed -or $rule.AccessControlType.ToString() -ne 'Allow'){$valid=$false}
 }
 if(-not $ownerFound){$valid=$false}
}
@{ok=$valid}|ConvertTo-Json -Compress
'''
    result=subprocess.run([PSHOST,'-NoProfile','-NonInteractive','-Command',script],cwd=ROOT,
        env={**os.environ,'BACKUP_OWNER_SID':sid,'BACKUP_ACL_PATH':str(path)},capture_output=True,
        timeout=60,creationflags=FLAGS)
    if result.returncode:
        (path/'acl-diagnostic.log').write_bytes(result.stdout+result.stderr)
        raise BackupFailure('private_ACL_verification_failed')
    if not json.loads(result.stdout.decode('utf-8-sig')).get('ok'):raise BackupFailure('private_ACL_verification_failed')


def credentials():
    for relative in ['.runtime/server-private/elice-api.json','.runtime/server-private/render-api.json']:
        path=ROOT/relative
        if not path.is_file():continue
        found=[]
        def visit(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key.upper()=='DATABASE_URL' and isinstance(item,str):found.append(item)
                if value.get('key')=='DATABASE_URL' and isinstance(value.get('value'),str):found.append(value['value'])
                for item in value.values():visit(item)
            elif isinstance(value,list):
                for item in value:visit(item)
        visit(json.loads(path.read_text(encoding='utf-8-sig')))
        found=list(dict.fromkeys(found))
        if len(found)==1:
            url=found[0].replace('postgresql+psycopg://','postgresql://',1)
            params=conninfo_to_dict(url)
            if params.get('host') in ('127.0.0.1','localhost','::1'):
                raise BackupFailure('source_credential_must_not_be_QA_or_restore_cluster')
            return params
        if len(found)>1:raise BackupFailure('ambiguous_source_credentials')
    raise BackupFailure('source_database_credential_not_found')


def database_environment(params,password_file,readonly=False):
    fields={'host':'PGHOST','port':'PGPORT','dbname':'PGDATABASE','user':'PGUSER','sslmode':'PGSSLMODE',
            'sslrootcert':'PGSSLROOTCERT','sslcert':'PGSSLCERT','sslkey':'PGSSLKEY','channel_binding':'PGCHANNELBINDING'}
    env={key:value for key,value in os.environ.items() if not key.startswith('PG')}
    env.update({variable:str(params[name]) for name,variable in fields.items() if params.get(name)})
    def escape(value):
        value=str(value)
        if '\n' in value or '\r' in value:raise BackupFailure('unsupported_password_encoding')
        return value.replace('\\','\\\\').replace(':','\\:')
    password_file.write_text(':'.join(escape(params.get(key,'5432' if key=='port' else ''))
        for key in ['host','port','dbname','user','password'])+'\n',encoding='utf-8')
    env.update(PGPASSFILE=str(password_file),PGCONNECT_TIMEOUT='15',PGAPPNAME='moduyuga_backup_verification',
        PGOPTIONS='-c statement_timeout=60000 -c lock_timeout=5000'+(' -c default_transaction_read_only=on' if readonly else ''))
    return env


def begin_readonly(connection):
    connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    connection.execute("SET LOCAL statement_timeout='60s'")
    connection.execute("SET LOCAL lock_timeout='5s'")
    connection.execute("SET LOCAL timezone='UTC'")
    connection.execute("SET LOCAL search_path=pg_catalog")
    if connection.execute('SHOW transaction_read_only').fetchone()[0]!='on':raise BackupFailure('read_only_transaction_missing')
    if connection.execute('SHOW transaction_isolation').fetchone()[0]!='repeatable read':raise BackupFailure('repeatable_read_missing')


def metadata(connection):
    tables=connection.execute("""SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','m')
        ORDER BY 1,2""").fetchall()
    constraints=connection.execute("""SELECT n.nspname,t.relname,c.conname,c.contype,pg_get_constraintdef(c.oid,true),c.convalidated,
        ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum,ord)
              JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.ord)
        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' ORDER BY 1,2,3""").fetchall()
    indexes=connection.execute("""SELECT n.nspname,t.relname,i.relname,pg_get_indexdef(i.oid),x.indisunique,x.indisvalid,x.indisready
        FROM pg_index x JOIN pg_class t ON t.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
        ORDER BY 1,2,3""").fetchall()
    fingerprints={}
    for number,(schema,table) in enumerate(tables):
        count,total,xor=0,0,0
        with connection.cursor(name='backup_verify_'+str(number)) as cursor:
            cursor.execute(sql.SQL('SELECT pg_catalog.row_to_json(t)::text FROM {} AS t').format(sql.Identifier(schema,table)))
            for (row,) in cursor:
                digest=int.from_bytes(hashlib.sha256(row.encode('utf-8')).digest(),'big')
                count+=1;total=(total+digest)%(1<<256);xor^=digest
        fingerprints[schema+'.'+table]={'rows':count,'multiset_sha256_sum':f'{total:064x}','multiset_sha256_xor':f'{xor:064x}'}
    return {'tables':fingerprints,'constraints':constraints,'indexes':indexes}


def constraint_probes(connection,port):
    if connection.info.host!='127.0.0.1' or connection.info.port!=port or connection.info.dbname!='restore_verify':
        raise BackupFailure('restore_only_constraint_probe_guard')
    result=[]
    user_id=str(uuid.uuid4());email='restore-'+user_id+'@example.invalid'
    def insert_user(id,value):
        connection.execute('INSERT INTO public.users(id,email,password_hash,nickname,is_admin,deleted,seller_status,points,marketing,created) VALUES(%s,%s,%s,%s,false,false,NULL,0,false,0)',
                           (id,value,'synthetic-restore-probe','restore probe'))
    def violation(work,error,label):
        try:
            with connection.transaction():work()
        except error:result.append(label)
        else:raise BackupFailure('restored_constraint_not_enforced')
    with connection.transaction(force_rollback=True):
        insert_user(user_id,email)
        violation(lambda:insert_user(user_id,'other-'+email),psycopg.errors.UniqueViolation,'restored_user_primary_key_enforced')
        violation(lambda:insert_user(str(uuid.uuid4()),email),psycopg.errors.UniqueViolation,'restored_user_email_unique_enforced')
        violation(lambda:connection.execute('INSERT INTO public.tokens(digest,user_id,kind,expires) VALUES(%s,%s,%s,0)',
                    (secrets.token_hex(32),str(uuid.uuid4()),'restore_probe')),psycopg.errors.ForeignKeyViolation,'restored_token_foreign_key_enforced')
        def record():
            connection.execute("INSERT INTO public.records(id,kind,owner_id,parent_id,unique_key,status,data,counter,capacity,ends,revision,created) VALUES(%s,'restore_probe',%s,NULL,'same-key','active','{}'::json,0,0,0,1,0)",
                               (str(uuid.uuid4()),user_id))
        record()
        violation(record,psycopg.errors.UniqueViolation,'restored_record_composite_unique_enforced')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin',type=Path,default=ROOT/'artifacts/beta/runtime/pgsql/bin')
    parser.add_argument('--port',type=int,default=55445)
    args=parser.parse_args()
    if args.port in (55441,55443,5432) or not 1024<=args.port<=65535:raise SystemExit('Choose a new owned local restore port.')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',args.port))==0:raise SystemExit('Restore port is already occupied; no existing process is touched.')
    output=ROOT/'artifacts/community-completion-20261106'
    private=output/('backup-private-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3))
    pg=args.pg_bin.resolve();checks=[];source=target=None;started=False;secured=False;status='failed';stage='private_storage'
    proof={'started_at':datetime.now(timezone.utc).isoformat(),'production_source_write':False,'restore_port':args.port,
           'source_data_or_credentials_in_result':False,'private_directory':private.relative_to(ROOT).as_posix(),
           'scope_limitations':['Windows localhost restore; production cutover and cross-OS default collation equivalence are not claimed.']}
    try:
        if not pg.is_relative_to(ROOT) or not private.is_relative_to(ROOT):raise BackupFailure('workspace_path_guard')
        sid=private_directory(private);secured=True;verify_acl(private,sid);checks.append('private_user_SYSTEM_ACL_and_gitignore_verified_before_data')
        params=credentials();params.setdefault('sslmode','require')
        stage='readonly_snapshot'
        source=psycopg.connect(**{**params,'connect_timeout':15,'application_name':'moduyuga_readonly_backup_snapshot'},autocommit=True)
        begin_readonly(source)
        snapshot=source.execute('SELECT pg_export_snapshot()').fetchone()[0]
        checks.append('source_readonly_repeatable_exported_snapshot')
        source_meta=metadata(source)
        if not all('public.'+table in source_meta['tables'] for table in ['users','records','tokens','rate_buckets']):
            raise BackupFailure('source_core_schema_missing')
        checks.append('source_core_schema_verified_without_writes')
        dump=private/'source-snapshot.dump'
        source_env=database_environment(params,private/'source.pgpass',readonly=True)
        stage='snapshot_dump'
        run([pg/'pg_dump.exe','--format=custom','--no-owner','--no-privileges','--snapshot='+snapshot,'--file',dump],
            private/'source-command.log',source_env)
        source.execute('ROLLBACK');source.close();source=None
        checks.append('pg_dump_uses_same_exported_source_snapshot')
        proof['dump_sha256']=hashlib.file_digest(dump.open('rb'),'sha256').hexdigest()
        stage='owned_local_restore'
        local_password=secrets.token_urlsafe(32);password_file=private/'local-init-password.txt';password_file.write_text(local_password,encoding='utf-8')
        data=private/'restore-data'
        run([pg/'initdb.exe','-D',data,'-U','backup_restore','-A','scram-sha-256','--pwfile',password_file,'--encoding=UTF8','--locale=C'],private/'local-command.log')
        # Reset new initdb files to the already restricted parent's inherited ACL.
        run(['icacls',data,'/reset','/T','/C','/Q'],private/'acl-command.log')
        verify_acl(private,sid)
        run([pg/'pg_ctl.exe','-D',data,'-l',private/'restore-postgres.log','-o',
            '-h 127.0.0.1 -p '+str(args.port)+' -c shared_buffers=32MB -c max_connections=10','-w','start'],private/'local-command.log')
        started=True
        local={'host':'127.0.0.1','port':str(args.port),'dbname':'postgres','user':'backup_restore','password':local_password,'sslmode':'disable'}
        restore_env=database_environment(local,private/'local.pgpass')
        run([pg/'createdb.exe','restore_verify'],private/'local-command.log',restore_env)
        local['dbname']='restore_verify';restore_env=database_environment(local,private/'local.pgpass')
        run([pg/'pg_restore.exe','--exit-on-error','--no-owner','--no-privileges','--dbname=restore_verify',dump],private/'restore-command.log',restore_env)
        checks.append('restore_only_to_new_localhost_SCRAM_cluster')
        target=psycopg.connect(**local,autocommit=True,connect_timeout=10)
        begin_readonly(target);restored_meta=metadata(target);target.execute('ROLLBACK')
        if source_meta!=restored_meta:raise BackupFailure('same_snapshot_restore_metadata_or_data_mismatch')
        checks.extend(['same_snapshot_all_table_counts_match','all_table_row_multiset_fingerprints_match',
                       'all_restored_constraint_definitions_and_validation_match','all_restored_index_definitions_and_validity_match'])
        stage='restored_constraint_probes'
        checks.extend(constraint_probes(target,args.port))
        begin_readonly(target);after_probes=metadata(target);target.execute('ROLLBACK')
        if after_probes!=restored_meta:raise BackupFailure('constraint_probe_rollback_did_not_preserve_restored_data')
        checks.append('restored_constraint_probe_writes_fully_rolled_back')
        (private/'snapshot-metadata.json').write_text(json.dumps({'source':source_meta,'restore':restored_meta},ensure_ascii=False,indent=2),encoding='utf-8')
        verify_acl(private,sid);checks.append('all_private_backup_restore_files_remain_ACL_restricted')
        status='pass'
    except Exception as exc:
        proof.update(error_type=type(exc).__name__,failed_stage=stage)
        if isinstance(exc,BackupFailure):proof['error_code']=str(exc)
        if secured:(private/'private-failure.log').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        for connection in [source,target]:
            if connection is not None:
                try:connection.close()
                except Exception:pass
        if started:
            try:
                run([pg/'pg_ctl.exe','-D',private/'restore-data','-m','fast','-w','stop'],private/'local-command.log')
                checks.append('owned_restore_PostgreSQL_stopped_normally')
            except Exception:
                status='failed';proof['failed_stage']='local_cluster_stop'
        if secured:
            try:
                for name in ['source.pgpass','local.pgpass','local-init-password.txt']:
                    (private/name).unlink(missing_ok=True)
                checks.append('temporary_libpq_and_init_password_files_removed')
            except OSError:
                status='failed';proof['failed_stage']='temporary_credential_cleanup'
        proof.update(status=status,checks=checks,completed_at=datetime.now(timezone.utc).isoformat(),
                     script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        output.mkdir(parents=True,exist_ok=True)
        (output/'backup-verification-results.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BACKUP_RESTORE_'+status.upper()+': '+str(len(checks))+' safe checks; see backup-verification-results.json')
    return 0 if status=='pass' else 1


if __name__=='__main__':raise SystemExit(main())
