"""Explainable discovery: declared interests, not transferred overseas customer scores."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field, field_validator
from .schemas import Strict

CATEGORIES = ('기저귀·물티슈', '수유·이유식', '목욕·위생', '외출·안전', '놀이·도서', '육아생활')
PREFERENCE = 'release_preference'
MIN_COHORT = 5
FOCUS = {
    'none': '상품 구성과 사용 조건을 나란히 살펴보세요.',
    'unit_price': '할인율보다 배송비를 더한 총액과 같은 단위당 금액을 비교하세요.',
    'composition': '구성품·용량·규격을 맞추고 별도 구매가 필요한 부속품을 확인하세요.',
    'care': '사용 연령·관리 방법·교체 안내와 교환·반품 조건을 확인하세요.',
}


class Preferences(Strict):
    categories: list[str] = Field(default_factory=list, max_length=3)
    priority: Literal['none', 'unit_price', 'composition', 'care'] = 'none'

    @field_validator('categories')
    @classmethod
    def valid_categories(cls, values):
        if len(set(values)) != len(values) or any(v not in CATEGORIES for v in values):
            raise ValueError('서로 다른 관심 카테고리를 최대 3개 선택하세요.')
        return values


def recommendations(entries, preferences, saved):
    preferred = set(preferences.categories)
    saved_categories = {e['category'] for e in entries if e['id'] in saved}
    candidates = []
    for position, entry in enumerate(entries):
        if entry['expires_at'] and datetime.fromisoformat(entry['expires_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
            continue
        reasons = []
        score = 0
        if entry['category'] in preferred:
            score = 2
            reasons.append('직접 고른 관심 카테고리')
        elif not preferred and entry['category'] in saved_categories:
            score = 1
            reasons.append('내가 저장한 육아템과 같은 카테고리')
        if not score:
            continue
        candidates.append((entry['id'] in saved, -score, position,
                           {**entry, 'saved': entry['id'] in saved, 'reasons': reasons}))
    candidates.sort(key=lambda row: row[:3])
    return {'items': [row[3] for row in candidates[:3]], 'focus': FOCUS[preferences.priority],
            'priority': preferences.priority, 'basis': 'preferences' if preferred else 'saved' if saved_categories else 'none'}


def masked_count(count):
    return count if count == 0 or count >= MIN_COHORT else None
