"""Rollback, actual process-crash recovery and post-commit private cleanup retries."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy.exc import IntegrityError

from app import attachments as A, file_journal as J
from app.db import Record, SessionLocal, User, uid
from test_attachments import files, upload


def test_purge_rollback_and_session_close_restore_original_bytes(files):
    c,p,_=files
    item=upload(c,p['buyer']).json()['id']
    before=[path.read_bytes() for path in A.storage_paths(item)]
    for close in [False,True]:
        db=SessionLocal()
        A.purge_user_uploads(db,p['buyer']['id'])
        assert not any(path.exists() for path in A.storage_paths(item))
        assert J.recover_file_journals(db)['restored']==0  # OS lock protects active transaction.
        if close:db.close()
        else:db.rollback();db.close()
        assert [path.read_bytes() for path in A.storage_paths(item)]==before
        with SessionLocal() as fresh:assert fresh.get(Record,item) is not None


def test_database_integrity_failure_restores_valid_upload(files):
    c,p,_=files
    item=upload(c,p['buyer']).json()['id']
    original=A.storage_paths(item)[1].read_bytes()
    with SessionLocal() as db:
        A.purge_user_uploads(db,p['buyer']['id'])
        db.add(User(email='buyer@example.com',nickname='중복 실패',password_hash='synthetic-only'))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
    with SessionLocal() as db:assert db.get(Record,item) is not None
    assert A.storage_paths(item)[1].read_bytes()==original


def test_savepoint_purge_rejected_and_unrelated_savepoint_does_not_finish_outer_purge(files):
    c,p,_=files
    item=upload(c,p['buyer']).json()['id']
    with SessionLocal() as db:
        with db.begin_nested():
            with pytest.raises(RuntimeError):A.purge_user_uploads(db,p['buyer']['id'])
        assert A.storage_paths(item)[0].exists()
        A.purge_user_uploads(db,p['buyer']['id'])
        with db.begin_nested():pass
        assert not A.storage_paths(item)[0].exists()
        assert db.info.get('upload_purge_batches')
        db.rollback()
    assert all(path.exists() for path in A.storage_paths(item))


def test_postcommit_unlink_failure_stays_private_durable_and_retries(files,monkeypatch):
    c,p,_=files
    item=upload(c,p['buyer']).json()['id']
    real_unlink=Path.unlink
    def fail_private_image(path,*args,**kwargs):
        if path.suffix=='.png' and path.parent.parent.name=='.purge-journal':
            raise OSError('synthetic temporary sharing violation')
        return real_unlink(path,*args,**kwargs)
    with SessionLocal() as db:
        A.purge_user_uploads(db,p['buyer']['id'])
        with monkeypatch.context() as patch:
            patch.setattr(Path,'unlink',fail_private_image)
            db.commit()  # Committed account action must not become an apparent DB failure.
        assert db.info['upload_cleanup_pending'] is True
        assert db.get(Record,item) is None
        assert not any(path.exists() for path in A.storage_paths(item))
        assert J.storage_usage(A.UPLOAD_ROOT)[1]>0
        result=J.recover_file_journals(db)
        assert result=={'restored':0,'purged':1,'pending':0}
    assert J.storage_usage(A.UPLOAD_ROOT)==(0,0)


@pytest.mark.parametrize('commit',[False,True])
def test_real_process_crash_recovers_committed_or_rolled_back_state(files,commit):
    c,p,_=files
    item=upload(c,p['buyer']).json()['id']
    original=A.storage_paths(item)[1].read_bytes()
    code='''
import os,sys
from pathlib import Path
from app import attachments as A, file_journal as J
from app.db import SessionLocal
A.UPLOAD_ROOT=Path(sys.argv[1])
if sys.argv[3]=='commit':
    J.after_commit=lambda session:os._exit(24)
with SessionLocal() as db:
    A.purge_user_uploads(db,sys.argv[2])
    if sys.argv[3]=='commit':db.commit()
    else:
        db.flush()
        os._exit(23)
'''
    root=Path(__file__).resolve().parents[2]
    process=subprocess.run([sys.executable,'-c',code,str(A.UPLOAD_ROOT),p['buyer']['id'],'commit' if commit else 'rollback'],
                           cwd=root,env=os.environ.copy(),capture_output=True,timeout=60)
    assert process.returncode==(24 if commit else 23),process.stderr.decode(errors='replace')
    assert not any(path.exists() for path in A.storage_paths(item))
    with SessionLocal() as db:
        result=J.recover_file_journals(db)
        assert result['pending']==0
        assert result['purged' if commit else 'restored']==1
        assert (db.get(Record,item) is None)==commit
    if commit:assert not any(path.exists() for path in A.storage_paths(item))
    else:assert A.storage_paths(item)[1].read_bytes()==original


def test_invalid_manifest_cannot_escape_storage_root(files):
    _,_,_=files
    journal=J.journal_root(A.UPLOAD_ROOT)
    batch=journal/uid();batch.mkdir()
    (batch/'manifest.json').write_text(json.dumps({'version':1,'ids':['../../outside']}),encoding='utf-8')
    outside=A.UPLOAD_ROOT.parent/'outside.txt';outside.write_text('KEEP-OUTSIDE',encoding='utf-8')
    with SessionLocal() as db:
        result=J.recover_file_journals(db)
        assert result['pending']==1
    assert outside.read_text(encoding='utf-8')=='KEEP-OUTSIDE'
