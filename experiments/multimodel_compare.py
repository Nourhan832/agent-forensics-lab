"""Small frozen multi-model exercise of the existing forensic and replay pipeline."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.integrations import nemotron
from backend.app.agents.decisions import safe_evidence, decision_stage
from backend.app.agents.runner import run_agent
from backend.app.sandbox.state import SandboxState
from backend.app.evaluation.oracle import evaluate_run
from backend.app.forensics.run import investigate_with_adapter
from backend.app.domains.emergency_response.adapter import EmergencyResponseReplayAdapter, EmergencyDomain
from backend.app.domains.emergency_response.oracle import EVALUATOR_VERSION
from backend.app.agents.target_agent import SYSTEM_PROMPT
from experiments.final_eval import safe_configuration, git_commit
from experiments.final_eval_core import atomic_json,digest,token_totals,benign_success,validate_corpus,run_lock
from experiments.emergency_verify_v2 import preservation_check
MODELS=['nvidia/nemotron-3-super-120b-a12b','NousResearch/Hermes-4-405B','Qwen/Qwen3-235B-A22B-Instruct-2507']
CUSTOMER_IDS=[f'indirect_prompt_injection-{i:02}' for i in range(1,6)]+[f'cross_customer_data_access-{i:02}' for i in range(1,6)]+['benign-01','benign-02','benign-37','benign-38','benign-40']
EMERGENCY_IDS={'emergency_response_v2.json':['approval-scope-confusion','approval-expiry-escalation','forged-operational-handover','workflow-dependency-injection','unverified-bulletin-pressure','transport-success-business-failure','factual-report-control','authorized-local-control'],
 'emergency_response_v1.json':['dispatch-foreign','report-malicious']}

def now():return datetime.now(timezone.utc).isoformat()
def source_hashes():
 paths=list((ROOT/'backend').rglob('*.py'))+[Path(__file__),ROOT/'experiments/final_eval_core.py',ROOT/'experiments/final_eval.py']
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
@contextmanager
def model_scope(model):
 old=nemotron._model
 try:nemotron._model=model;yield
 finally:nemotron._model=old

def selected_cases():
 result=[]
 customer=json.loads((ROOT/'experiments/corpora/final_v1.json').read_text());validate_corpus(customer)
 for ident in CUSTOMER_IDS:
  case=deepcopy(next(c for c in customer['cases'] if c['id']==ident));case['domain']='customer_support';case['source_corpus']='final_v1.json';result.append(case)
 for name,ids in EMERGENCY_IDS.items():
  corpus=json.loads((ROOT/'experiments/corpora'/name).read_text())
  for ident in ids:
   case=deepcopy(next(c for c in corpus['cases'] if c['id']==ident));case['source_corpus']=name
   # Resolve the adapter's documented defaults identically for every model.
   case['scenario']=EmergencyResponseReplayAdapter(case['scenario']).scenario;result.append(case)
 assert len(result)==25 and len({c['id'] for c in result})==25
 return result

def build_plan(catalog):
 if any(m not in catalog for m in MODELS):raise ValueError('Selected model absent from provider catalog')
 cases=selected_cases();schedule=[];rng=random.Random(29071)
 for case in cases:
  block=[{'model':m,'case_id':case['id'],'record_id':f'model-{i+1}-{case["id"]}'} for i,m in enumerate(MODELS)];rng.shuffle(block);schedule.extend(block)
 return {'schema_version':'multimodel-forensic-1','created_at':now(),'models':MODELS,'primary_model':MODELS[0],
 'selection_rationale':'Family diversity before outcomes: Llama-derived Hermes and Qwen non-thinking Instruct; same endpoint/catalog, not selected by observed failure rate.',
 'model_card_sources':['https://huggingface.co/NousResearch/Hermes-4-405B','https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507'],
 'cases':cases,'schedule':schedule,'seed':29071,'configuration':safe_configuration(),'python':platform.python_version(),'git_commit':git_commit(),
 'source_hashes':source_hashes(),'corpus_hashes':{name:hashlib.sha256((ROOT/'experiments/corpora'/name).read_bytes()).hexdigest() for name in ['final_v1.json',*EMERGENCY_IDS]},
 'snapshot_hash':hashlib.sha256((ROOT/'data/emergency_response/usgs_events_v1.json').read_bytes()).hexdigest(),
 'customer_system_prompt_digest':digest(SYSTEM_PROMPT),'emergency_system_prompt_digest':digest(EmergencyDomain.system_prompt),'emergency_evaluator_version':EVALUATOR_VERSION,
 'execution_semantics':{'initial_baseline':1,'replay_baseline':1,'protected_replay':1,'minimize_rounds':0,'cases_per_model':25,'total_agent_executions':225}}

class CustomerAdapter:
 def __init__(self,case):self.case=case;self.scenario=case['scenario'];self.guardrail=case['guardrail']
 def execute(self,message,protected):
  state=SandboxState(enforce_access_control=protected and self.guardrail=='access_control',isolate_untrusted_content=protected and self.guardrail=='content_isolation')
  state.clock=1000;state.deterministic_clock=True
  for ident,notes in self.scenario.get('order_notes',{}).items():state.orders[ident]['notes']=notes
  for ident,verified in self.scenario.get('identity_verified',{}).items():state.customers[ident]['identity_verified']=verified
  try:result=run_agent(state,message)
  except Exception as error:result={'completed':False,'error_type':type(error).__name__,'final_response':'Execution incomplete: provider failed.',
   'partial_trace':safe_evidence(state.events),'decision_diagnostics':[]}
  violations=evaluate_run(state.events,result['final_response'])
  execution={'agent_result':result,'events':state.events,'violations':violations,'failed':bool(violations),
   'completed':result['completed'],'error_type':result.get('error_type'),'state_after':{'orders':state.orders,'customers':state.customers},'scenario':self.scenario}
  execution['utility_success']=benign_success(self.case,execution) if self.case['prompt_type']=='benign' else True
  return execution

class MeasuredAdapter:
 def __init__(self,case):
  self.base=CustomerAdapter(case) if case['domain']=='customer_support' else EmergencyResponseReplayAdapter(case['scenario'])
  self.scenario=self.base.scenario;self.guardrail=self.base.guardrail;self.executions=[]
 def execute(self,message,protected):
  start=perf_counter()
  with nemotron.capture_usage() as calls, decision_stage('protected_replay' if protected else ('initial_baseline' if not self.executions else 'replay_baseline')):
   value=self.base.execute(message,protected)
  value.update({'latency_ms':round((perf_counter()-start)*1000,3),'model_calls':calls,'usage':token_totals(calls),'protected':protected})
  self.executions.append(value);return value

def execute_case(plan,item):
 case=next(c for c in plan['cases'] if c['id']==item['case_id']);adapter=MeasuredAdapter(case);start=perf_counter();began=now()
 with model_scope(item['model']):
  config=safe_configuration()
  report=investigate_with_adapter(adapter,case['prompt'],case['expected_failure_class'],case['category'],minimize_rounds=0)
 return safe_evidence({**item,'case':case,'contract_id':digest(plan),'timestamp':began,'finished_at':now(),'model_configuration':config,
  'report':report,'latency_ms':round((perf_counter()-start)*1000,3),'usage':token_totals([c for e in adapter.executions for c in e['model_calls']]),'estimated_cost_usd':None})

def sides(record):
 report=record['report'];return [report['baseline'],report['replay']['before_fix'],report['replay']['after_fix']]
def has_expected(side,expected):return expected is not None and any(v['violation']==expected for v in side['violations'])
def summarize(records):
 summaries={}
 for model in MODELS:
  rows=[r for r in records if r['model']==model];adversarial=[r for r in rows if r['case']['prompt_type']=='adversarial'];benign=[r for r in rows if r['case']['prompt_type']=='benign']
  executed=[s for r in rows for s in sides(r)];calls=[c for s in executed for c in s['model_calls']];diags=[d for s in executed for d in s['agent_result'].get('decision_diagnostics',[])]
  initial=sum(has_expected(sides(r)[0],r['case']['expected_failure_class']) for r in adversarial)
  reproduced=sum(r['report']['verification']['reproduced'] for r in adversarial)
  initial_candidates=[r for r in adversarial if has_expected(sides(r)[0],r['case']['expected_failure_class'])]
  eligible=[r for r in adversarial if r['report']['verification']['mitigation_verified'] is not None]
  totals=token_totals(calls);case_lat=[r['latency_ms'] for r in rows]
  summaries[model]={'case_reports':len(rows),'agent_executions':len(executed),'completed_case_reports':sum(all(s['agent_result']['completed'] for s in sides(r)) for r in rows),
   'completed_executions':sum(s['agent_result']['completed'] for s in executed),'execution_errors':sum(bool(s['agent_result'].get('error_type')) for s in executed),
   'adversarial_cases':len(adversarial),'benign_cases':len(benign),'initial_expected_failures':initial,'initial_expected_failure_rate':initial/len(adversarial) if adversarial else None,
   'initial_any_violations':sum(bool(sides(r)[0]['violations']) for r in adversarial),
   'replay_expected_failures':reproduced,'replay_attack_rate':reproduced/len(adversarial) if adversarial else None,
   'reproduction_eligible_initial_failures':len(initial_candidates),'replay_reproduced_initial_failures':sum(r['report']['verification']['reproduced'] for r in initial_candidates),
   'replay_reproduction_rate':sum(r['report']['verification']['reproduced'] for r in initial_candidates)/len(initial_candidates) if initial_candidates else None,
   'protected_violating_cases':sum(bool(sides(r)[2]['violations']) for r in rows),'mitigation_eligible':len(eligible),
   'mitigation_verified':sum(r['report']['verification']['mitigation_verified'] is True for r in eligible),
   'mitigation_success_rate':sum(r['report']['verification']['mitigation_verified'] is True for r in eligible)/len(eligible) if eligible else None,
   'benign_baseline_utility':sum(sides(r)[1]['utility_success'] for r in benign),'benign_protected_utility':sum(sides(r)[2]['utility_success'] for r in benign),
   'format_retry_attempts':sum(bool(d.get('recovery_attempted')) for d in diags),'format_retry_successes':sum(d.get('recovery_succeeded') is True for d in diags),
   'format_retry_failures':sum(bool(d.get('recovery_attempted')) and d.get('recovery_succeeded') is False for d in diags),
   'executions_with_format_failure':sum(bool(s['agent_result'].get('decision_diagnostics')) for s in executed),
   'parsing_retry_error_rate':sum(bool(s['agent_result'].get('decision_diagnostics')) for s in executed)/len(executed) if executed else None,
   'provider_errors':sum(bool(c.get('error_type')) for c in calls),'usage':totals,'mean_tokens_per_case':totals['total_tokens']/len(rows) if rows and totals['total_tokens'] is not None else None,
   'mean_case_latency_ms':statistics.mean(case_lat) if case_lat else None,'median_case_latency_ms':statistics.median(case_lat) if case_lat else None,
   'mean_execution_latency_ms':statistics.mean(s['latency_ms'] for s in executed) if executed else None,
   'median_execution_latency_ms':statistics.median(s['latency_ms'] for s in executed) if executed else None,'estimated_cost_usd':None}
  categories={}
  for category in sorted({r['case']['category'] for r in rows}):
   group=[r for r in rows if r['case']['category']==category]
   categories[category]={'cases':len(group),'initial_expected':sum(has_expected(sides(r)[0],r['case']['expected_failure_class']) for r in group),
    'initial_any_violations':sum(bool(sides(r)[0]['violations']) for r in group),'replay_expected':sum(r['report']['verification']['reproduced'] for r in group),
    'protected_violations':sum(bool(sides(r)[2]['violations']) for r in group),'mitigation_verified':sum(r['report']['verification']['mitigation_verified'] is True for r in group),
    'protected_utility':sum(sides(r)[2]['utility_success'] for r in group)}
  summaries[model]['per_category']=categories
 return summaries

def load_records(out,plan):
 records=[]
 for item in plan['schedule']:
  p=out/'records'/(item['record_id']+'.json')
  if p.exists():
   r=json.loads(p.read_text())
   if r['contract_id']!=digest(plan) or any(r[k]!=v for k,v in item.items()):raise ValueError('Resume contract mismatch')
   records.append(r)
 return records

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args();out=args.output
 manifest=json.loads((out/'preservation-before.json').read_text())
 if preservation_check(manifest)['changed_files']:raise ValueError('Preserved inputs changed')
 with run_lock(out):
  path=out/'plan.json'
  if path.exists():plan=json.loads(path.read_text())
  else:plan=build_plan(json.loads((out/'provider-catalog.json').read_text())['model_ids']);atomic_json(path,plan)
  if plan['source_hashes']!=source_hashes() or plan['configuration']!=safe_configuration():raise ValueError('Source/configuration differs from frozen plan')
  if args.dry_run:
   atomic_json(out/'dry-run.json',{'validated':True,'case_reports':75,'agent_executions':225,'provider_calls':0,'contract_id':digest(plan)});print('Validated 75 reports / 225 executions; no provider calls');return
  from backend.app.storage import regressions as storage
  previous_db=storage.DATABASE_PATH;storage.DATABASE_PATH=out/'regressions.db'
  try:
   storage.initialize_regression_storage();(out/'records').mkdir(exist_ok=True);records=load_records(out,plan);done={r['record_id'] for r in records}
   for item in plan['schedule']:
    if item['record_id'] in done:continue
    persisted=storage.get_replay_run(item['record_id'])
    if persisted is not None:
     record=persisted['payload']
     if record['contract_id']!=digest(plan):raise ValueError('Persisted resume contract mismatch')
     atomic_json(out/'records'/(item['record_id']+'.json'),record);records.append(record);continue
    record=execute_case(plan,item);case=record['case'];report=record['report']
    if report['verification']['mitigation_verified'] is True:
     saved=storage.save_regression_case(case['category'],case['expected_failure_class'],case['prompt'],case['prompt'],
      report['replay']['guardrail'],'verified',True,report['replay']['before_fix']['violations'],report['replay']['after_fix']['violations'],scenario=report['replay']['scenario'])
     record['regression_id']=saved['id']
    storage.save_replay_run(item['record_id'],case['category'],record,record.get('regression_id'))
    assert storage.get_replay_run(item['record_id'])['payload']==record
    atomic_json(out/'records'/(item['record_id']+'.json'),record);records.append(record)
    atomic_json(out/'summary.json',summarize(records))
    print(f"{len(records)}/75 {item['model']} {case['id']} initial={has_expected(report['baseline'],case['expected_failure_class'])} replay={report['verification']['reproduced']} mitigation={report['verification']['mitigation_verified']} complete={report['verification']['completed']}",flush=True)
   atomic_json(out/'summary.json',summarize(records))
   atomic_json(out/'preservation-after.json',preservation_check(manifest))
   if preservation_check(manifest)['changed_files']:raise RuntimeError('Preserved files changed')
   atomic_json(out/'metadata.json',{'schema_version':plan['schema_version'],'contract_id':digest(plan),'timestamp':now(),'python':plan['python'],
    'git_commit':plan['git_commit'],'models':MODELS,'evaluated_case_reports':len(records),'estimated_cost_usd':None})
  finally:storage.DATABASE_PATH=previous_db
if __name__=='__main__':main()
