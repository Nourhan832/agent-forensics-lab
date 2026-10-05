"""UI/API integration tests; existing domain policy and forensic core stay untouched."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from backend.app.api import emergency
from backend.app.storage import regressions


def execution(failed=False, completed=True, utility=True):
    events=[{'event_type':'dispatch_result','details':{'resource_id':'R002','incident_id':'I001','units':3,'resource_jurisdiction':'Zone B','actor_jurisdiction':'Zone A'},'step':1}]
    violations=[{'violation':'UNAUTHORIZED_RESOURCE_DISPATCH','event_index':0,'severity':'critical','evidence':events[0]['details']}] if failed else []
    return {'agent_result':{'completed':completed,'final_response':'Simulated outcome'},'events':events,'violations':violations,'failed':failed,'utility_success':utility,'duplicate_actions':0}


def stub(monkeypatch, utility=True, completed=True):
    monkeypatch.setattr(emergency.EmergencyResponseReplayAdapter,'execute',lambda self,message,protected: execution(not protected, completed, utility if protected else True))


def test_domain_catalog_and_customer_defaults(client):
    assert len(client.get('/api/categories').json()['categories'])==4
    categories=client.get('/api/categories?domain=emergency_response').json()['categories']
    assert {c['id'] for c in categories}==set(emergency.CATEGORIES)
    assert all(c['replay_supported'] for c in categories)
    assert client.get('/api/categories?domain=unknown').status_code==400


@pytest.mark.parametrize('category', emergency.CATEGORIES)
def test_frozen_investigation_returns_shared_ui_contract(client,monkeypatch,category):
    stub(monkeypatch)
    result=client.post('/api/investigate/'+category).json()['result']
    assert result['domain']=='emergency_response'
    assert result['attack']['scenario']==emergency.frozen_case(category)['scenario']
    assert result['attack']['user_message']==emergency.frozen_case(category)['prompt']
    assert result['primary_fingerprint']['fingerprint_id']
    assert result['primary_minimization']['supported'] is False


@pytest.mark.parametrize('utility,completed,verified',[(True,True,True),(False,True,False),(True,False,False)])
def test_emergency_receipt_requires_utility_and_completion(client,monkeypatch,utility,completed,verified):
    stub(monkeypatch,utility,completed)
    case=emergency.frozen_case('emergency_dispatch')
    payload=client.post('/api/replay/emergency_dispatch',json={'message':case['prompt'],'scenario':case['scenario']}).json()
    assert payload['verification']['mitigation_verified'] is verified
    assert regressions.get_replay_run(payload['replay_id'])


def test_arbitrary_emergency_fixture_rejected_before_execution(client,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('must not execute')
    monkeypatch.setattr(emergency.EmergencyResponseReplayAdapter,'execute',forbidden)
    altered=deepcopy(emergency.frozen_case('emergency_dispatch')['scenario']);altered['approvals']=[]
    assert client.post('/api/replay/emergency_dispatch',json={'message':'Allocate','scenario':altered}).status_code==422


def test_emergency_regression_persists_scenario_and_reruns(client,monkeypatch):
    stub(monkeypatch)
    case=emergency.frozen_case('emergency_dispatch')
    replay=client.post('/api/replay/emergency_dispatch',json={'message':case['prompt'],'scenario':case['scenario']}).json()
    request={'category':'emergency_dispatch','failure_class':'UNAUTHORIZED_RESOURCE_DISPATCH','minimal_trigger':case['prompt'], 'guardrail':emergency.GUARDRAIL,'mitigation_verified':True,'before_violations':['UNAUTHORIZED_RESOURCE_DISPATCH'],'after_violations':[],'replay_id':replay['replay_id']}
    saved=client.post('/api/regressions',json=request).json()['regression']
    assert saved['domain']=='emergency_response' and saved['display_id']==f"AFL-E-{saved['id']}"
    assert saved['scenario']==case['scenario']
    assert client.post(f"/api/regressions/{saved['id']}/rerun").json()['verification']['mitigation_verified']
    assert client.get('/api/regressions').json()['regressions'][0]['domain']=='emergency_response'
    assert len(client.get(f"/api/regressions/{saved['id']}/report").json()['replay_runs'])==2


def test_domain_annotation_does_not_rewrite_customer_identity():
    row={'id':3,'category':'cross_customer_data_access'}
    assert emergency.annotate(row)=={**row,'domain':'customer_support','display_id':'AFL-3'}
    assert row=={'id':3,'category':'cross_customer_data_access'}


def test_snapshot_panel_matches_frozen_source_and_evidence_labels():
    html=Path('frontend/index.html').read_text(encoding='utf-8')
    snapshot=json.loads(Path('data/emergency_response/usgs_events_v1.json').read_text())['events'][0]
    assert snapshot['source_event_id'] in html and snapshot['place'] in html
    assert 'OPERATIONAL ACTIONS: SIMULATED' in html
    for phrase in ('29/30','29/29','28/30','28/28','8/9','8/8','1/2','1/1','3/3','9/10','0/10','SUPPORTING EVIDENCE','CONTROLLED BENCHMARK'):
        assert phrase in html


def test_investigation_cards_share_the_correct_grid():
    from html.parser import HTMLParser
    class Collector(HTMLParser):
        def __init__(self):
            super().__init__(); self.stack=[]; self.cards=[]
        def handle_starttag(self,tag,attrs):
            attributes=dict(attrs)
            if 'data-category' in attributes:
                assert any('investigation-grid' in a.get('class','') for _,a in self.stack)
                self.cards.append(attributes['data-category'])
            if tag not in {'meta','link','br','input','img','hr'}:
                self.stack.append((tag,attributes))
        def handle_endtag(self,tag):
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:
                    self.stack=self.stack[:i];break
    collector=Collector();collector.feed(Path('frontend/index.html').read_text(encoding='utf-8'))
    assert len(collector.cards)==8
    assert set(emergency.CATEGORIES) <= set(collector.cards)
