"""Apply the user-authorized labelled demo dataset using an existing environment."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--environment', type=Path, required=True)
parser.add_argument('--apply', action='store_true', required=True)
args = parser.parse_args()
values = json.loads(args.environment.read_text(encoding='utf-8-sig'))
os.environ.update(values)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import SessionLocal
from app.community_demo import seed

with SessionLocal.begin() as session:
    receipt = seed(session)
print(json.dumps(receipt, ensure_ascii=False))
