"""Private product inquiries for dormant commerce routes; public release stays closed."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import exists, select

from .attachments import dormant_only
from .db import Record, User, get_db, now
from .schemas import InquiryAnswer
from .security import current_user, optional_user, throttle

router = APIRouter(prefix='/api', dependencies=[Depends(dormant_only)])


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def campaign_for(db, id, user=None, public_required=False):
    item = db.get(Record, id)
    seller = db.get(User, item.owner_id) if item and item.kind == 'campaign' else None
    suspended = bool(seller and db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == seller.id)))
    visible = bool(not suspended and item and item.kind == 'campaign' and item.status in ('active', 'ended') and
                   item.data.get('published') and seller and not seller.deleted and seller.seller_status == 'approved')
    if not visible and (public_required or not user or not item or (not user.is_admin and user.id != item.owner_id)):
        raise HTTPException(404, '공개된 상품을 찾을 수 없습니다.')
    if not item or item.kind != 'campaign':
        raise HTTPException(404, '상품을 찾을 수 없습니다.')
    return item


def visible_questions(db, campaign_id, user):
    suspended = exists(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == User.id)).correlate(User)
    query = select(Record).join(User, User.id == Record.owner_id).where(
        Record.kind == 'question', Record.parent_id == campaign_id, Record.status == 'active',
        User.deleted.is_(False), ~suspended)
    if user:
        blocked = select(Record.parent_id).where(Record.kind == 'block', Record.owner_id == user.id)
        query = query.where(Record.owner_id.not_in(blocked))
    return query.order_by(Record.created.desc(), Record.id)


def may_read(item, campaign, user):
    return not item.data.get('private', False) or bool(user and (user.is_admin or user.id in (item.owner_id, campaign.owner_id)))


def question_dto(db, item, campaign, user):
    allowed = may_read(item, campaign, user)
    base = {'id': item.id, 'private': bool(item.data.get('private', False)), 'can_view': allowed,
            'status': 'answered' if item.data.get('answer') else 'pending', 'created_at': stamp(item.created)}
    if not allowed:
        # A private list entry exposes existence/status, never title/body/answer/author.
        return base
    author = db.get(User, item.owner_id)
    return {**base, 'title': item.data.get('title', '상품 문의'), 'body': item.data['body'],
            'author_id': item.owner_id, 'author_name': author.nickname,
            'answer': item.data.get('answer'), 'answered_at': item.data.get('answered_at'),
            'answer_updated_at': item.data.get('answer_updated_at'), 'revision': item.revision,
            'own': bool(user and user.id == item.owner_id),
            'can_answer': bool(user and user.id == campaign.owner_id and user.seller_status == 'approved')}


def list_questions(db, campaign_id, user=None, limit=10, offset=0):
    campaign = campaign_for(db, campaign_id, user)
    if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
        raise HTTPException(422, '목록 범위를 확인해 주세요.')
    rows = list(db.scalars(visible_questions(db, campaign.id, user).limit(limit+1).offset(offset)))
    return {'items': [question_dto(db, item, campaign, user) for item in rows[:limit]], 'has_more': len(rows)>limit}


def create_question(db, campaign_id, body, user):
    campaign = campaign_for(db, campaign_id, user, public_required=True)
    if db.scalar(select(Record.id).where(Record.kind == 'block', Record.owner_id == campaign.owner_id, Record.parent_id == user.id)):
        raise HTTPException(403, '이 상품에 문의를 작성할 수 없습니다.')
    item = Record(kind='question', owner_id=user.id, parent_id=campaign.id,
                  data={'title': body.title, 'body': body.body, 'private': body.private})
    db.add(item)
    db.commit()
    return question_dto(db, item, campaign, user)


def get_question(db, id, user):
    item = db.get(Record, id)
    if not item or item.kind != 'question' or item.status != 'active':
        raise HTTPException(404, '문의를 찾을 수 없습니다.')
    campaign = campaign_for(db, item.parent_id, user)
    visible = db.scalar(visible_questions(db, campaign.id, user).where(Record.id == id))
    if not visible or not may_read(item, campaign, user):
        raise HTTPException(404, '문의를 찾을 수 없습니다.')
    return item, campaign


@router.get('/questions/{id}')
def detail(id: str, user=Depends(optional_user), db=Depends(get_db)):
    item, campaign = get_question(db, id, user)
    return question_dto(db, item, campaign, user)


@router.put('/questions/{id}/answer')
def answer(id: str, body: InquiryAnswer, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    item, campaign = get_question(db, id, user)
    if campaign.owner_id != user.id or user.seller_status != 'approved':
        raise HTTPException(403, '해당 상품의 판매자만 답변을 등록·수정할 수 있습니다.')
    if item.revision != body.revision:
        raise HTTPException(409, '다른 화면에서 변경된 문의입니다. 최신 내용을 확인해 주세요.')
    action_time = stamp(now())
    item.data = {**item.data, 'answer': body.body, 'answered_at': item.data.get('answered_at') or action_time,
                 'answer_updated_at': action_time}
    item.revision += 1
    # Audit stores identity/times only, never a private title, question or answer quote.
    db.add(Record(kind='audit', owner_id=user.id, parent_id=item.id,
                  data={'action': 'inquiry-answer', 'question_id': item.id, 'campaign_id': campaign.id}))
    db.commit()
    return question_dto(db, item, campaign, user)
