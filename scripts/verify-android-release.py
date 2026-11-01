"""Verify signed release artifacts offline; device execution is a separate gate."""
import argparse
import hashlib
from html import unescape
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--sdk', default='C:/Users/Public/CodexRuntime/android-sdk')
parser.add_argument('--java', default='C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot')
args = parser.parse_args()
release = ROOT / 'artifacts/android/release'
build = json.loads((release / 'build.json').read_text(encoding='utf-8-sig'))
evidence = ROOT / 'artifacts/beta'
evidence.mkdir(parents=True, exist_ok=True)
checks = []


def check(name, condition):
    checks.append({'name': name, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(name)


def run(name, command):
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=90, cwd=ROOT)
    (evidence / name).write_text(result.stdout + result.stderr, encoding='utf-8')
    check(name + ': exit zero', result.returncode == 0)
    return result.stdout + result.stderr


for item in build['artifacts']:
    artifact = release / item['name']
    check(item['name'] + ': SHA256', hashlib.sha256(artifact.read_bytes()).hexdigest() == item['sha256'])
    prefix = 'assets/' if artifact.suffix == '.apk' else 'base/assets/'
    with zipfile.ZipFile(artifact) as archive:
        html = unescape(archive.read(prefix + 'public/index.html').decode())
        check(item['name'] + ': CSP before script', 0 <= html.index('http-equiv="Content-Security-Policy"') < html.index('<script'))
        check(item['name'] + ': CSP HTTPS origin', 'https://moduyuga-beta.onrender.com' in html and 'unsafe-eval' not in html and '10.0.2.2' not in html)
        config = json.loads(archive.read(prefix + 'capacitor.config.json'))
        check(item['name'] + ': package', config['appId'] == 'kr.moduyuga.app')
        check(item['name'] + ': exact Korean name', config['appName'] == '모두의 육아 - 육아템 공동구매,핫딜')
        check(item['name'] + ': no remote app bundle', not config.get('server', {}).get('url'))
        scripts = '\n'.join(archive.read(n).decode() for n in archive.namelist() if n.startswith(prefix+'public/assets/') and n.endswith('.js'))
        check(item['name'] + ': release HTTPS API', build['api'] in scripts)
        for asset in ('symbol.svg', 'wordmark.png'):
            check(item['name'] + ': original ' + asset, archive.read(prefix+'public/brand/'+asset) == (ROOT/'frontend/public/brand'/asset).read_bytes())

build_tools = Path(args.sdk) / 'build-tools/35.0.0'
sign = run('release-apksigner.txt', [str(build_tools/'apksigner.bat'), 'verify', '--verbose', '--print-certs', str(release/'moduyuga-beta.apk')])
check('APK v2 signature', 'Verified using v2 scheme (APK Signature Scheme v2): true' in sign)
check('APK signing identity', 'CN=Team_Wifi' in sign)
jar = run('release-jarsigner.txt', [str(Path(args.java)/'bin/jarsigner.exe'), '-verify', str(release/'moduyuga-beta.aab')])
check('AAB JAR signature', 'jar verified.' in jar)
manifest = run('release-manifest.txt', [str(build_tools/'aapt.exe'), 'dump', 'xmltree', 'artifacts/android/release/moduyuga-beta.apk', 'AndroidManifest.xml'])
check('no debuggable=true', not any('debuggable' in line and '0xffffffff' in line for line in manifest.splitlines()))
for prop in ('allowBackup', 'usesCleartextTraffic'):
    check(prop+' false', any(prop in line and '=(type0x12)0x0' in line.replace(' ', '') for line in manifest.splitlines()))
badging = run('release-badging.txt', [str(build_tools/'aapt.exe'), 'dump', 'badging', 'artifacts/android/release/moduyuga-beta.apk'])
check('target API36', "targetSdkVersion:'36'" in badging)
check('no dangerous permissions', all('android.permission.INTERNET' in line or 'DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION' in line for line in badging.splitlines() if line.startswith('uses-permission:')))
report = {'scope': 'signed APK/AAB offline verification; Android execution and Play delivery are separate', 'checks': checks, 'build': build,
          'aab_signature_note': 'Android upload signing uses a self-signed certificate; jarsigner reports no public CA/timestamp and ZIP ordering warnings. Play bundle processing remains an independent validation.'}
(evidence/'android-release-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'ANDROID_RELEASE_OFFLINE_PASS {len(checks)} checks')
