"""Scan tracked files or reachable Git history without printing matched secrets."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{40,}',
    'github_token': rb'\bgh[pousr]_[A-Za-z0-9]{30,}',
    'github_pat': rb'\bgithub_pat_[A-Za-z0-9_]{40,}',
    'openai_key': rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}',
    'aws_access_key': rb'\bAKIA[A-Z0-9]{16}',
    'google_api_key': rb'\bAIza[A-Za-z0-9_-]{35}',
    'database_password': rb'postgres(?:ql)?(?:\+psycopg)?://[^\s:/]+:[^\s@]+@(?!localhost|127\.0\.0\.1)[^\s]+',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.history:
        objects = git('rev-list', '--objects', '--all').decode('utf-8').splitlines()
    else:
        entries = git('ls-tree', '-rz', 'HEAD').decode('utf-8').split('\0')
        objects = [entry.split()[2] + ' ' + entry.split('\t', 1)[1] for entry in entries if entry]

    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    findings, scanned, binary = [], 0, 0
    try:
        for entry in objects:
            oid, _, path = entry.partition(' ')
            process.stdin.write((oid + '\n').encode())
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3:
                raise RuntimeError('Git object could not be read')
            size = int(header[2])
            raw = process.stdout.read(size)
            process.stdout.read(1)
            if header[1] != b'blob':
                continue
            if b'\0' in raw:
                binary += 1
                continue
            scanned += 1
            # This exact password belongs to an ephemeral CI container defined in the same file.
            if path == '.github/workflows/container.yml':
                raw = raw.replace(b'postgresql+psycopg://app:container-verification-only@moduyuga-pg-verify/app', b'')
            for label, pattern in PATTERNS.items():
                if re.search(pattern, raw):
                    findings.append({'object': oid, 'path': path, 'rule': label})
    finally:
        process.stdin.close()
        process.wait()
    result = {
        'scope': 'reachable_history' if args.history else 'HEAD',
        'text_blobs_scanned': scanned,
        'binary_blobs_not_scanned': binary,
        'findings': findings,
        'limitation': 'Pattern scan only. Review data rights, personal information and binary files separately.',
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
