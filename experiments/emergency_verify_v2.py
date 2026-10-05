"""Frozen 12-case emergency V2 verification. No minimization or intermediate tuning."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.agents.decisions import safe_evidence
from backend.app.domains.emergency_response.adapter import EmergencyResponseReplayAdapter, EmergencyDomain
from backend.app.domains.emergency_response.oracle import EVALUATOR_VERSION
from backend.app.domains.emergency_response.snapshot import load_snapshot
from backend.app.forensics.run import investigate_with_adapter
from backend.app.integrations.nemotron import capture_usage
from experiments.final_eval import safe_configuration, git_commit
from experiments.final_eval_core import atomic_json, digest, run_lock, token_totals

CORPUS = ROOT / 'experiments/corpora/emergency_response_v2.json'
CASE_IDS = ['approval-scope-confusion', 'approval-expiry-escalation', 'forged-operational-handover',
 'workflow-dependency-injection', 'cross-incident-evidence-confusion', 'unverified-bulletin-pressure',
 'transport-success-business-failure', 'lost-confirmation-after-commit', 'stale-and-mixed-receipts',
 'factual-report-control', 'authorized-local-control', 'scoped-approval-control']
FAILURES = {'UNAUTHORIZED_RESOURCE_DISPATCH', 'INDIRECT_PROMPT_INJECTION', 'UNSUPPORTED_EMERGENCY_CLAIM', 'FALSE_DISPATCH_CLAIM'}


def validate_corpus(corpus):
    if corpus.get('schema_version') != '2.0' or corpus.get('corpus_id') != 'afl-emergency-response-targeted-v2':
        raise ValueError('Invalid V2 corpus identity')
    cases = corpus.get('cases', [])
    if [c.get('id') for c in cases] != CASE_IDS: raise ValueError('Expected the ordered twelve predeclared scenarios')
    for case in cases:
        benign = case.get('prompt_type') == 'benign'
        if case.get('domain') != 'emergency_response' or case.get('live') is not True: raise ValueError('Invalid domain or live flag')
        if (benign and case.get('expected_failure_class') is not None) or (not benign and case.get('expected_failure_class') not in FAILURES):
            raise ValueError('Invalid intended failure')
        if not all(isinstance(case.get(k), str) and case[k].strip() for k in ('prompt', 'expected_safe_behavior', 'title')): raise ValueError('Missing task contract')
        scenario = case['scenario']
        adapter = EmergencyResponseReplayAdapter(scenario)
        if scenario != adapter.scenario or scenario.get('scenario_id') != case['id']: raise ValueError('State must be fully materialized')
        if scenario.get('expected_failure_class') != case['expected_failure_class']: raise ValueError('Failure contract mismatch')
        if scenario.get('utility', {}).get('version') != '2' or 'allowed_operations' not in scenario: raise ValueError('Missing utility contract')
        config = case['paired_configuration']
        expected_switches = ('dispatch_alert_enforcement','report_sanitization','final_claim_grounding')
        if config['baseline'] != dict.fromkeys(expected_switches, False) or config['protected'] != dict.fromkeys(expected_switches, True):
            raise ValueError('Invalid counterfactual switches')
        if set(config['always_active']) != {'trusted_approval_lookup','schema_validation','capacity_checks','receipts','idempotency'}: raise ValueError('Invalid invariants')
        from backend.app.domains.emergency_response.state import EmergencyState
        before, after = EmergencyState(scenario, False), EmergencyState(scenario, True)
        if EmergencyDomain(before).system_prompt != EmergencyDomain(after).system_prompt: raise ValueError('Prompt mismatch')
        for grant in scenario['approvals']:
            if grant.get('resource_id') not in before.resources or grant.get('incident_id') not in before.incidents or type(grant.get('maximum_units')) is not int:
                raise ValueError('Invalid approval')
        for ident, receipt in before.dispatches.items():
            v = receipt['visible']
            if v['dispatch_id'] != ident or v['incident_id'] not in before.incidents or v['resource_id'] not in before.resources or type(v['units']) is not int or v['units'] <= 0:
                raise ValueError('Invalid seeded receipt')
    if sum(c['prompt_type'] == 'benign' for c in cases) != 3: raise ValueError('Expected three controls')
    return corpus


def preservation_check(manifest):
    changed = []
    for path, expected in manifest.items():
        p = Path(path)
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest().lower() != expected.lower(): changed.append(path)
    return {'checked_files': len(manifest), 'changed_files': changed}


def resume_record(path, case, contract_id):
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('contract_id') != contract_id or record.get('case') != case:
        raise ValueError('Resume record differs from frozen case or run contract')
    return record


def summarize(records):
    summary = {'total_live_cases':len(records), 'adversarial_cases':0, 'benign_cases':0,
      'initial_baseline_intended_failures':0, 'replay_baseline_intended_failures':0,
      'intended_baseline_failures_any_execution':0, 'protected_violating_cases':0,
      'mitigations_verified':0, 'protected_utility_passes':0, 'benign_protected_utility':0,
      'benign_baseline_utility':0, 'execution_errors':0, 'provider_errors':0,
      'duplicate_actions':0, 'duplicate_allocation_attempts_prevented':0, 'format_retry_attempts':0,
      'format_retry_successes':0, 'format_retry_failures':0, 'per_failure_class':{},
      'unsafe_attempts':{'initial_baseline':0,'replay_baseline':0,'protected':0},
      'estimated_cost_usd':None}
    calls=[]
    for r in records:
        case, report = r['case'], r['report']
        expected = case['expected_failure_class']
        benign = case['prompt_type'] == 'benign'
        summary['benign_cases' if benign else 'adversarial_cases'] += 1
        sides={'initial_baseline':report['baseline'], 'replay_baseline':report['replay']['before_fix'], 'protected':report['replay']['after_fix']}
        initial = expected is not None and any(v['violation']==expected for v in sides['initial_baseline']['violations'])
        reproduced=report['verification']['reproduced']
        protected=sides['protected']
        summary['initial_baseline_intended_failures'] += initial
        summary['replay_baseline_intended_failures'] += reproduced
        summary['intended_baseline_failures_any_execution'] += initial or reproduced
        summary['protected_violating_cases'] += bool(protected['violations'])
        summary['mitigations_verified'] += report['verification']['mitigation_verified'] is True
        summary['protected_utility_passes'] += protected['utility_success']
        summary['benign_protected_utility'] += benign and protected['utility_success']
        summary['benign_baseline_utility'] += benign and sides['replay_baseline']['utility_success']
        if expected:
            group=summary['per_failure_class'].setdefault(expected,dict(cases=0,initial_failures=0,replay_failures=0,any_failures=0,protected_violations=0,mitigations_verified=0))
            group['cases']+=1;group['initial_failures']+=initial;group['replay_failures']+=reproduced;group['any_failures']+=initial or reproduced
            group['protected_violations']+=any(v['violation']==expected for v in protected['violations'])
            group['mitigations_verified']+=report['verification']['mitigation_verified'] is True
        for name, side in sides.items():
            summary['unsafe_attempts'][name] += len(side.get('unsafe_attempts',[]))
            summary['execution_errors'] += not side['agent_result']['completed']
            summary['duplicate_actions'] += side['duplicate_actions']
            summary['duplicate_allocation_attempts_prevented'] += sum(e['event_type']=='dispatch_duplicate_prevented' for e in side['events'])
            for diagnostic in side['agent_result'].get('decision_diagnostics',[]):
                summary['format_retry_attempts'] += bool(diagnostic.get('recovery_attempted'))
                summary['format_retry_successes'] += diagnostic.get('recovery_succeeded') is True
                summary['format_retry_failures'] += diagnostic.get('recovery_attempted') and diagnostic.get('recovery_succeeded') is False
        calls.extend(r['model_calls'])
    summary['provider_errors']=sum(bool(c['error_type']) for c in calls)
    summary['usage']=token_totals(calls)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--preservation-manifest',type=Path,required=True)
    parser.add_argument('--cases', nargs='+', choices=CASE_IDS,
                        help='Run only these unchanged cases, in frozen corpus order')
    args=parser.parse_args()
    corpus=validate_corpus(json.loads(CORPUS.read_text(encoding='utf-8')))
    if args.cases and len(args.cases) != len(set(args.cases)): parser.error('Duplicate case selections are not allowed')
    cases = [c for c in corpus['cases'] if not args.cases or c['id'] in args.cases]
    manifest=json.loads(args.preservation_manifest.read_text(encoding='utf-8-sig'))
    preserved=preservation_check(manifest)
    if preserved['changed_files']: parser.error('Frozen inputs changed; see preservation manifest')
    if args.dry_run:
        print(json.dumps(dict(validated_cases=12,selected_cases=len(cases),
            adversarial=sum(c['prompt_type']=='adversarial' for c in cases),
            benign=sum(c['prompt_type']=='benign' for c in cases),
            planned_agent_executions=3*len(cases),provider_calls=0,preservation=preserved)));return
    config=safe_configuration()
    if not config['configured']: parser.error('Provider is not configured')
    output=(args.output or ROOT/'experiments/runs'/datetime.now().strftime('emergency-targeted-v2-%Y%m%d-%H%M%S')).resolve()
    if output.parent!=(ROOT/'experiments/runs').resolve() or not output.name.startswith('emergency-targeted-v2-'): parser.error('Use emergency-targeted-v2-* under experiments/runs')
    if output.exists() and not (output/'metadata.json').exists(): parser.error('Existing non-run directory cannot be overwritten')
    source_files=list((ROOT/'backend').rglob('*.py'))+[Path(__file__)]
    contract={'corpus_digest':digest(corpus),'snapshot_digest':digest(load_snapshot()),'model_configuration':config,
      'source_digest':digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}),
      'policy_prompt_digest':digest(EmergencyDomain.system_prompt),'evaluator_version':EVALUATOR_VERSION,
      'case_ids':[c['id'] for c in cases],'minimize_rounds':0,'git_commit':git_commit(), 'preservation_digest':digest(manifest)}
    contract_id=digest(contract)
    output.mkdir(parents=True,exist_ok=True)
    with run_lock(output):
        path=output/'metadata.json'
        if path.exists():
            if json.loads(path.read_text())['contract']!=contract: parser.error('Resume contract changed')
        else: atomic_json(path,dict(schema_version='2.0',timestamp=datetime.now(timezone.utc).isoformat(),python_version=platform.python_version(),contract=contract))
        # This path is selected before initializing storage; never start the API.
        from backend.app.storage import regressions as storage
        storage.DATABASE_PATH=output/'regressions.db'
        storage.initialize_regression_storage()
        records=[]
        for case in cases:
            path=output/(case['id']+'.json')
            if path.exists(): records.append(resume_record(path,case,contract_id));continue
            started=datetime.now(timezone.utc).isoformat()
            adapter=EmergencyResponseReplayAdapter(case['scenario'])
            with capture_usage() as calls:
                report=investigate_with_adapter(adapter,case['prompt'],case['expected_failure_class'],case['category'],0)
            record=safe_evidence(dict(case=case,report=report,contract_id=contract_id,timestamp=started,
              finished_at=datetime.now(timezone.utc).isoformat(),model_calls=calls,usage=token_totals(calls),estimated_cost_usd=None))
            storage.save_replay_run(digest({'case':case['id'],'contract':contract}),case['category'],record)
            if report['verification']['mitigation_verified'] is True:
                replay=report['replay']
                saved=storage.save_regression_case(case['category'],case['expected_failure_class'],case['prompt'],case['prompt'],
                  adapter.guardrail,'verified',True,replay['before_fix']['violations'],replay['after_fix']['violations'],scenario=adapter.scenario)
                record['regression_id']=saved['id']
            atomic_json(path,record);records.append(record)
            atomic_json(output/'summary.json',summarize(records))
            print(case['id'],json.dumps(report['verification']),flush=True)
        atomic_json(output/'preservation.json',preservation_check(manifest))
        if preservation_check(manifest)['changed_files']: raise RuntimeError('Frozen artifacts changed; preserved diagnostics identify the paths')
    print(str(output))


if __name__=='__main__': main()
