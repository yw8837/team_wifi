"""Public retrieval relevance regressions; holdout questions are not evaluated here."""
import hashlib
import json
from pathlib import Path

from app import knowledge


def frozen_cases():
    path=Path(__file__).with_name('fixtures')/'assistant-evaluation.json'
    # Git checkouts may translate CRLF/LF; freeze every other gold byte.
    raw=path.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(raw).hexdigest()=='5660262f19d042d2dc9130cb875fa8cf304b9ffa617d401a9395b487b45684ac'
    # Retain the original Windows fixture hash as an additional provenance check.
    assert hashlib.sha256(raw.replace(b'\n',b'\r\n')).hexdigest()=='73d03184ced03cc8ab8e83c5356aa6d8787c4439ddec72979652d9f7dcd50f97'
    cases=json.loads(raw)['cases']
    return [case for case in cases if case['split']=='frozen']


def test_privacy_service_question_has_no_unrelated_product_evidence():
    documents=knowledge.retrieve('개인정보 없이 육아 도우미는 어떻게 이용하나요?')
    assert documents and documents[0].source_id=='guide:privacy-chat'
    assert {document.source_type for document in documents}=={'service_guide'}
    assert not any(document.source_id.startswith(('catalog:','analysis:')) for document in documents)
    assert '개인정보를 질문에 적지 마세요' in documents[0].text


def test_generic_use_words_do_not_admit_a_catalog():
    assert knowledge.retrieve('자료 정보를 어떻게 이용하나요?')==[]
    assert knowledge.retrieve('zzzzqxyv qxyvzzzz')==[]


def test_bottle_comparison_excludes_book_catalog():
    documents=knowledge.retrieve('젖병 용량과 소재, 젖꼭지 포함 수량 비교')
    ids={document.source_id for document in documents}
    assert 'catalog:doubleheart-bottles' in ids
    assert 'catalog:bluerabbit-books' not in ids


def test_frozen_retrieval_gold_recall_is_preserved():
    applicable=[case for case in frozen_cases() if case['retrieval_applicable']]
    assert len(frozen_cases())==30
    misses=[]
    for case in applicable:
        found={chunk.source_id for chunk in knowledge.retrieve(case['question'])}
        missing=set(case['gold_source_ids'])-found
        if missing:misses.append((case['id'],sorted(missing)))
    assert not misses,misses


def test_retrieval_does_not_change_generation_tokenizer_or_export_unapproved_types():
    assert {'이용하나요','이용','용하','하나','나요'} <= knowledge.tokens('이용하나요')
    assert {chunk.source_type for chunk in knowledge.corpus()} <= {'service_guide','catalog_comparison','reviewed_analysis'}
