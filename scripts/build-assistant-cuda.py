"""Build the pinned GPU engine against the existing host's glibc and CUDA.

The upstream CUDA binary targets a newer glibc than this instance. All build
files and downloads stay in the approved project; no system library is replaced.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

REVISION = 'cd959bae99ff4bed22bef2604f45241c09bbb8c8'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    runtime = root / '.runtime'
    workspace = runtime / 'assistant-build'
    workspace.mkdir(exist_ok=True)
    temp = workspace / 'tmp'
    temp.mkdir(exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(temp), 'TEMP': str(temp), 'TMP': str(temp),
           'PIP_CACHE_DIR': str(runtime / 'pip-cache'), 'UV_CACHE_DIR': str(runtime / 'uv-cache')}
    cmake = workspace / 'cmake/cmake/data/bin/cmake'
    if not cmake.exists():
        uv = runtime / 'uv-tool/bin/uv'
        subprocess.run([str(uv), 'pip', 'install', '--python', sys.executable, '--target', str(workspace / 'cmake'),
                        'cmake==3.31.6'], check=True, env=env)
    archive = workspace / f'llama-{REVISION}.tar.gz'
    url = f'https://github.com/ggml-org/llama.cpp/archive/{REVISION}.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
    with archive.open('rb') as source:
        source_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    with tarfile.open(archive) as source:
        source.extractall(workspace, filter='data')
    source = workspace / f'llama.cpp-{REVISION}'
    build = workspace / 'cuda-build'
    with (workspace / 'cuda-build.log').open('w') as output:
        print('Configuring pinned CUDA source for existing sm80 GPU', flush=True)
        subprocess.run([str(cmake), '-S', str(source), '-B', str(build),
                        '-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON', '-DCMAKE_CUDA_ARCHITECTURES=80',
                        '-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc', '-DLLAMA_BUILD_TESTS=OFF',
                        '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_TOOLS=ON',
                        '-DLLAMA_CURL=OFF'], env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
        print('Building llama-server; progress in .runtime/assistant-build/cuda-build.log', flush=True)
        subprocess.run([str(cmake), '--build', str(build), '--target', 'llama-server', '--parallel', '2'],
                       env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
    binary = build / 'bin/llama-server'
    result = subprocess.run([str(binary), '--list-devices'], capture_output=True, text=True, check=True, env=env)
    (workspace / 'provenance.json').write_text(json.dumps({
        'engine': 'ggml-org/llama.cpp', 'revision': REVISION, 'source_url': url,
        'source_archive_sha256': source_hash, 'cmake_version': '3.31.6', 'cuda_architecture': '80',
        'binary': str(binary), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'devices': result.stdout.strip(),
    }, indent=2) + '\n')
    print(result.stdout, flush=True)
    print('Native CUDA engine ready', flush=True)


if __name__ == '__main__':
    main()
