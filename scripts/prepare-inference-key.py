"""Prepare an explicitly configured secret without logging secret/configuration data.

Success prints the private runtime path for the startup shell. Failures print only
one fixed reason enum; OS exception text and input values never reach the CLI.
"""
import os
from pathlib import Path
import stat
import tempfile


REASONS = frozenset({
    'key_format_invalid',
    'private_chmod_denied',
    'private_chmod_failed',
    'private_key_chmod_denied',
    'private_key_chmod_failed',
    'private_directory_denied',
    'private_directory_failed',
    'private_key_create_denied',
    'private_key_create_failed',
    'private_key_missing',
    'private_key_stat_denied',
    'private_key_stat_failed',
    'private_key_write_failed',
    'private_missing',
    'private_parent_missing',
    'private_permissions_invalid',
    'private_stat_denied',
    'private_stat_failed',
    'runtime_create_denied',
    'runtime_create_failed',
    'runtime_missing',
    'runtime_owner_mismatch',
    'runtime_parent_missing',
    'runtime_path_not_absolute',
    'runtime_stat_denied',
    'runtime_stat_failed',
    'runtime_symlink',
    'secret_config_missing',
    'source_missing',
    'source_not_regular',
    'source_path_not_absolute',
    'source_read_denied',
    'source_read_failed',
    'source_size_invalid',
    'source_stat_denied',
    'source_stat_failed',
    'unexpected',
})


class PreparationError(ValueError):
    def __init__(self, code):
        self.code = code if isinstance(code,str) and code in REASONS else 'unexpected'
        super().__init__(self.code)


def checked_io(operation, *, missing, denied, failed):
    try:
        return operation()
    except FileNotFoundError:
        raise PreparationError(missing) from None
    except PermissionError:
        raise PreparationError(denied) from None
    except OSError:
        raise PreparationError(failed) from None


def service_uid():
    return os.getuid() if os.name == 'posix' else None


def prepare(source, runtime):
    source=Path(source)
    runtime=Path(runtime)
    if not source.is_absolute():
        raise PreparationError('source_path_not_absolute')
    if not runtime.is_absolute():
        raise PreparationError('runtime_path_not_absolute')
    metadata=checked_io(source.stat,missing='source_missing',denied='source_stat_denied',failed='source_stat_failed')
    if not stat.S_ISREG(metadata.st_mode):
        raise PreparationError('source_not_regular')
    if not 100<metadata.st_size<=16384:
        raise PreparationError('source_size_invalid')
    def read_secret():
        with source.open('rb') as input_file:
            return input_file.read(16385)
    raw=checked_io(read_secret,missing='source_missing',denied='source_read_denied',failed='source_read_failed')
    if not 100<len(raw)<=16384 or not raw.startswith(b'-----BEGIN OPENSSH PRIVATE KEY-----'):
        raise PreparationError('key_format_invalid')
    checked_io(lambda:runtime.mkdir(mode=0o700,parents=True,exist_ok=True),
        missing='runtime_parent_missing',denied='runtime_create_denied',failed='runtime_create_failed')
    if runtime.is_symlink():
        raise PreparationError('runtime_symlink')
    metadata=checked_io(runtime.stat,missing='runtime_missing',denied='runtime_stat_denied',failed='runtime_stat_failed')
    uid=service_uid()
    if uid is not None and metadata.st_uid!=uid:
        raise PreparationError('runtime_owner_mismatch')
    private=Path(checked_io(lambda:tempfile.mkdtemp(prefix='inference-',dir=runtime),
        missing='private_parent_missing',denied='private_directory_denied',failed='private_directory_failed'))
    # mkdir can inherit setgid/default ACL bits from the shared runtime parent.
    # Tighten only this newly created directory, never the parent or mounted secret.
    if os.name=='posix':
        checked_io(lambda:private.chmod(0o700),missing='private_missing',
            denied='private_chmod_denied',failed='private_chmod_failed')
    target=private/'key'
    descriptor=checked_io(lambda:os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400),
        missing='private_parent_missing',denied='private_key_create_denied',failed='private_key_create_failed')
    try:
        with os.fdopen(descriptor,'wb') as output:
            if os.name=='posix':
                checked_io(lambda:os.fchmod(output.fileno(),0o400),missing='private_key_missing',
                    denied='private_key_chmod_denied',failed='private_key_chmod_failed')
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except Exception as error:
        try:
            target.unlink(missing_ok=True)
            private.rmdir()
        except OSError:
            pass
        if isinstance(error,PreparationError):
            raise
        raise PreparationError('private_key_write_failed') from None
    if os.name=='posix':
        private_metadata=checked_io(private.stat,missing='private_missing',denied='private_stat_denied',failed='private_stat_failed')
        target_metadata=checked_io(target.stat,missing='private_key_missing',denied='private_key_stat_denied',failed='private_key_stat_failed')
        if stat.S_IMODE(private_metadata.st_mode)!=0o700 or stat.S_IMODE(target_metadata.st_mode)!=0o400:
            raise PreparationError('private_permissions_invalid')
    return target


def main():
    try:
        source=os.environ.get('ASSISTANT_SSH_SECRET_FILE')
        if not source:
            raise PreparationError('secret_config_missing')
        result=prepare(source,os.environ.get('RUNTIME_DIR','/tmp/moduyuga'))
    except PreparationError as error:
        raise SystemExit('Dedicated inference key preparation failed. reason='+error.code) from None
    except Exception:
        raise SystemExit('Dedicated inference key preparation failed. reason=unexpected') from None
    print(result)


if __name__=='__main__':
    main()
