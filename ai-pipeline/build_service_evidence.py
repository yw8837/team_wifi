"""Recompute service-facing aggregates; keep customer rows and IDs out of the app."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '_archive/legacy-project/data'


def build():
    summary = json.loads((ROOT / 'ai-pipeline/artifacts/summary.json').read_text('utf-8'))
    for source in summary['source_hashes']:
        path = DATA / source['path']
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != source['sha256']:
            raise ValueError('Source differs from audited analysis: ' + source['path'])
    with (DATA / 'raw/01_ecommerce_behavior/Ecommerce_Consumer_Behavior_Analysis_Data.csv').open(encoding='utf-8-sig', newline='') as f:
        consumers = list(csv.DictReader(f))
    sensitivity = Counter(r['Discount_Sensitivity'] for r in consumers)
    baby = [r for r in consumers if r['Purchase_Category'] == 'Baby Products']
    with (DATA / 'raw/04_uci_shoppers/online_shoppers_intention.csv').open(encoding='utf-8-sig', newline='') as f:
        sessions = list(csv.DictReader(f))
    purchased = [r for r in sessions if r['Revenue'].lower() == 'true']
    unpurchased = [r for r in sessions if r['Revenue'].lower() == 'false']
    if len(purchased) + len(unpurchased) != len(sessions):
        raise ValueError('Unexpected purchase label')
    intent = summary['intent']
    selected = intent['models'][intent['selected_model']]['test']
    return {
        'schema_version': 1,
        'source_hashes': {s['path']: s['sha256'] for s in summary['source_hashes']},
        'd1': {'rows': len(consumers), 'baby_rows': len(baby), 'discount_sensitivity': dict(sorted(sensitivity.items())),
               'baby_discount_sensitivity': dict(sorted(Counter(r['Discount_Sensitivity'] for r in baby).items())),
               'application': '가격 관심이 서로 달라 비교 기준을 직접 고르게 하고, 같은 계정의 관심 카테고리를 앱·웹에 적용합니다.',
               'limitation': '관측 표본의 요약입니다. 국내 육아 구매자를 대표하거나 할인 효과를 입증하지 않습니다.'},
        'd2': {'rows': summary['retail']['audit']['d2_rows'], 'matched_rows': summary['retail']['audit']['matched_rows'],
               'application': 'D3와 같은 거래를 합산하지 않습니다. 서비스의 저장·관심도 계정별 중복을 제거해 셉니다.'},
        'd3': {'rows': summary['retail']['audit']['d3_rows'], 'bundle_evaluation': summary['retail']['bundle_evaluation'],
               'application': '동시구매 분석의 집계 방법을 실제 앱의 함께 저장한 육아템에 적용합니다. 최소 5계정의 신호만 운영자에게 표시합니다.',
               'limitation': '과거 영국 상품을 육아템으로 치환하지 않습니다. 함께 저장은 구매 실적이나 수요 예측이 아닙니다.'},
        'd4': {'rows': len(sessions), 'purchased_sessions': len(purchased),
               'product_duration_median_seconds': {'purchased': median(float(r['ProductRelated_Duration']) for r in purchased),
                                                    'not_purchased': median(float(r['ProductRelated_Duration']) for r in unpurchased)},
               'selected_model': intent['selected_model'], 'test_auroc': selected['auroc'],
               'test_average_precision': selected['pr_auc_average_precision'],
               'application': '종료된 세션 특성을 현재 이용자의 구매 확률로 쓰지 않습니다. 비교 도움은 이용자가 선택해 열도록 제공합니다.',
               'automatic_behavior_scoring': False,
               'limitation': '구매한 뒤의 체류시간도 포함합니다. 실시간 구매 의도·인과 효과·한국 서비스 성능으로 해석할 수 없습니다.'},
        'sources': [{k: s[k] for k in ('id', 'name', 'url', 'rows')} for s in summary['sources']],
    }


if __name__ == '__main__':
    output = ROOT / 'backend/app/discovery_evidence.json'
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SERVICE_DATA_ANALYSIS_PASS: four source hashes, fresh D1/D4 aggregates, audited D2/D3 evidence')
