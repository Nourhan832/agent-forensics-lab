"""Execute judge-facing UI state transitions against the real script and catalogs."""
import json
import shutil
import subprocess

import pytest

from backend.app.api.main import CATEGORIES
from backend.app.api.emergency import CATEGORIES as EMERGENCY_CATEGORIES


@pytest.mark.parametrize('scenario', [
    'verified_customer', 'verified_emergency', 'not_reproduced', 'other_failure',
    'protected_violation', 'incomplete_before', 'incomplete_after',
    'contradictory_receipt', 'saved_replay', 'eligibility', 'severity', 'readiness',
    'export', 'last_run', 'load_error', 'investigation_error', 'replay_error', 'save_error',
    'replay_running', 'save_running', 'rerun_incomplete', 'rerun_not_reproduced',
])
def test_judge_facing_frontend_state(scenario):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node required for executable frontend state tests')
    catalogs = {domain: [dict(id=key, severity=value[1], replay_supported=True)
                         for key, value in definitions.items()]
                for domain, definitions in [('customer_support', CATEGORIES),
                                            ('emergency_response', EMERGENCY_CATEGORIES)]}
    result = subprocess.run([node, 'tests/frontend_state.cjs', scenario],
                            input=json.dumps(catalogs), text=True,
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
