"""Real image decoding, private evidence ownership and bounded local file storage."""
from io import BytesIO
import os

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
import pytest
from sqlalchemy import select

from app import attachments as A, config
from app.db import Record, SessionLocal, User
from app.http_safety import BodyLimitMiddleware


@pytest.fixture
def files(setup, monkeypatch, tmp_path):
    _, people, ids = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', False)
    monkeypatch.setattr(config, 'BETA', False)
    monkeypatch.setattr(A, 'UPLOAD_ROOT', tmp_path/'uploads')
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware)
    app.include_router(A.router)
    with TestClient(app) as client:
        yield client, people, ids


def picture(fmt='PNG', size=(640,640), metadata=False):
    image = Image.new('RGB',size,(110,120,130))
    out = BytesIO()
    kwargs = {}
    if metadata and fmt == 'PNG':
        info = PngImagePlugin.PngInfo()
        info.add_text('private-note','GPS-PRIVATE-METADATA')
        kwargs['pnginfo'] = info
    image.save(out,format=fmt,**kwargs)
    return out.getvalue()


def upload(client, person, purpose='bankproof', raw=None, name='bank.png', mime='image/png'):
    return client.post('/api/attachments',headers=person['headers'],data={'purpose':purpose},
                       files={'file':(name,picture() if raw is None else raw,mime)})


@pytest.mark.parametrize('fmt,name,mime',[('JPEG','photo.jpg','image/jpeg'),('JPEG','photo.JPEG','image/jpeg'),
    ('PNG','photo.png','image/png'),('GIF','photo.gif','image/gif'),('BMP','photo.bmp','image/bmp')])
def test_allowed_actual_formats_reencode_to_clean_png(files,fmt,name,mime):
    c,p,_=files
    response=upload(c,p['seller'],'thumbnail',picture(fmt),name,mime)
    assert response.status_code==201,response.text
    data=response.json()
    assert data['source_format']==fmt and data['format']=='PNG' and data['width']==data['height']==640
    assert 'sha256' not in data and 'path' not in data
    download=c.get('/api/attachments/'+data['id'],headers=p['seller']['headers'])
    assert download.status_code==200 and download.content.startswith(b'\x89PNG')
    assert download.headers['cache-control']=='private, no-store'
    assert download.headers['x-content-type-options']=='nosniff'
    assert 'attachment;' in download.headers['content-disposition']
    assert "sandbox" in download.headers['content-security-policy']
    assert not A.storage_paths(data['id'])[1].exists()


@pytest.mark.parametrize('raw,name,mime',[(b'<svg/>','x.svg','image/svg+xml'),(b'not an image','x.png','image/png'),
    (picture(),'x.jpg','image/jpeg'),(picture(),'x.png','text/html'),(picture()[:40],'x.png','image/png')])
def test_forged_mismatched_or_truncated_images_rejected_without_files(files,raw,name,mime):
    c,p,_=files
    assert upload(c,p['seller'],'thumbnail',raw,name,mime).status_code==422
    assert not A.UPLOAD_ROOT.exists() or list(A.UPLOAD_ROOT.iterdir())==[]
    with SessionLocal() as db:
        assert not db.scalar(select(Record.id).where(Record.kind==A.ATTACHMENT))


@pytest.mark.parametrize('size',[(639,639),(640,641),(640,639)])
def test_thumbnail_minimum_and_square_restriction(files,size):
    c,p,_=files
    assert upload(c,p['seller'],'thumbnail',picture(size=size)).status_code==422


def test_detail_width_not_forced_and_metadata_removed(files):
    c,p,_=files
    source=picture(size=(7,1500),metadata=True)
    result=upload(c,p['seller'],'detail',source).json()
    response=c.get('/api/attachments/'+result['id'],headers=p['seller']['headers'])
    assert response.status_code==200
    with Image.open(BytesIO(response.content)) as image:
        assert image.size==(7,1500) and 'private-note' not in image.info
    assert b'GPS-PRIVATE-METADATA' not in response.content


def test_stream_size_pixels_frames_and_storage_quota_are_bounded(files,monkeypatch):
    c,p,_=files
    raw=picture(size=(10,10))
    with SessionLocal() as db:
        user=db.get(User,p['seller']['id'])
        with pytest.raises(HTTPException) as size:
            A.store_upload(db,user,BytesIO(b'x'*(4*A.MIB+1)),'x.png','image/png','thumbnail')
        assert size.value.status_code==422
    monkeypatch.setattr(A,'MAX_PIXELS',50)
    assert upload(c,p['seller'],'detail',raw).status_code==422
    monkeypatch.setattr(A,'MAX_PIXELS',16_000_000)
    monkeypatch.setattr(A,'MAX_ACCOUNT_BYTES',1)
    assert upload(c,p['seller'],'detail',raw).status_code==422
    monkeypatch.setattr(A,'MAX_ACCOUNT_BYTES',100*A.MIB)
    frames=BytesIO()
    Image.new('RGB',(5,5),'red').save(frames,format='GIF',save_all=True,append_images=[Image.new('RGB',(5,5),'blue')])
    monkeypatch.setattr(A,'MAX_FRAMES',1)
    assert upload(c,p['seller'],'detail',frames.getvalue(),'two.gif','image/gif').status_code==422
    assert not A.UPLOAD_ROOT.exists() or not list(A.UPLOAD_ROOT.iterdir())


def test_auth_private_original_ownership_application_match_and_erasure(files):
    c,p,_=files
    assert c.post('/api/attachments',data={'purpose':'bankproof'},files={'file':('a.png',picture(),'image/png')}).status_code==401
    assert upload(c,p['buyer'],'thumbnail').status_code==403
    raw=picture(metadata=True)
    response=upload(c,p['buyer'],'bankproof',raw,'../../통장.png')
    assert response.status_code==201,response.text
    item=response.json()
    url='/api/attachments/'+item['id']
    assert item['filename']=='통장.png'
    assert c.get(url,headers=p['buyer2']['headers']).status_code==404
    assert c.get(url,headers=p['admin']['headers']).status_code==404
    assert c.get(url+'/original',headers=p['admin']['headers']).status_code==404
    assert c.get(url+'/original',headers=p['buyer']['headers']).content==raw
    with SessionLocal() as db:
        user=db.get(User,p['buyer']['id'])
        target=Record(kind='application',owner_id=user.id,data={'bankproof_id':item['id']})
        db.add(target);db.flush()
        A.bind_application_file(db,target,user)
        application_id=target.id
        db.commit()
    downloaded=c.get(url+'/original',headers=p['admin']['headers'])
    assert downloaded.status_code==200 and downloaded.content==raw
    for header in ['content-security-policy','x-content-type-options','cache-control','content-disposition']:
        assert header in downloaded.headers
    listing=c.get('/api/applications/'+application_id+'/attachments',headers=p['admin']['headers'])
    assert listing.status_code==200 and listing.json()['items'][0]['id']==item['id']
    assert c.get('/api/applications/'+application_id+'/attachments',headers=p['buyer2']['headers']).status_code==404
    with SessionLocal() as db:
        target=db.get(Record,application_id)
        target.data={'bankproof_id':'wrong-file-id'}
        db.commit()
    assert c.get(url+'/original',headers=p['admin']['headers']).status_code==404
    with SessionLocal() as db:
        A.purge_user_uploads(db,p['buyer']['id']);db.commit()
    assert not any(path.exists() for path in A.storage_paths(item['id']))
    assert c.get(url,headers=p['buyer']['headers']).status_code==404


def test_selection_checks_all_before_mutation_and_preserves_valid_file(files):
    c,p,ids=files
    thumb=upload(c,p['seller'],'thumbnail').json()['id']
    details=[upload(c,p['seller'],'detail',picture(size=(5,8))).json()['id'] for _ in range(4)]
    other=upload(c,p['buyer'],'bankproof').json()['id']
    with SessionLocal() as db:
        user=db.get(User,p['seller']['id'])
        target=db.get(Record,ids['campaign'])
        target.data={**target.data,'thumbnail_id':thumb,'thumbnail_alt_text':'상품 사진',
                     'detail_image_ids':details[:3],'detail_alt_texts':['설명1','설명2','설명3']}
        A.bind_campaign_files(db,target,user);db.commit()
        for purpose, selected in [('thumbnail',[thumb,thumb]),('detail',details),('detail',[other]),('bankproof',[other])]:
            with pytest.raises(HTTPException):
                A.bind_selection(db,target,purpose,selected,user)
        assert db.get(Record,thumb).parent_id==target.id and A.storage_paths(thumb)[0].is_file()
        target.data={**target.data,'detail_image_ids':details[1:],'detail_alt_texts':[]}
        with pytest.raises(HTTPException):
            A.bind_campaign_files(db,target,user)
        assert db.get(Record,details[0]).parent_id==target.id
    assert c.delete('/api/attachments/'+thumb,headers=p['seller']['headers']).status_code==409


def test_cross_parent_binding_cannot_reuse_file(files):
    c,p,ids=files
    detail=upload(c,p['seller'],'detail',picture(size=(5,8))).json()['id']
    with SessionLocal() as db:
        user=db.get(User,p['seller']['id']);target=db.get(Record,ids['campaign'])
        A.bind_selection(db,target,'detail',[detail],user)
        second=Record(kind='campaign',owner_id=user.id,data={});db.add(second);db.flush()
        with pytest.raises(HTTPException):
            A.bind_selection(db,second,'detail',[detail],user)
        db.rollback()


def test_failed_database_write_cleans_temporary_and_final_bytes(files,monkeypatch):
    _,p,_=files
    with SessionLocal() as db:
        user=db.get(User,p['buyer']['id'])
        monkeypatch.setattr(db,'commit',lambda: (_ for _ in ()).throw(RuntimeError('simulated storage failure')))
        with pytest.raises(RuntimeError):
            A.store_upload(db,user,BytesIO(picture()),'x.png','image/png','bankproof')
    assert list(A.UPLOAD_ROOT.iterdir())==[]
    with SessionLocal() as db:
        assert not db.scalar(select(Record.id).where(Record.kind==A.ATTACHMENT))


def test_orphan_cleanup_preserves_live_uploads_and_count_guard(files,monkeypatch):
    c,p,_=files
    live=upload(c,p['buyer']).json()['id']
    monkeypatch.setattr(A,'MAX_UNATTACHED',1)
    assert upload(c,p['buyer']).status_code==422
    assert A.storage_paths(live)[0].exists()
    with SessionLocal() as db:
        row=db.get(Record,live);row.created=A.now()-A.ORPHAN_TTL-1;row.ends=0;db.commit()
        assert A.cleanup_orphans(db)==1;db.commit()
    assert not any(path.exists() for path in A.storage_paths(live))


def test_source_submission_fields_and_bound_proof_required(files):
    _,p,_=files
    with SessionLocal() as db:
        user=db.get(User,p['buyer']['id']);target=Record(kind='application',owner_id=user.id,data={})
        with pytest.raises(HTTPException):
            A.validate_application_submission(db,target,user)
        seller=db.get(User,p['seller']['id']);campaign=Record(kind='campaign',owner_id=seller.id,data={})
        with pytest.raises(HTTPException):
            A.validate_campaign_submission(db,campaign,seller)


def test_public_release_never_opens_upload_or_download(files,monkeypatch):
    c,p,_=files
    monkeypatch.setattr(config,'PUBLIC_RELEASE',True)
    assert upload(c,p['buyer']).status_code==404
    assert c.get('/api/attachments/00000000-0000-0000-0000-000000000000',headers=p['admin']['headers']).status_code==404


def test_middleware_only_expands_exact_dormant_upload_path(monkeypatch):
    import asyncio
    from app.http_safety import BodyLimitMiddleware
    calls=[]
    async def app(scope,receive,send):
        body=await receive();calls.append(len(body['body']))
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})
    async def invoke(path,public,chunks):
        monkeypatch.setattr(config,'PUBLIC_RELEASE',public)
        messages=[{'type':'http.request','body':chunk,'more_body':i<len(chunks)-1} for i,chunk in enumerate(chunks)]
        output=[]
        async def receive():return messages.pop(0)
        async def send(value):output.append(value)
        await BodyLimitMiddleware(app)({'type':'http','method':'POST','path':path},receive,send)
        return output[0]['status']
    assert asyncio.run(invoke('/api/attachments',False,[b'x'*65536,b'x']))==200
    for path,public in [('/api/attachments',True),('/api/attachments/other',False),('/api/release/demands',False)]:
        assert asyncio.run(invoke(path,public,[b'x'*65536,b'x']))==413
    assert asyncio.run(invoke('/api/attachments',False,[b'x'*(A.FORM_BODY_LIMIT+1)]))==413
    assert calls==[65537]


def test_untracked_crash_files_cleanup_storage_capacity_and_path_safety(files,monkeypatch):
    c,p,_=files
    A.UPLOAD_ROOT.mkdir(parents=True)
    # A process crash can leave bytes before its metadata transaction commits.
    abandoned=A.UPLOAD_ROOT/'00000000-0000-0000-0000-000000000000.png'
    abandoned.write_bytes(b'old crash data')
    old=A.now()-A.ORPHAN_TTL-2
    os.utime(abandoned,(old,old))
    temporary=A.UPLOAD_ROOT/'upload-abandoned.tmp'
    temporary.write_bytes(b'old temp data');os.utime(temporary,(old,old))
    with SessionLocal() as db:
        A.cleanup_orphans(db);db.commit()
    assert not abandoned.exists() and not temporary.exists()
    with pytest.raises(HTTPException):A.storage_paths('../../outside')
    monkeypatch.setattr(A,'MAX_STORAGE_BYTES',1)
    assert upload(c,p['buyer']).status_code==503
    assert not list(A.UPLOAD_ROOT.iterdir())


def test_original_download_rejects_poisoned_legacy_cross_purpose_binding(files):
    c,p,ids=files
    attachment=upload(c,p['seller'],'bankproof').json()['id']
    with SessionLocal() as db:
        item=db.get(Record,attachment)
        target=db.get(Record,ids['campaign'])
        item.parent_id=target.id
        target.data={**target.data,'thumbnail_id':attachment}
        db.commit()
    assert c.get('/api/attachments/'+attachment+'/original',headers=p['admin']['headers']).status_code==404
    assert c.get('/api/attachments/'+attachment,headers=p['admin']['headers']).status_code==404
