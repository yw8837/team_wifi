"""Operator-only published evaluation summaries. Never reads member conversations."""
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from .security import admin_user
from . import model_runtime, observability

router = APIRouter(prefix='/api/release/admin/assistant', tags=['assistant evaluation'])
SUMMARY = Path(__file__).with_name('assistant_evaluation.json')


@router.get('/evaluation')
def evaluation(actor=Depends(admin_user)):
    try:
        data=json.loads(SUMMARY.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not isinstance(data.get('runs'), list):
            raise ValueError()
    except (OSError, ValueError):
        raise HTTPException(503, '검증된 평가 요약을 불러오지 못했습니다. 다시 확인해 주세요.') from None
    return {**data, 'runtime': model_runtime.status(),
            'telemetry': {'status': observability.status(), 'delivery': observability.delivery_snapshot()}}
