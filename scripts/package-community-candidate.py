"""Package reviewable source only; never include runtime credentials or member data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT not in output.parents or output.exists():
        parser.error('Choose a new output file inside the active workspace.')
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
        '--', 'backend/app', 'backend/tests', 'backend/requirements.txt', 'backend/requirements-opik.txt',
        'scripts', 'ai-pipeline'], cwd=ROOT).decode().split('\0')
    files = []
    for name in sorted(set(filter(None, names))):
        path = ROOT / name
        if not path.is_file() or path.suffix in ('.log', '.pem', '.env'):
            continue
        if path.is_symlink() or ROOT not in path.resolve().parents:
            raise SystemExit('Source package cannot follow external paths or symlinks.')
        files.append((name, path))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'w:gz') as archive:
        for name, path in files:
            archive.add(path, arcname=name, recursive=False)
    receipt = {'base_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
               'includes_working_changes': True, 'source_files': len(files),
               'archive_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
               'files': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files}}
    output.with_suffix('.manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'files'}))


if __name__ == '__main__':
    main()
