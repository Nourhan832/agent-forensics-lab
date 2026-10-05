"""Offline validation for model scope, frozen selection and shared forensic metrics."""
from copy import deepcopy
import json
import pytest
from experiments import multimodel_compare as compare
from backend.app.agents import runner
from backend.app.integrations import nemotron
from experiments.final_eval_core import atomic_json

def test_frozen_balanced_selection():
 cases=compare.selected_cases()
 assert len(cases)==25
 assert sum(c['domain']=='customer_support' for c in cases)==15
 assert sum(c['prompt_type']=='benign' for c in cases)==7
 assert sum(c['category']=='emergency_dispatch' for c in cases)==3
 assert sum(c['category']=='emergency_injection' for c in cases)==3
 for case in cases:
  original=json.loads((compare.ROOT/'experiments/corpora'/case['source_corpus']).read_text())
  frozen=next(c for c in original['cases'] if c['id']==case['id'])
  assert case['prompt']==frozen['prompt']
  if case['domain']=='customer_support':assert case['scenario']==frozen['scenario']

def test_schedule_and_catalog():
 plan=compare.build_plan(compare.MODELS)
 assert len(plan['schedule'])==75
 for m in compare.MODELS:assert sum(i['model']==m for i in plan['schedule'])==25
 assert len({i['record_id'] for i in plan['schedule']})==75
 with pytest.raises(ValueError):compare.build_plan(compare.MODELS[:2])

def test_model_selection_does_not_change_credentials():
 before=(nemotron._model,nemotron._api_key,nemotron._base_url)
 with pytest.raises(RuntimeError):
  with compare.model_scope(compare.MODELS[1]):
   assert nemotron._model==compare.MODELS[1]
   raise RuntimeError('test')
 assert (nemotron._model,nemotron._api_key,nemotron._base_url)==before

@pytest.mark.parametrize('model',compare.MODELS)
def test_same_replay_pipeline_and_metrics(model,monkeypatch,tmp_path):
 plan=compare.build_plan(compare.MODELS)
 item=next(i for i in plan['schedule'] if i['case_id']=='cross_customer_data_access-01' and i['model']==model)
 decisions=[]
 for side in range(3):
  decisions.extend([{'action':'tool_call','tool':'lookup_order','arguments':{'order_id':'O2001'}},
    {'action':'respond','message':'O2001 is processing.' if side<2 else 'Access denied: this order belongs to another customer.'}])
 it=iter(decisions);monkeypatch.setattr(runner,'generate_response',lambda **kwargs:json.dumps(next(it)))
 r=compare.execute_case(plan,item)
 assert r['report']['verification']['mitigation_verified'] is True
 assert len(r['report']['critical_steps'])>0 and len(r['report']['fingerprints'])>0
 summary=compare.summarize([r])[model]
 assert summary['initial_expected_failures']==1
 assert summary['replay_reproduction_rate']==1
 assert summary['mitigation_success_rate']==1
 assert summary['protected_violating_cases']==0
 (tmp_path/'records').mkdir();atomic_json(tmp_path/'records'/(item['record_id']+'.json'),r)
 assert compare.load_records(tmp_path,plan)==[r]
 changed=deepcopy(plan);changed['seed']=0
 with pytest.raises(ValueError,match='Resume contract'):compare.load_records(tmp_path,changed)

def test_benign_notes_reach_real_sanitizer(monkeypatch):
 case=next(c for c in compare.selected_cases() if c['id']=='benign-37')
 seen=[]
 decisions=iter([{'action':'tool_call','tool':'lookup_order','arguments':{'order_id':'O3001'}},
  {'action':'respond','message':'O3001 delivery window is 9 AM to noon.'}])
 def response(**kwargs):seen.append(kwargs['user_prompt']);return json.dumps(next(decisions))
 monkeypatch.setattr(runner,'generate_response',response)
 value=compare.CustomerAdapter(case).execute(case['prompt'],True)
 assert value['utility_success']
 assert value['events'][0]['details']['content_isolated']
 assert 'sanitized_facts' in seen[1] and 'delivery_window' in seen[1]
