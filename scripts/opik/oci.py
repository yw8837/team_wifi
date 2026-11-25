"""Read-only public OCI downloader and safe user-prefix rootfs extraction; no daemon/namespaces."""
import hashlib
import json
import os
import posixpath
from pathlib import Path
import shutil
import tarfile
import tempfile
from uuid import uuid4
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ', '.join(['application/vnd.oci.image.index.v1+json','application/vnd.docker.distribution.manifest.list.v2+json','application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.v2+json'])


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        result = super().redirect_request(request, fp, code, msg, headers, newurl)
        if result and urllib.parse.urlsplit(request.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            result.remove_header('Authorization')
        return result


class OCI:
    def __init__(self, image, cache):
        self.image=image
        registry, reference=image.split('/',1)
        self.repository,self.reference=reference.rsplit(':',1)
        self.registry='registry-1.docker.io' if registry=='docker.io' else registry
        self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.token=None
        self.opener=urllib.request.build_opener(SafeRedirect())

    def open(self,path,accept=None):
        headers={'User-Agent':'TeamWifi-native-opik/1'}
        if accept:headers['Accept']=accept
        if self.token:headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request('https://'+self.registry+'/v2/'+self.repository+'/'+path,headers=headers)
        try:return self.opener.open(request,timeout=90)
        except urllib.error.HTTPError as error:
            if error.code!=401:raise
            import re
            params=dict(re.findall(r'(\w+)="([^"]*)"',error.headers.get('WWW-Authenticate','')))
            query=urllib.parse.urlencode({'service':params.get('service',''),'scope':params.get('scope','repository:'+self.repository+':pull')})
            with self.opener.open(params['realm']+'?'+query,timeout=30) as response:
                credentials=json.load(response);self.token=credentials.get('token') or credentials['access_token']
            headers['Authorization']='Bearer '+self.token
            return self.opener.open(urllib.request.Request(request.full_url,headers=headers),timeout=90)

    def manifest(self,reference):
        with self.open('manifests/'+reference,ACCEPT) as response:
            raw=response.read(2_000_000)
            digest='sha256:'+hashlib.sha256(raw).hexdigest()
            if reference.startswith('sha256:') and digest!=reference:raise RuntimeError('OCI manifest digest mismatch')
            data=json.loads(raw)
            if 'manifests' in data:
                selected=[m for m in data['manifests'] if m.get('platform',{}).get('architecture')=='amd64' and m.get('platform',{}).get('os')=='linux']
                if not selected:raise RuntimeError('No Linux amd64 OCI manifest')
                return self.manifest(selected[0]['digest'])
            return digest,data

    def blob(self,digest):
        algorithm,value=digest.split(':',1)
        if algorithm!='sha256' or len(value)!=64:raise ValueError('Unsupported digest')
        destination=self.cache/(value+'.blob')
        if destination.exists() and file_hash(destination)==value:return destination
        part=destination.with_suffix('.partial')
        checksum=hashlib.sha256();count=0
        with self.open('blobs/'+digest) as source,part.open('wb') as output:
            os.chmod(part,0o600)
            while True:
                block=source.read(1024*1024)
                if not block:break
                count+=len(block)
                if count>2_000_000_000:raise RuntimeError('OCI layer exceeds byte budget')
                checksum.update(block);output.write(block)
        if checksum.hexdigest()!=value:raise RuntimeError('OCI blob digest mismatch')
        part.replace(destination)
        return destination

    def extract(self,destination):
        destination=Path(destination).absolute()
        if destination.is_symlink():raise ValueError('OCI destination cannot be a symlink')
        destination.parent.mkdir(parents=True,exist_ok=True)
        manifest_digest,manifest=self.manifest(self.reference)
        stamp=destination/'.verified-image.json'
        if stamp.exists() and json.loads(stamp.read_text())['manifest_digest'] != manifest_digest:
            raise ValueError('A different OCI manifest requires a fresh extraction directory')
        if stamp.exists() and json.loads(stamp.read_text())['manifest_digest']==manifest_digest and json.loads(stamp.read_text()).get('extraction_version')==3:
            print('Cached '+self.image,flush=True);return json.loads(stamp.read_text())
        # Rebuild old extraction formats in an empty sibling. Replaying base
        # layers over a merged root breaks legitimate file-to-directory changes.
        stage=Path(tempfile.mkdtemp(prefix=destination.name+'.staging-',dir=destination.parent))
        for index,layer in enumerate(manifest['layers']):
            print('Layer '+self.image+' '+str(index+1)+'/'+str(len(manifest['layers']))+' '+str(layer.get('size',0)),flush=True)
            blob=self.blob(layer['digest'])
            extract_layer(blob,stage)
        provenance={'extraction_version':3,'image':self.image,'manifest_digest':manifest_digest,'layers':[item['digest'] for item in manifest['layers']]}
        staged_stamp=stage/'.verified-image.json'
        staged_stamp.write_text(json.dumps(provenance,indent=2)+'\n');os.chmod(staged_stamp,0o600)
        previous=destination.with_name(destination.name+'.previous-'+uuid4().hex)
        parent=destination.parent.resolve()
        if any(path.parent.resolve()!=parent for path in (stage,destination,previous)):
            raise ValueError('OCI staging promotion must stay in the destination parent')
        archived=False
        if destination.exists():
            destination.rename(previous)
            archived=True
        try:stage.rename(destination)
        except OSError:
            if archived and not destination.exists():previous.rename(destination)
            raise
        # Retain previous rootfs for inspection/rollback; never delete running files.
        return provenance


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def bounded(root,path):
    candidate=root/path
    result=Path(os.path.abspath(candidate.parent.resolve()/candidate.name))
    if result!=root and root not in result.parents:raise ValueError('Unsafe OCI extraction path')
    return result


def extract_layer(archive,destination):
    root=destination.resolve()
    with tarfile.open(archive,'r:*') as layer:
        members=[]
        for item in layer.getmembers():
            relative=Path(item.name)
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe OCI member')
            if not relative.parts or relative.parts[0] in ('dev','proc','sys','run'):continue
            members.append((item,relative))
        # OCI whiteouts remove lower-layer content only, regardless of tar order.
        # Apply them before writing any files from this layer.
        for item,relative in members:
            if relative.name.startswith('.wh.'):
                if relative.name=='.wh..wh..opq':
                    directory=bounded(root,relative.parent)
                    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                        directory.unlink()
                    directory.mkdir(parents=True,exist_ok=True)
                    for child in directory.iterdir():
                        target=bounded(root,child.relative_to(root))
                        if target.is_dir() and not target.is_symlink():shutil.rmtree(target)
                        else:target.unlink()
                    continue
                target=bounded(root,relative.parent/relative.name[4:])
                if target.is_dir() and not target.is_symlink():shutil.rmtree(target)
                elif target.exists() or target.is_symlink():target.unlink()
        for item,relative in members:
            if relative.name.startswith('.wh.'):continue
            target=bounded(root,relative)
            if item.isdir():target.mkdir(parents=True,exist_ok=True);continue
            if not(item.isfile() or item.issym() or item.islnk()):continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.is_symlink():target.unlink()
            if item.issym():
                linked=Path(item.linkname)
                try:
                    image_path=posixpath.normpath('/'+(linked.as_posix().lstrip('/') if linked.is_absolute() else (relative.parent/linked).as_posix())).lstrip('/')
                    linked=bounded(root,image_path)
                except (ValueError,RuntimeError):
                    print('Skipping unsafe/unneeded image symlink '+str(relative),flush=True)
                    continue
                if target.exists():
                    if target.is_dir():continue
                    target.unlink()
                target.symlink_to(os.path.relpath(linked,target.parent))
            elif item.islnk():
                linked=bounded(root,Path(item.linkname).as_posix().lstrip('/'))
                if target.exists():target.unlink()
                if linked.exists():os.link(linked,target)
            else:
                source=layer.extractfile(item)
                if source:
                    if target.exists():target.chmod(target.stat().st_mode | 0o600)
                    with target.open('wb') as output:shutil.copyfileobj(source,output,1024*1024)
                    target.chmod(item.mode & 0o777)
