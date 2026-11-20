import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from oci import extract_layer


class ExtractionSafety(unittest.TestCase):
    def archive(self,path,entries):
        with tarfile.open(path,'w') as out:
            for name,body,link in entries:
                info=tarfile.TarInfo(name)
                if link is not None:info.type=tarfile.SYMTYPE;info.linkname=link;out.addfile(info)
                else:info.size=len(body);info.mode=0o444;out.addfile(info,io.BytesIO(body))

    def test_rejects_archive_parent_traversal(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'.runtime/opik/tmp') as folder:
            root=Path(folder);self.archive(root/'layer.tar',[('../outside',b'bad',None)])
            with self.assertRaises(ValueError):extract_layer(root/'layer.tar',root/'extract')
            self.assertFalse((root.parent/'outside').exists())

    def test_prefix_symlink_and_readonly_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'.runtime/opik/tmp') as folder:
            root=Path(folder);destination=root/'extract';destination.mkdir()
            self.archive(root/'one.tar',[('etc/trust',b'old',None),('usr/lib/java/cacerts',b'', '/etc/trust')])
            extract_layer(root/'one.tar',destination)
            self.archive(root/'two.tar',[('etc/trust',b'new',None)])
            extract_layer(root/'two.tar',destination)
            self.assertEqual((destination/'usr/lib/java/cacerts').read_bytes(),b'new')
            self.assertTrue((destination/'usr/lib/java/cacerts').resolve().is_relative_to(destination))
            extract_layer(root/'one.tar',destination)
            self.assertEqual((destination/'usr/lib/java/cacerts').read_bytes(),b'old')


class LoopbackBindings(unittest.TestCase):
    def test_ipv4_ipv6_and_java_mapped_loopback(self):
        from verify import is_loopback
        for address,family in [('0100007F','tcp'),('00000000000000000000000001000000','tcp6'),('0000000000000000FFFF00000100007F','tcp6')]:
            self.assertTrue(is_loopback(address,family))
        for address,family in [('00000000','tcp'),('00000000000000000000000000000000','tcp6'),('0000000000000000FFFF000000000000','tcp6')]:
            self.assertFalse(is_loopback(address,family))


if __name__=='__main__':unittest.main()
