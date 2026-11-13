"""Shared inclusive Korea calendar-day filters for creation/action timestamps."""
from datetime import date, datetime, time, timedelta, timezone
import re

from fastapi import HTTPException

from .db import Record

KOREA = timezone(timedelta(hours=9))


def korea_date_bounds(start_date=None, end_date=None):
    def parse(value):
        if value is None:
            return None
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        return date.fromisoformat(value)
    try:
        start, end = parse(start_date), parse(end_date)
        if start and end and start > end:
            raise ValueError()
        lower = int(datetime.combine(start, time.min, KOREA).timestamp()) if start else None
        upper = int(datetime.combine(end+timedelta(days=1), time.min, KOREA).timestamp()) if end else None
    except (ValueError, OverflowError):
        raise HTTPException(422, '기간은 YYYY-MM-DD 형식이며 시작일이 종료일보다 늦을 수 없습니다.') from None
    return lower, upper


def filter_created(query, start_date=None, end_date=None, column=Record.created):
    lower, upper = korea_date_bounds(start_date, end_date)
    if lower is not None:
        query = query.where(column >= lower)
    if upper is not None:
        query = query.where(column < upper)
    return query
