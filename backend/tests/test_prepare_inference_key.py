import importlib.util
import os
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('prepare_inference_key',Path(__file__).resolve().parents[2]/'scripts/prepare-inference-key.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_copies_only_named_secret_and_preserves_original(tmp_path):
    original=b'-----BEGIN OPENSSH PRIVATE KEY-----\n'+b'SYNTHETIC'*20+b'\n-----END OPENSSH PRIVATE KEY-----\n'
    source=tmp_path/'platform-secret';source.write_bytes(original)
    result=module.prepare(source,tmp_path/'runtime')
    assert result.read_bytes()==original and source.read_bytes()==original
    assert result.parent.parent==tmp_path/'runtime'
    second=module.prepare(source,tmp_path/'runtime')
    assert second!=result
    if os.name=='posix':
        assert result.stat().st_mode&0o777==0o400
        assert result.parent.stat().st_mode&0o777==0o700


def test_rejects_relative_and_non_key_without_partial_file(tmp_path):
    with pytest.raises(ValueError):module.prepare('relative-secret',tmp_path/'runtime')
    source=tmp_path/'not-a-key';source.write_text('not a private key')
    with pytest.raises(ValueError):module.prepare(source,tmp_path/'runtime')
    assert not (tmp_path/'runtime').exists()


def test_secret_read_is_bounded_even_if_file_changes(monkeypatch,tmp_path):
    original=b'-----BEGIN OPENSSH PRIVATE KEY-----\n'+b'SYNTHETIC'*20+b'\n-----END OPENSSH PRIVATE KEY-----\n'
    source=tmp_path/'platform-secret';source.write_bytes(original)
    open_file=Path.open;reads=[]
    class Reader:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def read(self,size=-1):
            reads.append(size)
            # A regular secret replaced/grown after stat must still not be read unbounded.
            if size<0:return original+b'x'*20000
            return (original+b'x'*20000)[:size]
    def bounded(self,*args,**kwargs):
        stream=open_file(self,*args,**kwargs)
        return Reader(stream) if self==source else stream
    monkeypatch.setattr(Path,'open',bounded)
    with pytest.raises(ValueError):module.prepare(source,tmp_path/'runtime')
    assert reads==[16385]
    assert not (tmp_path/'runtime').exists()


def test_cli_failure_has_no_key_path_or_traceback(tmp_path):
    import subprocess,sys
    private_marker='SYNTHETIC_PRIVATE_CANARY'
    response=subprocess.run([sys.executable,str(Path(module.__file__))],env={**os.environ,
        'ASSISTANT_SSH_SECRET_FILE':str(tmp_path/private_marker),'RUNTIME_DIR':str(tmp_path/'runtime')},capture_output=True)
    assert response.returncode!=0 and response.stdout==b''
    assert response.stderr.strip()==b'Dedicated inference key preparation failed. reason=source_missing'
    assert private_marker.encode() not in response.stderr and b'Traceback' not in response.stderr


@pytest.mark.parametrize('enabled,expect_helper_failure',[('true',True),('false',False)])
def test_start_script_stops_before_server_when_key_preparation_fails(tmp_path,enabled,expect_helper_failure):
    import shutil,subprocess
    root=Path(__file__).resolve().parents[2]
    git_bash=root/'.runtime/toolchains/git/bin/bash.exe'
    bash=str(git_bash) if os.name=='nt' and git_bash.exists() else shutil.which('bash')
    if not bash:pytest.skip('Bash is required for the actual startup script regression.')
    for directory in (tmp_path/'fakebin',tmp_path/'backend/fakebin'):
        directory.mkdir(parents=True)
        fake=directory/'python'
        fake.write_text('#!/bin/sh\nif [ "$1" = "scripts/prepare-inference-key.py" ]; then echo "Dedicated inference key preparation failed." >&2; exit 7; fi\necho UVICORN_WOULD_START\n',encoding='utf-8',newline='\n')
        fake.chmod(0o700)
    response=subprocess.run([bash,str(root/'scripts/render-start.sh')],cwd=tmp_path,env={**os.environ,
        'PATH':'fakebin:/usr/bin:/bin','ASSISTANT_SSH_ENABLED':enabled,'PORT':'9999'},capture_output=True,timeout=15)
    if expect_helper_failure:
        assert response.returncode!=0
        assert b'UVICORN_WOULD_START' not in response.stdout
        assert b'Dedicated inference key preparation failed.' in response.stderr
    else:
        assert response.returncode==0 and b'UVICORN_WOULD_START' in response.stdout


@pytest.mark.parametrize('scenario,expected',[
    ('missing_config','secret_config_missing'),
    ('relative_source','source_path_not_absolute'),
    ('relative_runtime','runtime_path_not_absolute'),
    ('missing_source','source_missing'),
    ('directory_source','source_not_regular'),
    ('short_source','source_size_invalid'),
    ('invalid_key','key_format_invalid'),
    ('runtime_file','runtime_create_failed'),
])
def test_real_cli_reasons_never_include_submitted_values(tmp_path,scenario,expected):
    import subprocess,sys
    marker='PRIVATE_CANARY_DO_NOT_PRINT'
    source=tmp_path/marker
    source.write_bytes(b'-----BEGIN OPENSSH PRIVATE KEY-----\n'+b'SYNTHETIC'*20)
    runtime=tmp_path/(marker+'-runtime')
    env={**os.environ,'ASSISTANT_SSH_SECRET_FILE':str(source),'RUNTIME_DIR':str(runtime)}
    if scenario=='missing_config':env.pop('ASSISTANT_SSH_SECRET_FILE')
    elif scenario=='relative_source':env['ASSISTANT_SSH_SECRET_FILE']=marker
    elif scenario=='relative_runtime':env['RUNTIME_DIR']=marker
    elif scenario=='missing_source':source.unlink()
    elif scenario=='directory_source':source.unlink();source.mkdir()
    elif scenario=='short_source':source.write_bytes(b'short')
    elif scenario=='invalid_key':source.write_bytes(marker.encode()*10)
    elif scenario=='runtime_file':runtime.write_bytes(b'file')
    result=subprocess.run([sys.executable,module.__file__],env=env,capture_output=True,timeout=15)
    assert result.returncode!=0 and result.stdout==b''
    assert result.stderr.strip()==('Dedicated inference key preparation failed. reason='+expected).encode()
    assert marker.encode() not in result.stderr and b'Traceback' not in result.stderr


@pytest.mark.parametrize('stage,exception,expected',[
    ('stat',PermissionError,'source_stat_denied'),
    ('stat',OSError,'source_stat_failed'),
    ('read',PermissionError,'source_read_denied'),
    ('read',OSError,'source_read_failed'),
    ('runtime',PermissionError,'runtime_create_denied'),
])
def test_os_errors_are_fixed_reasons_without_raw_details(monkeypatch,tmp_path,stage,exception,expected):
    source=tmp_path/'source'
    source.write_bytes(b'-----BEGIN OPENSSH PRIVATE KEY-----\n'+b'SYNTHETIC'*20)
    runtime=tmp_path/'runtime'
    original_stat=Path.stat;original_open=Path.open;original_mkdir=Path.mkdir
    def fail():raise exception('PRIVATE_PATH SECRET_OS_DETAIL')
    if stage=='stat':
        def stat_file(self,*args,**kwargs):
            if self==source:fail()
            return original_stat(self,*args,**kwargs)
        monkeypatch.setattr(Path,'stat',stat_file)
    elif stage=='read':
        def open_file(self,*args,**kwargs):
            if self==source:fail()
            return original_open(self,*args,**kwargs)
        monkeypatch.setattr(Path,'open',open_file)
    else:
        def mkdir(self,*args,**kwargs):
            if self==runtime:fail()
            return original_mkdir(self,*args,**kwargs)
        monkeypatch.setattr(Path,'mkdir',mkdir)
    monkeypatch.setenv('ASSISTANT_SSH_SECRET_FILE',str(source))
    monkeypatch.setenv('RUNTIME_DIR',str(runtime))
    with pytest.raises(SystemExit) as error:module.main()
    assert str(error.value)=='Dedicated inference key preparation failed. reason='+expected
    assert 'PRIVATE' not in str(error.value)


def test_runtime_owner_guard_remains_fail_closed(monkeypatch,tmp_path):
    source=tmp_path/'source';source.write_bytes(b'-----BEGIN OPENSSH PRIVATE KEY-----\n'+b'SYNTHETIC'*20)
    runtime=tmp_path/'runtime';runtime.mkdir()
    monkeypatch.setattr(module,'service_uid',lambda:runtime.stat().st_uid+1)
    monkeypatch.setenv('ASSISTANT_SSH_SECRET_FILE',str(source));monkeypatch.setenv('RUNTIME_DIR',str(runtime))
    with pytest.raises(SystemExit) as error:module.main()
    assert str(error.value)=='Dedicated inference key preparation failed. reason=runtime_owner_mismatch'
    assert not list(runtime.iterdir())


def test_unexpected_failure_cli_still_has_no_raw_exception(monkeypatch,tmp_path):
    monkeypatch.setenv('ASSISTANT_SSH_SECRET_FILE',str(tmp_path/'private-marker'))
    def fail(*args):raise RuntimeError('PRIVATE_KEY_AND_PATH')
    monkeypatch.setattr(module,'prepare',fail)
    with pytest.raises(SystemExit) as error:module.main()
    assert str(error.value)=='Dedicated inference key preparation failed. reason=unexpected'


def test_reason_enum_never_accepts_freeform_details(monkeypatch,tmp_path):
    monkeypatch.setenv('ASSISTANT_SSH_SECRET_FILE',str(tmp_path/'source'))
    def fail(*args):raise module.PreparationError('PRIVATE_PATH_AND_SECRET')
    monkeypatch.setattr(module,'prepare',fail)
    with pytest.raises(SystemExit) as error:module.main()
    assert str(error.value)=='Dedicated inference key preparation failed. reason=unexpected'
