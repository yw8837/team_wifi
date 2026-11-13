"""Offline OCI layer semantics; no image downloads or service changes."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('opik_oci', Path(__file__).resolve().parents[2] / 'scripts/opik/oci.py')
oci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oci)


def layer(tmp_path, name, entries):
    path = tmp_path / name
    with tarfile.open(path, 'w') as archive:
        for filename, content in entries:
            data = content.encode()
            item = tarfile.TarInfo(filename)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
    return path


@pytest.mark.parametrize('whiteout_first', [True, False])
def test_opaque_whiteout_removes_only_lower_content(tmp_path, whiteout_first):
    root = tmp_path / 'rootfs'
    root.mkdir()
    oci.extract_layer(layer(tmp_path, 'base.tar', [('etc/obsolete.conf', 'old'), ('etc/sub/old', 'old'), ('keep', 'keep')]), root)
    entries = [('etc/.wh..wh..opq', ''), ('etc/current.conf', 'new')]
    if not whiteout_first:
        entries.reverse()
    oci.extract_layer(layer(tmp_path, 'upper.tar', entries), root)
    assert sorted(p.name for p in (root / 'etc').iterdir()) == ['current.conf']
    assert (root / 'etc/current.conf').read_text() == 'new'
    assert (root / 'keep').read_text() == 'keep'


def test_regular_whiteout_does_not_delete_same_layer_replacement(tmp_path):
    root = tmp_path / 'rootfs'
    root.mkdir()
    oci.extract_layer(layer(tmp_path, 'base.tar', [('value', 'old')]), root)
    oci.extract_layer(layer(tmp_path, 'upper.tar', [('value', 'new'), ('.wh.value', '')]), root)
    assert (root / 'value').read_text() == 'new'


def test_unsafe_whiteout_cannot_escape_root(tmp_path):
    root = tmp_path / 'rootfs'
    root.mkdir()
    outside = tmp_path / 'keep'
    outside.write_text('keep')
    with pytest.raises(ValueError):
        oci.extract_layer(layer(tmp_path, 'unsafe.tar', [('../.wh.keep', '')]), root)
    assert outside.read_text() == 'keep'


def test_v2_cache_upgrade_rebuilds_in_fresh_prefix_and_preserves_old(tmp_path):
    base = layer(tmp_path, 'base.tar', [('f', 'file')])
    upper = layer(tmp_path, 'upper.tar', [('.wh.f', ''), ('f/member', 'member')])
    root = tmp_path / 'image'
    root.mkdir()
    oci.extract_layer(base, root)
    oci.extract_layer(upper, root)
    (root / '.verified-image.json').write_text(json.dumps({'manifest_digest': 'same', 'extraction_version': 2}))
    client = oci.OCI('docker.io/example/image:fixed', tmp_path / 'cache')
    client.manifest = lambda _: ('same', {'layers': [{'digest': 'base'}, {'digest': 'upper'}]})
    client.blob = lambda digest: {'base': base, 'upper': upper}[digest]
    assert client.extract(root)['extraction_version'] == 3
    assert (root / 'f/member').read_text() == 'member'
    previous = list(tmp_path.glob('image.previous-*'))
    assert len(previous) == 1
    assert json.loads((previous[0] / '.verified-image.json').read_text())['extraction_version'] == 2
    assert (previous[0] / 'f/member').read_text() == 'member'


def test_failed_upgrade_does_not_replace_existing_root(tmp_path):
    root = tmp_path / 'image'
    root.mkdir()
    (root / 'keep').write_text('old')
    (root / '.verified-image.json').write_text(json.dumps({'manifest_digest': 'same', 'extraction_version': 2}))
    client = oci.OCI('docker.io/example/image:fixed', tmp_path / 'cache')
    client.manifest = lambda _: ('same', {'layers': [{'digest': 'broken'}]})
    client.blob = lambda _: layer(tmp_path, 'bad.tar', [('../escape', 'no')])
    with pytest.raises(ValueError):
        client.extract(root)
    assert (root / 'keep').read_text() == 'old'
    assert json.loads((root / '.verified-image.json').read_text())['extraction_version'] == 2
