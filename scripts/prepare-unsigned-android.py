"""Package CI outputs for local signing. This script never reads signing secrets."""
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
assert os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('MODU_UNSIGNED_CI') == '1'
assert not any(os.environ.get(key) for key in ('MODU_KEYSTORE', 'MODU_STORE_PASSWORD', 'MODU_KEY_PASSWORD'))
commit = os.environ['GITHUB_SHA']
assert re.fullmatch(r'[a-f0-9]{40}', commit)
assert os.environ['VITE_PUBLIC_RELEASE'] == '1' and os.environ['VITE_BETA_MODE'] == '0'
api = os.environ['VITE_API_BASE_URL']
assert api == 'https://moduyuga-beta.onrender.com/api'
out = root / 'artifacts/android/unsigned-ci'
out.mkdir(parents=True, exist_ok=False)
dist = root / 'frontend/dist'
shutil.copytree(dist, out / 'web')
sources = {
    'moduyuga-unsigned.apk': root / 'frontend/android/app/build/outputs/apk/release/app-release-unsigned.apk',
    'moduyuga-unsigned.aab': root / 'frontend/android/app/build/outputs/bundle/release/app-release.aab',
}
for name, source in sources.items():
    shutil.copy2(source, out / name)
    prefix = 'assets/public/' if source.suffix == '.apk' else 'base/assets/public/'
    with zipfile.ZipFile(source) as archive:
        html = unescape(archive.read(prefix+'index.html').decode())
        assert re.search(r'<meta\s+name="moduyuga-mode"\s+content="public_release"', html)
        for file in dist.rglob('*'):
            if file.is_file():
                assert archive.read(prefix+file.relative_to(dist).as_posix()) == file.read_bytes()

def version(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
    return (result.stdout + result.stderr).strip()

manifest = dict(schema_version=1, signed=False, commit=commit, run_id=os.environ['GITHUB_RUN_ID'],
                run_attempt=os.environ['GITHUB_RUN_ATTEMPT'], mode='public_release', api=api,
                versionCode=int(os.environ['MODU_VERSION_CODE']), versionName=os.environ['MODU_VERSION_NAME'],
                tools={'java': version(['java', '-version']), 'node': version(['node', '--version'])}, files={})
for file in sorted(out.rglob('*')):
    if file.is_file():
        raw = file.read_bytes()
        manifest['files'][file.relative_to(out).as_posix()] = dict(bytes=len(raw), sha256=sha256(raw).hexdigest())
(out/'provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('UNSIGNED_ANDROID_PROVENANCE_PASS', commit, len(manifest['files']))
