"""Dormant, authenticated image attachments. No public community upload surface.

Source limits: thumbnail 1 / 4 MiB / >=640px square; detail 3 / 20 MiB.
Operational bounds (not original requirements): bankproof 1 / 20 MiB, 16M decoded
pixels total, 100 frames, 10 unattached files, 100 MiB/account, 512 MiB storage,
5000 storage files, 24h orphan TTL. Image decoding is serialized within a worker.
Only bankproof retains validated original bytes for authorized evidence download;
all default downloads are reencoded PNGs without source metadata.
"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal
import warnings

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from . import config
from .db import RUNTIME, Record, get_db, now, uid
from .security import current_user, throttle
from .file_journal import stage_file_purge, storage_usage

ATTACHMENT = 'attachment'
UPLOAD_ROOT = RUNTIME / 'uploads'
MIB = 1024 * 1024
LIMITS = {'thumbnail': (1, 4*MIB), 'detail': (3, 20*MIB), 'bankproof': (1, 20*MIB)}
MAX_PIXELS = 16_000_000
MAX_FRAMES = 100
MAX_UNATTACHED = 10
MAX_ACCOUNT_BYTES = 100*MIB
MAX_STORAGE_FILES = 5000
MAX_STORAGE_BYTES = 512*MIB
_IMAGE_GATE = threading.BoundedSemaphore(1)
ORPHAN_TTL = 86400
FORM_BODY_LIMIT = 20*MIB + 65536
FORMATS = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'gif': 'GIF', 'bmp': 'BMP'}
MIMES = {'JPEG': {'image/jpeg', 'image/jpg'}, 'PNG': {'image/png'}, 'GIF': {'image/gif'}, 'BMP': {'image/bmp', 'image/x-ms-bmp'}}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def dormant_only():
    if config.PUBLIC_RELEASE:
        raise HTTPException(404, '공개 서비스에서 제공하지 않는 기능입니다.')


router = APIRouter(prefix='/api', dependencies=[Depends(dormant_only)])


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def storage_paths(id):
    # No client filename, owner ID, digest or stored path participates in a path.
    if not re.fullmatch(r'[a-f0-9-]{36}', id):
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    root = UPLOAD_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = (root / (id+'.png'), root / (id+'.original'))
    if any(path.resolve().parent != root or path.is_symlink() for path in paths):
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    return paths


def safe_filename(value):
    value = (value or '').replace('\\', '/').rsplit('/', 1)[-1]
    value = re.sub(r'[\x00-\x1f\x7f]', '', value).strip(' .')[:120]
    if not value or '.' not in value:
        raise HTTPException(422, '파일 이름과 JPG, JPEG, PNG, GIF, BMP 형식을 확인해 주세요.')
    return value


def validate_image(raw, filename, content_type, purpose):
    if purpose not in LIMITS:
        raise HTTPException(422, '첨부 용도를 확인해 주세요.')
    filename = safe_filename(filename)
    extension = filename.rsplit('.', 1)[-1].lower()
    expected = FORMATS.get(extension)
    if not expected or content_type.lower() not in MIMES[expected]:
        raise HTTPException(422, '확장자와 파일 형식은 JPG, JPEG, PNG, GIF, BMP로 일치해야 합니다.')
    if not raw or len(raw) > LIMITS[purpose][1]:
        raise HTTPException(422, '파일 용량이 허용 기준을 초과했거나 비어 있습니다.')
    try:
        with _IMAGE_GATE, warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=list(MIMES)) as probe:
                if probe.format != expected:
                    raise ValueError('type')
                width, height = probe.size
                if width*height > MAX_PIXELS:
                    raise ValueError('pixels')
                if purpose == 'thumbnail' and (width < 640 or height < 640 or width != height):
                    raise ValueError('thumbnail')
                probe.verify()
            with Image.open(BytesIO(raw), formats=list(MIMES)) as image:
                frames = getattr(image, 'n_frames', 1)
                if frames > MAX_FRAMES or width*height*frames > MAX_PIXELS:
                    raise ValueError('frames')
                for frame in range(frames):
                    image.seek(frame)
                    image.load()
                image.seek(0)
                # New image drops EXIF, comments, ICC, animation and arbitrary metadata.
                clean = Image.new('RGBA', (width, height))
                clean.paste(image.convert('RGBA'))
                buffer = BytesIO()
                clean.save(buffer, format='PNG')
                encoded = buffer.getvalue()
                if len(encoded) > LIMITS['detail'][1]:
                    raise ValueError('encoded size')
        return filename, expected, width, height, encoded
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError,
            OverflowError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, '실제 이미지 형식·용량·해상도를 확인해 주세요. 대표 사진은 640px 이상 정사각형이어야 합니다.') from None


def attachment_dto(item):
    return {'id': item.id, 'filename': item.data['filename'], 'purpose': item.data['purpose'],
            'format': 'PNG', 'source_format': item.data['source_format'], 'size': item.data['size'],
            'source_size': item.data['source_size'], 'width': item.data['width'], 'height': item.data['height'],
            'created_at': stamp(item.created)}


def cleanup_orphans(db):
    stale = list(db.scalars(select(Record).where(Record.kind == ATTACHMENT,
                 Record.parent_id.is_(None), Record.created < now()-ORPHAN_TTL, Record.ends <= now())))
    stage_file_purge(db, [item.id for item in stale], UPLOAD_ROOT)
    for item in stale:
        db.delete(item)
    # Interrupted writes have no DB row; only old server-named files are eligible.
    root = UPLOAD_ROOT.resolve()
    if root.is_dir():
        known = set(db.scalars(select(Record.id).where(Record.kind == ATTACHMENT)))
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                continue
            try:
                modified = path.stat().st_mtime
            except FileNotFoundError:
                continue  # A concurrent committed purge may already have moved it.
            if path.name.startswith('upload-') and path.suffix == '.tmp':
                if modified < now()-3600:
                    path.unlink(missing_ok=True)
            elif re.fullmatch(r'[a-f0-9-]{36}\.(png|original)', path.name):
                if path.name.split('.')[0] not in known and modified < now()-ORPHAN_TTL:
                    path.unlink(missing_ok=True)
    return len(stale)


def store_upload(db, user, stream, filename, content_type, purpose):
    if purpose not in LIMITS:
        raise HTTPException(422, '첨부 용도를 확인해 주세요.')
    if purpose != 'bankproof' and user.seller_status != 'approved':
        raise HTTPException(403, '승인된 판매자만 상품 이미지를 등록할 수 있습니다.')
    cleanup_orphans(db)
    if storage_usage(UPLOAD_ROOT)[0] >= MAX_STORAGE_FILES:
        raise HTTPException(503, '첨부 저장소가 혼잡합니다. 잠시 후 다시 시도해 주세요.')
    records = list(db.scalars(select(Record).where(Record.kind == ATTACHMENT, Record.owner_id == user.id)))
    if sum(item.parent_id is None for item in records) >= MAX_UNATTACHED:
        raise HTTPException(422, '연결하지 않은 첨부 파일이 많습니다. 기존 파일을 삭제한 후 다시 시도해 주세요.')
    limit = LIMITS[purpose][1]
    raw = bytearray()
    while len(raw) <= limit:
        chunk = stream.read(min(65536, limit+1-len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
    name, source_format, width, height, encoded = validate_image(bytes(raw), filename, content_type, purpose)
    original = bytes(raw) if purpose == 'bankproof' else None
    stored_size = len(encoded)+(len(original) if original else 0)
    if storage_usage(UPLOAD_ROOT)[1]+stored_size > MAX_STORAGE_BYTES:
        raise HTTPException(503, '첨부 저장소가 혼잡합니다. 잠시 후 다시 시도해 주세요.')
    if sum(item.data.get('stored_size', 0) for item in records)+stored_size > MAX_ACCOUNT_BYTES:
        raise HTTPException(422, '계정의 첨부 저장 한도를 초과했습니다. 기존 파일을 정리해 주세요.')
    item = Record(id=uid(), kind=ATTACHMENT, owner_id=user.id, ends=now()+ORPHAN_TTL, data={
        'filename': name, 'purpose': purpose, 'source_format': source_format, 'width': width, 'height': height,
        'size': len(encoded), 'source_size': len(raw), 'stored_size': stored_size,
        'sha256': sha256(encoded).hexdigest()})
    destinations = storage_paths(item.id)
    temporary, written = [], []
    try:
        for destination, payload in zip(destinations, (encoded, original)):
            if payload is None:
                continue
            with tempfile.NamedTemporaryFile(prefix='upload-', suffix='.tmp', dir=UPLOAD_ROOT, delete=False) as handle:
                temporary.append(Path(handle.name))
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary[-1], destination)
            written.append(destination)
        db.add(item)
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return item


@router.post('/attachments', status_code=201)
def upload(request: Request, purpose: Literal['thumbnail', 'detail', 'bankproof'] = Form(...),
           file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    try:
        return attachment_dto(store_upload(db, user, file.file, file.filename, file.content_type or '', purpose))
    finally:
        file.file.close()


def validate_selection(db, target, purpose, ids, user):
    if target.owner_id != user.id or target.kind not in ('campaign', 'application'):
        raise HTTPException(404, '첨부 대상을 찾을 수 없습니다.')
    if purpose not in LIMITS or (target.kind == 'application') != (purpose == 'bankproof'):
        raise HTTPException(422, '첨부 용도와 대상이 일치하지 않습니다.')
    if len(ids) != len(set(ids)) or len(ids) > LIMITS[purpose][0]:
        raise HTTPException(422, '첨부 개수와 중복 선택을 확인해 주세요.')
    selected = []
    for id in ids:
        item = db.get(Record, id)
        if not item or item.kind != ATTACHMENT or item.owner_id != user.id:
            raise HTTPException(404, '본인의 첨부 파일을 찾을 수 없습니다.')
        if item.data.get('purpose') != purpose or item.parent_id not in (None, target.id):
            raise HTTPException(422, '다른 용도나 다른 대상에 연결된 파일입니다.')
        if not storage_paths(item.id)[0].is_file():
            raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
        selected.append(item)
    return selected


def bind_selection(db, target, purpose, ids, user):
    selected = validate_selection(db, target, purpose, ids, user)
    for old in db.scalars(select(Record).where(Record.kind == ATTACHMENT, Record.parent_id == target.id)):
        if old.data.get('purpose') == purpose and old.id not in ids:
            old.parent_id = None
            old.ends = now()+ORPHAN_TTL  # Retain original upload time when detached.
    for item in selected:
        item.parent_id = target.id
    return selected


def bind_application_file(db, target, user):
    id = target.data.get('bankproof_id')
    return bind_selection(db, target, 'bankproof', [id] if id else [], user)


def bind_campaign_files(db, target, user):
    thumb = [target.data['thumbnail_id']] if target.data.get('thumbnail_id') else []
    details = target.data.get('detail_image_ids', [])
    alts = target.data.get('detail_alt_texts', [])
    if len(alts) != len(details) or any(not text.strip() for text in alts):
        raise HTTPException(422, '상세 이미지마다 대체 설명을 입력해 주세요.')
    if thumb and not target.data.get('thumbnail_alt_text', '').strip():
        raise HTTPException(422, '대표 사진의 대체 설명을 입력해 주세요.')
    validate_selection(db, target, 'thumbnail', thumb, user)
    validate_selection(db, target, 'detail', details, user)
    bind_selection(db, target, 'thumbnail', thumb, user)
    bind_selection(db, target, 'detail', details, user)


def validate_application_submission(db, target, user):
    if any(not target.data.get(key, '').strip() for key in ('settlement_bank', 'settlement_holder', 'settlement_account')) or not target.data.get('bankproof_id'):
        raise HTTPException(422, '정산 은행·예금주·계좌번호와 통장 사본을 확인해 주세요.')
    bind_application_file(db, target, user)


def validate_campaign_submission(db, target, user):
    if not target.data.get('thumbnail_id'):
        raise HTTPException(422, '대표 사진을 등록해 주세요.')
    bind_campaign_files(db, target, user)


def binding_matches(db, item):
    if not item.parent_id:
        return False
    target = db.get(Record, item.parent_id)
    if not target or target.owner_id != item.owner_id:
        return False
    if target.kind == 'application' and item.data['purpose'] == 'bankproof':
        return target.data.get('bankproof_id') == item.id
    if target.kind == 'campaign' and item.data['purpose'] == 'thumbnail':
        return target.data.get('thumbnail_id') == item.id
    if target.kind == 'campaign' and item.data['purpose'] == 'detail':
        return item.id in target.data.get('detail_image_ids', [])
    return False


def authorized_attachment(db, id, user):
    item = db.get(Record, id)
    if not item or item.kind != ATTACHMENT:
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    if item.owner_id != user.id and not (user.is_admin and binding_matches(db, item)):
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    return item


def file_response(db, id, user, original=False):
    item = authorized_attachment(db, id, user)
    if original and item.data['purpose'] != 'bankproof':
        raise HTTPException(404, '원본 파일을 찾을 수 없습니다.')
    path = storage_paths(item.id)[1 if original else 0]
    if not path.is_file():
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    filename = item.data['filename'] if original else item.data['filename'].rsplit('.', 1)[0]+'.png'
    media_type = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif', 'BMP': 'image/bmp'}[item.data['source_format']] if original else 'image/png'
    return FileResponse(path, filename=filename, media_type=media_type, content_disposition_type='attachment',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                                 'Content-Security-Policy': "default-src 'none'; sandbox"})


@router.get('/attachments/{id}')
def download(id: str, user=Depends(current_user), db=Depends(get_db)):
    return file_response(db, id, user)


@router.get('/attachments/{id}/original')
def download_original(id: str, user=Depends(current_user), db=Depends(get_db)):
    return file_response(db, id, user, original=True)


@router.get('/applications/{id}/attachments')
def application_files(id: str, user=Depends(current_user), db=Depends(get_db)):
    target = db.get(Record, id)
    if not target or target.kind != 'application' or (target.owner_id != user.id and not user.is_admin):
        raise HTTPException(404, '신청 자료를 찾을 수 없습니다.')
    records = db.scalars(select(Record).where(Record.kind == ATTACHMENT, Record.parent_id == id, Record.owner_id == target.owner_id))
    return {'application_id': target.id, 'items': [attachment_dto(item) for item in records if binding_matches(db, item)]}


@router.delete('/attachments/{id}')
def delete_attachment(id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    item = db.get(Record, id)
    if not item or item.kind != ATTACHMENT or item.owner_id != user.id:
        raise HTTPException(404, '첨부 파일을 찾을 수 없습니다.')
    if item.parent_id:
        raise HTTPException(409, '연결된 자료에서 파일 선택을 먼저 해제해 주세요.')
    stage_file_purge(db, [item.id], UPLOAD_ROOT)
    db.delete(item)
    db.commit()
    return {'message': '첨부 파일을 삭제했습니다.'}


def purge_user_uploads(db, user_id):
    # Caller must invoke BEFORE deleting the account's Record metadata.
    items = list(db.scalars(select(Record).where(Record.kind == ATTACHMENT, Record.owner_id == user_id)))
    stage_file_purge(db, [item.id for item in items], UPLOAD_ROOT)
    for item in items:
        db.delete(item)
