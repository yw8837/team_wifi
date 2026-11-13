"""Crash-recoverable private file purge coupled to the outer SQLAlchemy transaction.

Quarantine manifests contain only server-generated attachment IDs. Account deletion
commits before bytes are finally unlinked; failed physical cleanup remains private
and durable for startup/hourly retry. Rollback or uncommitted Session.close restores
bytes. Purging inside a SAVEPOINT is intentionally rejected.
"""
import json
import os
from pathlib import Path
import re

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .db import Record, User, uid

ID_PATTERN = re.compile(r'[a-f0-9-]{36}')
MAX_MANIFEST_BYTES = 256*1024


def journal_root(root):
    root = Path(root).resolve()
    path = root/'.purge-journal'
    if path.is_symlink() or path.resolve().parent != root:
        raise OSError('Unsafe private journal location')
    path.mkdir(parents=True, exist_ok=True)
    return path


def paths(root, id):
    if not isinstance(id, str) or not ID_PATTERN.fullmatch(id):
        raise ValueError('Invalid server attachment identifier')
    root = Path(root).resolve()
    result = [root/(id+'.png'), root/(id+'.original')]
    if any(path.is_symlink() or path.resolve().parent != root for path in result):
        raise OSError('Unsafe private attachment location')
    return result


def lock_batch(batch):
    lock = batch/'batch.lock'
    if lock.is_symlink():
        raise OSError('Unsafe private journal lock')
    handle = lock.open('a+b')
    try:
        if not handle.tell():
            handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError:
        handle.close()
        raise


def unlock(handle):
    try:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def read_manifest(batch):
    path = batch/'manifest.json'
    if path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Invalid private journal manifest')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'version', 'ids'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid private journal manifest')
    ids = value['ids']
    if not isinstance(ids, list) or len(ids)>5000 or any(not isinstance(id,str) or not ID_PATTERN.fullmatch(id) for id in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid private journal identifiers')
    return ids


def finish_batch(batch, root, ids, handle, restore_ids=()):
    """Return False on deferred I/O cleanup; never turn a completed DB commit into failure."""
    success = False
    try:
        restore = set(restore_ids)
        for id in ids:
            for original in paths(root,id):
                staged = batch/original.name
                if staged.is_symlink():
                    raise OSError('Unsafe quarantined attachment')
                if staged.exists():
                    if id in restore:
                        os.replace(staged,original)
                    else:
                        staged.unlink()
        (batch/'manifest.json').unlink(missing_ok=True)
        success = True
    except (OSError, ValueError):
        pass
    finally:
        unlock(handle)
    if success:
        try:
            (batch/'batch.lock').unlink(missing_ok=True)
            batch.rmdir()
        except OSError:
            # No original bytes remain in this batch; the next recovery removes controls.
            pass
    return success


def finish_session(session, committed):
    batches = session.info.pop('upload_purge_batches', [])
    for batch,root,ids,handle in batches:
        restored = () if committed else ids
        if not finish_batch(batch,root,ids,handle,restored):
            session.info['upload_cleanup_pending'] = True


def after_commit(session):
    if not session.in_nested_transaction():
        finish_session(session,True)


def after_rollback(session):
    if not session.in_nested_transaction():
        finish_session(session,False)


def after_transaction_end(session,transaction):
    if transaction.parent is None and session.info.get('upload_purge_batches'):
        # Session.close without commit emits transaction_end rather than after_rollback.
        finish_session(session,False)


def stage_file_purge(session, ids, root):
    ids = list(dict.fromkeys(ids))
    if not ids:
        return
    if session.in_nested_transaction():
        raise RuntimeError('Attachment purge requires the outer transaction, not a SAVEPOINT.')
    if not session.in_transaction():
        session.begin()
    root = Path(root).resolve()
    for id in ids:paths(root,id)
    batch = journal_root(root)/uid()
    batch.mkdir()
    handle = lock_batch(batch)
    try:
        manifest = batch/'manifest.json'
        with manifest.open('x',encoding='utf-8') as out:
            json.dump({'version':1,'ids':ids},out,separators=(',',':'))
            out.flush();os.fsync(out.fileno())
        for id in ids:
            for original in paths(root,id):
                if original.is_file():
                    os.replace(original,batch/original.name)
    except Exception:
        finish_batch(batch,root,ids,handle,ids)
        raise
    if not session.info.get('upload_journal_events'):
        event.listen(session,'after_commit',after_commit)
        event.listen(session,'after_rollback',after_rollback)
        event.listen(session,'after_transaction_end',after_transaction_end)
        session.info['upload_journal_events'] = True
    session.info.setdefault('upload_cleanup_pending',False)
    session.info.setdefault('upload_purge_batches',[]).append((batch,root,ids,handle))


def recover_file_journals(db, root=None):
    """Run at startup/hourly; each unlocked batch reauthenticates from a fresh DB session.

    A live process holds an OS lock until its outer DB transaction finishes. A
    crash releases that lock, so recovery uses committed metadata to choose restore
    or permanent removal. No source bytes, account IDs or file names are returned.
    """
    if root is None:
        from .attachments import UPLOAD_ROOT
        root = UPLOAD_ROOT
    root = Path(root).resolve()
    journal = root/'.purge-journal'
    result = {'restored':0,'purged':0,'pending':0}
    if not journal.exists():return result
    if journal.is_symlink() or journal.resolve().parent != root:
        return {**result,'pending':1}
    for batch in journal.iterdir():
        if batch.is_symlink() or not batch.is_dir() or not ID_PATTERN.fullmatch(batch.name):
            result['pending']+=1;continue
        try:
            handle = lock_batch(batch)
        except OSError:
            continue  # An active transaction owns the batch; no recovery race.
        try:
            if not (batch/'manifest.json').exists():
                unlock(handle)
                (batch/'batch.lock').unlink(missing_ok=True);batch.rmdir()
                continue
            ids = read_manifest(batch)
            restore = []
            # A distinct session avoids an old caller snapshot restoring erased bytes.
            with Session(bind=db.get_bind(),expire_on_commit=False) as fresh:
                if fresh.get_bind().dialect.name == 'postgresql':
                    fresh.connection(execution_options={'isolation_level':'READ COMMITTED'})
                for id in ids:
                    item=fresh.get(Record,id)
                    owner=fresh.get(User,item.owner_id) if item and item.kind=='attachment' else None
                    if owner and not owner.deleted:restore.append(id)
            success = finish_batch(batch,root,ids,handle,restore)
            handle = None
            if success:
                result['restored']+=len(restore)
                result['purged']+=len(ids)-len(restore)
            else:result['pending']+=1
        except (OSError,ValueError,json.JSONDecodeError,SQLAlchemyError):
            result['pending']+=1
        finally:
            if handle is not None and not handle.closed:unlock(handle)
    return result


def storage_usage(root):
    """Include quarantined bytes in quotas, tolerating concurrent cleanup moves."""
    root=Path(root).resolve()
    if not root.is_dir():return 0,0
    files=[]
    for path in root.iterdir():
        if path.is_symlink():continue
        if path.is_file():files.append(path)
        elif path.name=='.purge-journal':
            try:batches=list(path.iterdir())
            except FileNotFoundError:continue
            for batch in batches:
                if batch.is_symlink() or not batch.is_dir():continue
                try:children=list(batch.iterdir())
                except FileNotFoundError:continue
                files.extend(child for child in children if child.is_file() and not child.is_symlink())
    count,total=0,0
    for path in files:
        try:size=path.stat().st_size
        except FileNotFoundError:continue
        count+=1;total+=size
    return count,total
