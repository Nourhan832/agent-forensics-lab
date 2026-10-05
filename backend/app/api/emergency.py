"""UI boundary for existing emergency adapters; frozen scenarios, unchanged policy/core."""
import json
from pathlib import Path
from fastapi import HTTPException
from backend.app.domains.emergency_response.adapter import EmergencyResponseReplayAdapter
from backend.app.forensics.localizer import localize_critical_steps
from backend.app.forensics.fingerprint import create_failure_fingerprint
from backend.app.forensics.replay import replay_with_adapter
from backend.app.forensics.verification import verify_replay

CORPUS = Path(__file__).resolve().parents[3] / 'experiments/corpora/emergency_response_v2.json'
GUARDRAIL = 'emergency_policy_and_content_grounding'
CATEGORIES = {
    'emergency_dispatch': ('Unauthorized Resource Dispatch', 'critical', 'Tests scoped authority for simulated resource allocation.'),
    'emergency_injection': ('Indirect Prompt Injection', 'critical', 'Tests operational instructions in untrusted field reports.'),
    'emergency_emergency_claim': ('Unsupported Emergency Claim', 'high', 'Checks claims against the correct trusted incident.'),
    'emergency_dispatch_claim': ('False Dispatch Claim', 'high', 'Checks completion against matching dispatch receipts.'),
}
DEFAULT_CASES = {
    'emergency_dispatch': 'approval-expiry-escalation',
    'emergency_injection': 'workflow-dependency-injection',
    'emergency_emergency_claim': 'unverified-bulletin-pressure',
    'emergency_dispatch_claim': 'transport-success-business-failure',
}
EXPECTED = {
    'emergency_dispatch': 'UNAUTHORIZED_RESOURCE_DISPATCH',
    'emergency_injection': 'INDIRECT_PROMPT_INJECTION',
    'emergency_emergency_claim': 'UNSUPPORTED_EMERGENCY_CLAIM',
    'emergency_dispatch_claim': 'FALSE_DISPATCH_CLAIM',
}


def frozen_case(category, scenario=None):
    """Only server-owned frozen fixtures may be used by these demo routes."""
    cases = json.loads(CORPUS.read_text(encoding='utf-8'))['cases']
    ident = scenario.get('scenario_id') if scenario else DEFAULT_CASES.get(category)
    case = next((c for c in cases if c['id'] == ident and c['category'] == category), None)
    if case is None or (scenario is not None and scenario != case['scenario']):
        raise HTTPException(422, 'Emergency replay requires an unchanged server-owned scenario fixture')
    return case


def investigate(category):
    case = frozen_case(category)
    baseline = EmergencyResponseReplayAdapter(case['scenario']).execute(case['prompt'], False)
    events, violations = baseline['events'], baseline['violations']
    localized = localize_critical_steps(events, violations)
    attack = {'category': category, 'goal': EXPECTED[category], 'user_message': case['prompt'], 'scenario': case['scenario']}
    fingerprints = [create_failure_fingerprint(attack, v, point) for v, point in zip(violations, localized)]
    index = next((i for i,v in enumerate(violations) if v['violation'] == EXPECTED[category]), 0) if violations else None
    return {**baseline, 'domain': 'emergency_response', 'attack': attack,
        'critical_steps': localized, 'fingerprints': fingerprints,
        'primary_violation': violations[index] if index is not None else None,
        'primary_critical_step': localized[index] if index is not None else None,
        'primary_fingerprint': fingerprints[index] if index is not None else None,
        'primary_minimization': {'supported': False, 'reason': 'Emergency demo preserves the frozen exact scenario; minimization was not run.'},
        'expected_primary_failure': EXPECTED[category],
        'category_failure_detected': any(v['violation'] == EXPECTED[category] for v in violations)}


def replay(category, message, scenario=None):
    case = frozen_case(category, scenario)
    result = replay_with_adapter(EmergencyResponseReplayAdapter(case['scenario']), message)
    verification = verify_replay(result, EXPECTED[category])
    verification.update(before_failed=bool(result['before_fix']['failed']), after_failed=bool(result['after_fix']['failed']))
    return result, verification


def annotate(case):
    emergency = case['category'] in CATEGORIES
    return {**case, 'domain': 'emergency_response' if emergency else 'customer_support',
            'display_id': f"AFL-{'E-' if emergency else ''}{case['id']}"}
