from app import admin_assistant, model_runtime
from test_public_release import public_mode


def test_evaluation_is_operator_only_and_contains_no_member_records(public_mode,monkeypatch):
    c,p,_=public_mode
    path='/api/release/admin/assistant/evaluation'
    assert c.get(path).status_code==401
    assert c.get(path,headers=p['buyer']['headers']).status_code==403
    monkeypatch.setattr(model_runtime,'status',lambda:{'available':False,'mode':'retrieval_only','model':None})
    response=c.get(path,headers=p['admin']['headers'])
    assert response.status_code==200,response.text
    data=response.json()
    assert data['schema_version']==1 and data['runs']
    assert all(run['report_sha256'] and run['source_kind']=='public_synthetic' for run in data['runs'])
    assert not data['telemetry']['delivery']['persistence_verified']
    assert 'buyer@example.com' not in response.text and 'operator@example.com' not in response.text


def test_missing_evidence_is_not_a_zero_or_success(public_mode,monkeypatch,tmp_path):
    c,p,_=public_mode
    monkeypatch.setattr(admin_assistant,'SUMMARY',tmp_path/'missing.json')
    assert c.get('/api/release/admin/assistant/evaluation',headers=p['admin']['headers']).status_code==503
