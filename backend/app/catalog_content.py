"""Dependency-free public content shared by the API and static web build."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

ORIGIN = 'https://moduyuga.onrender.com'


def checked_time(entry):
    return datetime.fromisoformat(entry['source_checked_at'].replace('Z', '+00:00')).astimezone(
        timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')


def active(entry):
    return not entry['expires_at'] or datetime.fromisoformat(entry['expires_at'].replace('Z', '+00:00')) > datetime.now(timezone.utc)


def guide_path(entry):
    return '/items/' + quote(entry['id'], safe='') + '.html'


def guide(entry):
    canonical = ORIGIN + guide_path(entry)
    return {
        'id': entry['id'], 'canonical_url': canonical, 'summary': entry['summary'],
        'comparison_notes': entry['comparison_notes'], 'source_checked_at': entry['source_checked_at'],
        'source_url': entry['source_url'], 'expired': not active(entry),
        'structured_data': {'@context': 'https://schema.org', '@type': 'Article',
            'headline': entry['title'], 'description': entry['summary'],
            'mainEntityOfPage': canonical, 'inLanguage': 'ko-KR',
            'author': {'@type': 'Organization', 'name': 'Team_Wifi'},
            'citation': entry['source_url'], 'dateModified': entry['source_checked_at']},
        'limitations': '공식 목록을 살펴보는 비교 안내입니다. 개별 모델의 가격·재고·호환성·KC 인증을 확인한 상품 제안이 아닙니다.',
    }
