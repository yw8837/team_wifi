from datetime import datetime
from typing import Literal
import unicodedata
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Register(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    nickname: str = Field(min_length=2, max_length=30)
    track: Literal['buyer', 'seller']
    terms_accepted: bool
    privacy_accepted: bool
    marketing_opt_in: bool = False
    invite_code: str = Field(default='', max_length=200)
    age_confirmed: StrictBool | None = None
    adult_confirmed: StrictBool = False

class Login(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class ProfileUpdate(Strict):
    nickname: str = Field(min_length=2, max_length=30)

    @field_validator('nickname')
    @classmethod
    def visible_nickname(cls, value):
        if any(unicodedata.category(char) in ('Cc', 'Cf', 'Cs') for char in value):
            raise ValueError('닉네임에 줄바꿈이나 보이지 않는 제어 문자를 사용할 수 없습니다.')
        return value

class Password(Strict):
    password: str = Field(default='', max_length=128)
    reauth_token: str = Field(default='', max_length=200)

class ResetRequest(Strict):
    email: EmailStr

class Reset(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)

class Recover(Strict):
    email: EmailStr
    recovery_code: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)

class BetaApplication(Strict):
    brand_name: str = Field(min_length=2, max_length=80)
    brand_description: str = Field(min_length=5, max_length=1000)
    seller_terms_accepted: bool

class Application(Strict):
    settlement_bank: str = Field(default='', max_length=80)
    settlement_holder: str = Field(default='', max_length=80)
    settlement_account: str = Field(default='', max_length=80)
    bankproof_id: str | None = Field(default=None, min_length=36, max_length=36)
    business_name: str = Field(default='', max_length=100)
    business_number: str = Field(default='', max_length=20)
    representative: str = Field(default='', max_length=80)
    contact_phone: str = Field(default='', max_length=30)
    contact_email: str = Field(default='', max_length=254)
    business_address: str = Field(default='', max_length=300)
    return_address: str = Field(default='', max_length=300)
    commerce_number: str = Field(default='', max_length=100)
    commerce_exempt_reason: str = Field(default='', max_length=500)
    shipping_policy: str = Field(default='', max_length=2000)
    refund_policy: str = Field(default='', max_length=2000)
    brand_name: str = Field(default='', max_length=80)
    brand_description: str = Field(default='', max_length=1000)
    seller_terms_accepted: bool = False

class CampaignInput(Strict):
    thumbnail_id: str | None = Field(default=None, min_length=36, max_length=36)
    thumbnail_alt_text: str = Field(default='', max_length=300)
    detail_image_ids: list[str] = Field(default_factory=list, max_length=3)
    detail_alt_texts: list[str] = Field(default_factory=list, max_length=3)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=3000)
    category: str = Field(min_length=1, max_length=40)
    price: int = Field(gt=0, le=10_000_000)
    shipping_fee: int = Field(ge=0, le=100000)
    unit: str = Field(min_length=1, max_length=100)
    minimum_quantity: int = Field(ge=1, le=10000)
    stock: int = Field(ge=1, le=10000)
    ends_at: datetime

    @field_validator('ends_at')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError('시간대가 포함된 마감 시간을 입력해 주세요.')
        return value

class ReservationInput(Strict):
    quantity: int = Field(ge=1, le=20)
    revision: int = Field(ge=1)

class CouponInput(Strict):
    title: str = Field(min_length=2, max_length=100)
    amount: int = Field(gt=0, le=100000)
    min_spend: int = Field(ge=0, le=10_000_000)
    stock: int = Field(gt=0, le=10000)
    ends_at: datetime
    points_cost: int = Field(default=0, ge=0, le=100000)

class BodyInput(Strict):
    title: str = Field(default='상품 문의', min_length=1, max_length=120)
    private: StrictBool = False
    body: str = Field(min_length=1, max_length=1000)

class InquiryAnswer(Strict):
    body: str = Field(min_length=1, max_length=1000)
    revision: int = Field(default=1, ge=1, strict=True)


class ReportInput(Strict):
    target_type: Literal['question', 'campaign', 'user']
    target_id: str = Field(max_length=36)
    reason: str = Field(min_length=3, max_length=500)

class SellerReview(Strict):
    decision: Literal['approved', 'needs_changes', 'suspended']
    note: str = Field(min_length=2, max_length=500)

class CampaignReview(Strict):
    decision: Literal['active', 'rejected']
    note: str = Field(min_length=2, max_length=500)

class ResolveReport(Strict):
    action: Literal['hide', 'dismiss']

class OrderInput(Strict):
    user_id: str = Field(max_length=36)
    campaign_id: str = Field(max_length=36)
    external_reference: str = Field(min_length=3, max_length=100)
    eligible_amount: int = Field(gt=0, le=100_000_000)
    status: Literal['confirmed'] = 'confirmed'
