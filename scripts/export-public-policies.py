"""Export the same public policies for the free static web frontend.

Only public disclosures are used. This build has no DB connection or secrets.
"""
from html import escape
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/dist')
output_root = parser.parse_args().output_dir.resolve()
if not output_root.is_relative_to(ROOT):
    parser.error('Policy output must stay inside the project')
os.environ['MODU_ENV'] = 'local'
sys.path.insert(0, str(ROOT / 'backend'))
from app import config
from app.legal_public import public_pages, public_page

if not all((config.SUPPORT_EMAIL, config.HOSTING_LOCATION, config.DATABASE_LOCATION)):
    raise SystemExit('Static policy build requires the real public support and storage disclosures.')
contact = f'<a href="mailto:{escape(config.SUPPORT_EMAIL)}">{escape(config.SUPPORT_EMAIL)}</a>'
for kind, (title, body) in public_pages(contact).items():
    output = output_root / 'legal' / kind / 'index.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    html = public_page(title, body).replace('<meta name="robots"',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'self\'">\n<meta name="robots"', 1)
    output.write_text(html, encoding='utf-8')
print('PUBLIC_POLICY_EXPORT_PASS 4 pages; no database access')
