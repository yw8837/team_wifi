"""Start the API from a protected JSON environment file; never print secrets."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if os.name != 'nt' and args.environment.stat().st_mode & 0o077:
        raise SystemExit('Environment file must be readable only by its owner (chmod 600).')
    values = json.loads(args.environment.read_text(encoding='utf-8-sig'))
    if values.get('MODU_ENV') != 'public_release' or not all(isinstance(v, str) for v in values.values()):
        raise SystemExit('Expected a public-release environment with string values.')
    os.environ.update(values)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'backend'))
    import uvicorn
    uvicorn.run('app.main:app', host=args.host, port=args.port, access_log=False,
                limit_concurrency=24, timeout_keep_alive=5, proxy_headers=False)


if __name__ == '__main__':
    main()
