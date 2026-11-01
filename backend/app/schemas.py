from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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

class Login(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class Password(Strict):
    password: str = Field(min_length=1, max_length=128)

class ResetRequest(Strict):
    email: EmailStr

class Reset(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)

class Application(Strict):
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
    body: str = Field(min_length=1, max_length=1000)

class ReportInput(Strict):
    target_type: Literal['question', 'campaign']
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
