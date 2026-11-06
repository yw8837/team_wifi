"""Independent scheduled retention jobs; failures never log member data."""
import asyncio
from contextlib import suppress
import logging

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from . import config
from .db import SessionLocal


def _jobs():
    from .assistant import cleanup_expired_conversations
    from .attachments import cleanup_orphans
    from .file_journal import recover_file_journals

    jobs = [('attachment_journal', recover_file_journals),
            ('attachment_orphans', cleanup_orphans)]
    if config.PUBLIC_RELEASE:
        jobs.append(('assistant_retention', cleanup_expired_conversations))
    return jobs


def _run_transaction(work):
    # Each job owns its transaction. SQLite must lock before metadata reads,
    # matching request writes so orphan cleanup cannot race an attachment bind.
    with SessionLocal() as db:
        try:
            if db.bind.dialect.name == 'sqlite':
                db.execute(text('BEGIN IMMEDIATE'))
            result = work(db)
            db.commit()
            return result
        except BaseException:
            with suppress(Exception):
                db.rollback()
            raise


async def _finish_running_job(work):
    # A cancelled await cannot stop a synchronous SQL transaction. Drain this
    # worker before propagating cancellation, leaving no unobserved write behind.
    worker = asyncio.create_task(run_in_threadpool(_run_transaction, work))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        with suppress(Exception, asyncio.CancelledError):
            await worker
        raise


async def cleanup_once():
    logger = logging.getLogger(__name__)
    for name, work in _jobs():
        try:
            result = await _finish_running_job(work)
            if name == 'attachment_journal' and result.get('pending', 0):
                logger.warning('attachment_journal_cleanup_pending')
        except asyncio.CancelledError:
            raise
        except Exception:
            # Job names are server-owned constants. Never log SQL, connection
            # URLs, original exception text, file names or member content.
            logger.warning(name+'_cleanup_failed')


async def conversation_cleanup_loop():
    while True:
        await cleanup_once()
        await asyncio.sleep(3600)
