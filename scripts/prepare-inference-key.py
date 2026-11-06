"""Copy the explicitly configured Render secret to a process-owned private file.

Only the resulting path is printed. No key or configuration values are logged.
"""
import os
from pathlib import Path
import stat
import tempfile


def prepare(source, runtime):
    source=Path(source)
    runtime=Path(runtime)
    if not source.is_absolute() or not runtime.is_absolute():
        raise ValueError('Absolute secret and runtime paths are required.')
    metadata=source.stat()
    if not stat.S_ISREG(metadata.st_mode) or not 100<metadata.st_size<=16384:
        raise ValueError('Invalid dedicated key file.')
    with source.open('rb') as input_file:
        raw=input_file.read(16385)
    if not 100<len(raw)<=16384 or not raw.startswith(b'-----BEGIN OPENSSH PRIVATE KEY-----'):
        raise ValueError('Invalid dedicated key file.')
    runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
    if runtime.is_symlink() or (os.name=='posix' and runtime.stat().st_uid!=os.getuid()):
        raise ValueError('Runtime must belong to the service user.')
    private=Path(tempfile.mkdtemp(prefix='inference-',dir=runtime))
    target=private/'key'
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
    try:
        with os.fdopen(descriptor,'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        private.rmdir()
        raise
    if os.name=='posix' and (stat.S_IMODE(private.stat().st_mode)!=0o700 or stat.S_IMODE(target.stat().st_mode)!=0o400):
        raise ValueError('Private key permissions could not be established.')
    return target


if __name__=='__main__':
    try:
        result=prepare(os.environ['ASSISTANT_SSH_SECRET_FILE'],os.environ.get('RUNTIME_DIR','/tmp/moduyuga'))
    except Exception:
        raise SystemExit('Dedicated inference key preparation failed.') from None
    print(result)
