"""Fetch reviewed seller pages, then optionally synchronize their public facts."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--environment', type=Path)
parser.add_argument('--apply', action='store_true')
parser.add_argument('--retire-demo', action='store_true')
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
if args.apply and not args.environment:
    parser.error('--apply requires --environment')
if args.environment:
    os.environ.update(json.loads(args.environment.read_text(encoding='utf-8-sig')))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import external_groupbuys
from app.db import SessionLocal

entries, failures = [], []
for source in external_groupbuys.SOURCES:
    try:
        entries.append(external_groupbuys.fetch(source))
    except Exception as error:
        failures.append({'source_id': source['id'], 'error': type(error).__name__})
receipt = {'entries': entries, 'failures': failures, 'stored': 0, 'demo_changes': 0}
if args.apply and entries:
    with SessionLocal.begin() as db:
        receipt['stored'] = external_groupbuys.store(db, entries)
        if args.retire_demo:
            receipt['demo_changes'] = external_groupbuys.retire_demo_listings(db)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'collected': len(entries), 'failed': len(failures), 'stored': receipt['stored'],
                  'demo_changes': receipt['demo_changes']}))
if failures:
    raise SystemExit(1)
