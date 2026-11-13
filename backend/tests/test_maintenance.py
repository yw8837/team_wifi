"""Independent maintenance transactions, retention failure isolation and shutdown."""
import asyncio
from threading import Event
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app import assistant, attachments, config, file_journal, maintenance
from app.db import Base, Record, SessionLocal, User, engine, now


@pytest.fixture
def cleanup_database():
    # Tests use conftest's disposable DB; no live app lifespan is running here.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        owner = User(email='maintenance@example.invalid',nickname='합성 정리 계정',password_hash='synthetic-only')
        db.add(owner);db.flush()
        expired = Record(kind=assistant.CHAT,owner_id=owner.id,ends=now()-1,data={'messages':['EXPIRED-PRIVATE-TEXT']})
        active = Record(kind=assistant.CHAT,owner_id=owner.id,ends=now()+86400,data={'messages':['KEEP-ACTIVE-TEXT']})
        unrelated = Record(kind='unrelated',owner_id=owner.id,ends=0,data={'body':'KEEP-UNRELATED-TEXT'})
        db.add_all([expired,active,unrelated]);db.commit()
        return {'owner':owner.id,'expired':expired.id,'active':active.id,'unrelated':unrelated.id}


@pytest.mark.parametrize('failures', [(),('attachment_journal',),('attachment_orphans',),
    ('attachment_journal','attachment_orphans'),('assistant_retention',)])
def test_jobs_have_separate_commit_rollback_and_later_retention_runs(cleanup_database,monkeypatch,caplog,failures):
    ids=cleanup_database
    monkeypatch.setattr(config,'PUBLIC_RELEASE',True)
    original_retention=assistant.cleanup_expired_conversations
    calls=[];sessions=[]
    def work(name,db):
        calls.append(name);sessions.append(db)
        db.add(Record(kind='maintenance_probe',owner_id=ids['owner'],unique_key=name,data={}))
        db.flush()
        result=original_retention(db) if name=='assistant_retention' else {'pending':0}
        if name in failures:raise OSError('SYNTHETIC-PRIVATE-TEXT database URL must not be logged')
        return result
    monkeypatch.setattr(file_journal,'recover_file_journals',lambda db:work('attachment_journal',db))
    monkeypatch.setattr(attachments,'cleanup_orphans',lambda db:work('attachment_orphans',db))
    monkeypatch.setattr(assistant,'cleanup_expired_conversations',lambda db:work('assistant_retention',db))
    asyncio.run(maintenance.cleanup_once())
    assert calls==['attachment_journal','attachment_orphans','assistant_retention']
    assert len({id(db) for db in sessions})==3
    assert all(db.get_transaction() is None for db in sessions)
    with SessionLocal() as db:
        persisted=set(db.scalars(select(Record.unique_key).where(Record.kind=='maintenance_probe')))
        assert persisted==set(calls)-set(failures)
        assert (db.get(Record,ids['expired']) is None)==('assistant_retention' not in failures)
        assert db.get(Record,ids['active']).data['messages']==['KEEP-ACTIVE-TEXT']
        assert db.get(Record,ids['unrelated']).data['body']=='KEEP-UNRELATED-TEXT'
    assert sorted(record.message for record in caplog.records)==sorted(name+'_cleanup_failed' for name in failures)
    assert 'SYNTHETIC-PRIVATE-TEXT' not in caplog.text


def test_pending_file_journal_is_observable_without_stopping_retention(cleanup_database,monkeypatch,caplog):
    ids=cleanup_database
    monkeypatch.setattr(config,'PUBLIC_RELEASE',True)
    monkeypatch.setattr(file_journal,'recover_file_journals',lambda db:{'restored':0,'purged':0,'pending':1})
    monkeypatch.setattr(attachments,'cleanup_orphans',lambda db:0)
    asyncio.run(maintenance.cleanup_once())
    assert [record.message for record in caplog.records]==['attachment_journal_cleanup_pending']
    with SessionLocal() as db:assert db.get(Record,ids['expired']) is None


def test_non_public_mode_does_not_delete_assistant_content(cleanup_database,monkeypatch):
    ids=cleanup_database
    monkeypatch.setattr(config,'PUBLIC_RELEASE',False)
    monkeypatch.setattr(file_journal,'recover_file_journals',lambda db:{'pending':0})
    monkeypatch.setattr(attachments,'cleanup_orphans',lambda db:0)
    retention=Mock(side_effect=AssertionError('retention must remain public-release-only'))
    monkeypatch.setattr(assistant,'cleanup_expired_conversations',retention)
    asyncio.run(maintenance.cleanup_once())
    retention.assert_not_called()
    with SessionLocal() as db:assert db.get(Record,ids['expired']) is not None


def test_cancelled_job_rolls_back_and_does_not_start_next_job(cleanup_database,monkeypatch,caplog):
    ids=cleanup_database;calls=[]
    def cancel(db):
        calls.append('first')
        db.add(Record(kind='maintenance_probe',owner_id=ids['owner'],data={}))
        db.flush()
        raise asyncio.CancelledError()
    monkeypatch.setattr(maintenance,'_jobs',lambda:[('first',cancel),('second',lambda db:calls.append('second'))])
    with pytest.raises(asyncio.CancelledError):asyncio.run(maintenance.cleanup_once())
    assert calls==['first'] and not caplog.records
    with SessionLocal() as db:assert not db.scalar(select(Record.id).where(Record.kind=='maintenance_probe'))


def test_shutdown_drains_running_transaction_and_skips_later_jobs(cleanup_database,monkeypatch,caplog):
    ids=cleanup_database;started=Event();release=Event();finished=Event();calls=[]
    def slow(db):
        calls.append('first')
        db.add(Record(kind='maintenance_probe',owner_id=ids['owner'],unique_key='drained',data={}))
        db.flush();started.set()
        assert release.wait(10),'test must release its bounded synthetic worker'
        finished.set()
    monkeypatch.setattr(maintenance,'_jobs',lambda:[('first',slow),('second',lambda db:calls.append('second'))])
    async def scenario():
        task=asyncio.create_task(maintenance.cleanup_once())
        assert await asyncio.to_thread(started.wait,5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):await asyncio.wait_for(task,5)
    try:asyncio.run(scenario())
    finally:release.set()
    assert finished.is_set() and calls==['first'] and not caplog.records
    with SessionLocal() as db:
        assert db.scalar(select(Record.id).where(Record.kind=='maintenance_probe',Record.unique_key=='drained'))


def test_idle_loop_cancellation_is_not_logged_as_failure(monkeypatch,caplog):
    sleeping=asyncio.Event();never=asyncio.Event();cycles=[];intervals=[]
    async def cycle():cycles.append('cycle')
    async def sleep(seconds):
        intervals.append(seconds);sleeping.set();await never.wait()
    monkeypatch.setattr(maintenance,'cleanup_once',cycle)
    monkeypatch.setattr(maintenance.asyncio,'sleep',sleep)
    async def scenario():
        task=asyncio.create_task(maintenance.conversation_cleanup_loop())
        await asyncio.wait_for(sleeping.wait(),2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(scenario())
    assert cycles==['cycle'] and intervals==[3600] and not caplog.records
