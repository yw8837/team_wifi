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
    assert response.stderr.strip()==b'Dedicated inference key preparation failed.'
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
