"""Add only the owned loopback inference program to the existing supervisor.

Run on the authorized existing host after setup-local-assistant.py. This script
does not stop or reconfigure the API, any other program, or external networking.
"""
import argparse
from pathlib import Path
import subprocess
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--accelerator', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--replace-owned-program', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    runtime = root / '.runtime'
    # The host's glibc is older than the official CUDA release binary. The
    # native build pins the same commit and records its binary hash/provenance.
    binary = (runtime / 'assistant-build/cuda-build/bin/llama-server' if args.accelerator == 'cuda'
              else runtime / 'assistant-model/cpu/llama-b12110/llama-server')
    model = runtime / 'assistant-model/Qwen3-1.7B-Q8_0.gguf'
    config = runtime / 'supervisord.conf'
    if not binary.is_file() or not model.is_file() or not config.is_file():
        raise SystemExit('Verified model, engine and existing supervisor required.')
    content = config.read_text()
    program = '\n'.join([
        '[program:moduyuga-assistant-model]',
        f'directory={root}',
        f'command={binary} --model {model} --host 127.0.0.1 --port 8091 '
        '--alias moduyuga-qwen3-1.7b --ctx-size 6144 --parallel 1 '
        '--threads 2 --threads-batch 2 --threads-http 2 --log-disable'
        + (' --n-gpu-layers 99' if args.accelerator == 'cuda' else ''),
        'autostart=true', 'autorestart=unexpected', 'startsecs=5', 'startretries=2',
        'stopasgroup=true', 'killasgroup=true', 'redirect_stderr=true',
        f'stdout_logfile={runtime}/logs/assistant-model.log',
        'stdout_logfile_maxbytes=1MB', 'stdout_logfile_backups=1', '',
    ])
    if '[program:moduyuga-assistant-model]' in content:
        if program not in content:
            if not args.replace_owned_program:
                raise SystemExit('Existing assistant program differs; inspect before changing.')
            previous = re.search(r'(?ms)^\[program:moduyuga-assistant-model\]\n.*?(?=^\[|\Z)', content)
            if not previous or str(root) not in previous.group():
                raise SystemExit('Owned assistant program identity not confirmed.')
            (runtime / 'assistant-model/previous-program.conf').write_text(previous.group())
            config.write_text(content[:previous.start()] + program + '\n' + content[previous.end():])
    else:
        config.write_text(content.rstrip() + '\n\n' + program)
    ctl = root / '.venv/bin/supervisorctl'
    subprocess.run([str(ctl), '-c', str(config), 'reread'], check=True)
    subprocess.run([str(ctl), '-c', str(config), 'update', 'moduyuga-assistant-model'], check=True)
    subprocess.run([str(ctl), '-c', str(config), 'status', 'moduyuga-assistant-model'], check=True)


if __name__ == '__main__':
    main()
