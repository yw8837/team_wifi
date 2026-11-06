"""Start a disposable loopback public-mode API with real PostgreSQL guards.

Only synthetic accounts are created. No remote credentials are read. The
returned runtime keeps PID/command receipts for an explicit, verified stop.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    if ROOT not in runtime.parents or runtime.exists():
        raise SystemExit('Use a new disposable runtime below the active workspace.')
    pg = args.pg_bin.resolve(strict=True)
    for port in (55441, 18180, 18181):
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', port))
    runtime.mkdir(parents=True)
    password = secrets.token_urlsafe(32)
    password_file = runtime / 'pg-password.txt'
    password_file.write_text(password)
    password_file.chmod(0o600)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    data = runtime / 'database'
    def database_command(name, *values):
        with (runtime / (name+'.log')).open('a') as log:
            subprocess.run([str(pg / (name+'.exe' if os.name == 'nt' else name)), *map(str, values)],
                           cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                           creationflags=flags, timeout=60, check=True)
    database_command('initdb', '-D', data, '-U', 'community_qa', '-A', 'scram-sha-256',
                     '--pwfile', password_file, '--encoding=UTF8', '--locale=C')
    database_command('pg_ctl', '-D', data, '-l', runtime / 'postgres.log', '-o',
                     '-h 127.0.0.1 -p 55441 -c shared_buffers=32MB -c max_connections=25', '-w', 'start')
    values = dict(MODU_ENV='public_release', PUBLIC_ORIGIN='https://community-qa.example.test',
        DATABASE_URL=f'postgresql+psycopg://community_qa:{password}@127.0.0.1:55441/postgres',
        RATE_LIMIT_SECRET=secrets.token_urlsafe(32), SUPPORT_EMAIL='qa@example.test',
        HOSTING_LOCATION='독립 로컬 검증 환경', DATABASE_LOCATION='독립 로컬 PostgreSQL',
        RUNTIME_DIR=str(runtime / 'app'), ASSISTANT_MODEL_ENABLED='false', ASSISTANT_OPIK_ENABLED='false')
    environment = runtime / 'api-environment.json'
    environment.write_text(json.dumps(values), encoding='utf-8')
    environment.chmod(0o600)
    os.environ.update(values)
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.db import SessionLocal, User, init_db
    from app.security import passwords
    init_db()
    with SessionLocal() as db:
        for name in ('reader', 'other', 'operator'):
            db.add(User(email=f'{name}@example.com', nickname=f'화면검증{name}',
                        password_hash=passwords.hash('Community-QA-only-2026!'), is_admin=name == 'operator'))
        db.commit()
    log = (runtime / 'api.log').open('a')
    command = [sys.executable, str(ROOT / 'scripts/serve-deployment.py'), '--environment',
               str(environment), '--host', '127.0.0.1', '--port', '18180']
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=log, creationflags=flags)
    log.close()
    (runtime / 'receipt.json').write_text(json.dumps({'api_pid': process.pid, 'api_command': command,
        'database_directory': str(data), 'database_port': 55441, 'api_url': 'http://127.0.0.1:18180',
        'synthetic_only': True, 'guards_disabled': False}, indent=2), encoding='utf-8')
    for _ in range(30):
        if process.poll() is not None:
            raise SystemExit('API exited; inspect the private runtime log.')
        try:
            with urllib.request.urlopen('http://127.0.0.1:18180/api/health', timeout=1) as response:
                if response.status == 200:
                    print('Loopback QA API ready; real authentication and PostgreSQL rate limits enabled.')
                    return
        except OSError:
            time.sleep(1)
    raise SystemExit('API health deadline exceeded; retained receipt identifies owned processes.')


if __name__ == '__main__':
    main()
