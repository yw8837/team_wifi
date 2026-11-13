"""Fetch reviewed seller pages, then optionally synchronize their public facts."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--environment', type=Path)
parser.add_argument('--apply', action='store_true')
parser.add_argument('--retire-demo', action='store_true')
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--interval-seconds', type=int, default=0)
parser.add_argument('--daily-midnight', action='store_true', help='Run at 00:00 Asia/Seoul, including startup recovery')
parser.add_argument('--discover', action='store_true', help='Discover new products on reviewed seller storefronts')
args = parser.parse_args()
if args.daily_midnight and args.interval_seconds:
    parser.error('Choose midnight scheduling or an interval')
if args.interval_seconds and not 3600 <= args.interval_seconds <= 86400:
    parser.error('Refresh interval must be between one hour and one day')
if (args.interval_seconds or args.daily_midnight) and args.retire_demo:
    parser.error('Demo migration is a one-time operation')
if args.apply and not args.environment:
    parser.error('--apply requires --environment')
if args.environment:
    os.environ.update(json.loads(args.environment.read_text(encoding='utf-8-sig')))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import external_groupbuys, groupbuy_discovery
from app.db import SessionLocal

def collect_once():
    if args.discover:
        with SessionLocal() as db:
            receipt = groupbuy_discovery.collect(db if args.apply else None)
        receipt.update(stored=0, expired=0, ended=0, demo_changes=0)
        if args.apply:
            with SessionLocal.begin() as db:
                receipt.update(groupbuy_discovery.apply_collection(db, receipt))
        write_receipt(receipt)
        return bool(receipt['failures'])
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
    write_receipt(receipt)
    return bool(failures)


def write_receipt(receipt):
    if args.daily_midnight:
        receipt['schedule_timezone'] = 'Asia/Seoul'
        receipt['next_run_at'] = external_groupbuys.release.timestamp(
            int(time.time() + groupbuy_discovery.seconds_until_midnight()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_suffix('.pending.json')
    pending.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(args.output)
    print(json.dumps({'collected': len(receipt['entries']), 'failed': len(receipt['failures']),
                      'stored': receipt['stored'], 'expired': receipt.get('expired', 0),
                      'ended': receipt.get('ended', 0),
                      'demo_changes': receipt['demo_changes']}), flush=True)


while True:
    try:
        failed = collect_once()
    except Exception as error:
        print(json.dumps({"collection_error": type(error).__name__}), flush=True)
        failed = True
    if not args.interval_seconds and not args.daily_midnight:
        raise SystemExit(1 if failed else 0)
    time.sleep(groupbuy_discovery.seconds_until_midnight() if args.daily_midnight else args.interval_seconds)
