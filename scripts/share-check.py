"""Fail before sharing accidentally staged secrets, raw data, or private local paths."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'], cwd=ROOT).decode('utf-8').split('\0')
bad = []
checked = 0
patterns = [re.compile(p) for p in [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'\bgh[pousr]_[A-Za-z0-9]{30,}',
              r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}', r'\bAKIA[A-Z0-9]{16}', r'(?i)[A-Z]:[/\\]Users[/\\](?!Public[/\\])[^/\\\s]+']]
for name in filter(None, names):
    p = Path(name)
    if ('runtime/' in name or name.startswith('data/') and name != 'data/README.md' or p.suffix in {'.db', '.jks', '.keystore', '.p12', '.pem'}
        or p.name.startswith('.env') and not p.name.endswith('.example')
        or p.name in {'company_source_extract.json', 'materials_inventory.json', 'requirements_source.json'}
        or p.name.startswith('requirements_traceability.')):
        bad.append(name+': private file staged')
        continue
    raw = subprocess.check_output(['git', 'show', ':'+name], cwd=ROOT)
    if b'\0' in raw:
        continue
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        continue
    checked += 1
    for index, pattern in enumerate(patterns):
        if pattern.search(text):
            bad.append(f'{name}: sensitive pattern {index+1}; value redacted')
if bad:
    print('\n'.join(bad))
    raise SystemExit(1)
print(f'SHARE_CHECK_PASS: {checked} staged text files; no matched secret/private path or forbidden raw files. Manual review still required.')
