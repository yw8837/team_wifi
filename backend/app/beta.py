"""Closed-beta access and recovery; never claim email ownership verification."""
import secrets
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from .db import Record, Token, now
from .security import token_digest


def redeem_invite(db, raw):
    if not raw:
        raise HTTPException(422, '비공개 베타 참여코드를 입력해 주세요.')
    invitation = db.scalar(select(Record).where(
        Record.kind == 'beta_invite', Record.unique_key == token_digest(raw),
        Record.status == 'active', Record.ends > now()))
    if not invitation:
        raise HTTPException(400, '사용할 수 없거나 만료된 참여코드입니다.')
    changed = db.execute(update(Record).where(
        Record.id == invitation.id, Record.status == 'active', Record.ends > now()
    ).values(status='used')).rowcount
    if changed != 1:
        raise HTTPException(409, '이미 사용한 참여코드입니다.')


def recovery_code(db, user):
    db.execute(delete(Token).where(Token.user_id == user.id, Token.kind == 'recovery'))
    raw = secrets.token_urlsafe(32)
    db.add(Token(digest=token_digest(raw), user_id=user.id, kind='recovery', expires=now()+90*86400))
    return raw


def virtual_application(brand_name, brand_description, accepted):
    return dict(business_name='베타 가상 판매처', business_number='1234567891',
                representative='베타 운영', contact_phone='01000000000',
                contact_email='beta@example.com', business_address='실제 주소 수집하지 않음',
                return_address='실제 반품 없음', commerce_number='', commerce_exempt_reason='실거래 없는 비공개 베타',
                shipping_policy='시험 참여입니다. 상품은 배송되지 않습니다.',
                refund_policy='실제 결제가 없어 환불은 발생하지 않습니다. 참여를 철회할 수 있습니다.',
                brand_name=brand_name, brand_description=brand_description, seller_terms_accepted=accepted)
