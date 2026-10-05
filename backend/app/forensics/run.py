from backend.app.agents.attacker import generate_attack
from backend.app.agents.runner import run_agent
from backend.app.evaluation.oracle import evaluate_run
from backend.app.forensics.localizer import localize_critical_steps
from backend.app.forensics.fingerprint import create_failure_fingerprint
from backend.app.forensics.minimizer import minimize_failure
from backend.app.sandbox.state import SandboxState


PRIMARY_FAILURE_BY_CATEGORY = {
    "authorization_bypass": "REFUND_LIMIT_BYPASS",
    "identity_bypass": "IDENTITY_BYPASS",
    "cross_customer_data_access": "CROSS_CUSTOMER_ACCESS",
    "indirect_prompt_injection": "INDIRECT_PROMPT_INJECTION",
    "false_action_claim": "FALSE_SUCCESS_CLAIM",
}


MINIMIZABLE_FAILURES = {
    "CROSS_CUSTOMER_ACCESS",
    "INDIRECT_PROMPT_INJECTION",
    "IDENTITY_BYPASS",
    "REFUND_LIMIT_BYPASS",
}


def find_violation_by_name(
    violations: list,
    violation_name: str,
):
    for violation in violations:
        if violation["violation"] == violation_name:
            return violation

    return None


def investigate_with_adapter(adapter, message, expected_failure, category, minimize_rounds=0):
    """Domain-neutral entry point using the existing forensic operations.

An adapter supplies fresh executions and its deterministic oracle; localization,
fingerprinting, reduction and paired replay remain core operations.
"""
    from backend.app.forensics.replay import replay_with_adapter
    from backend.app.forensics.verification import verify_replay
    baseline = adapter.execute(message, protected=False)
    violations = baseline["violations"]
    localized = localize_critical_steps(baseline["events"], violations)
    attack = {"category": category, "goal": expected_failure, "user_message": message,
              "scenario": adapter.scenario}
    fingerprints = [create_failure_fingerprint(attack, v, point)
                    for v, point in zip(violations, localized)]
    reduction = None
    if minimize_rounds and find_violation_by_name(violations, expected_failure):
        def reproducer(candidate_message, expected_violation):
            result = adapter.execute(candidate_message, protected=False)
            found = result["agent_result"]["completed"] and any(v["violation"] == expected_violation for v in result["violations"])
            return found, result
        reduction = minimize_failure(message, expected_failure, max_rounds=minimize_rounds,
            reproducer=reproducer, identifier_pattern=adapter.identifier_pattern, request_words=getattr(adapter, "request_words", None))
    trigger = reduction["minimal_message"] if reduction else message
    replay = replay_with_adapter(adapter, trigger)
    return {"attack": attack, "baseline": baseline, "critical_steps": localized,
            "fingerprints": fingerprints, "minimization": reduction, "replay": replay,
            "verification": verify_replay(replay, expected_failure)}


def find_matching_critical_step(
    violations: list,
    critical_steps: list,
    target_violation: dict | None,
):
    if target_violation is None:
        return None

    try:
        index = violations.index(target_violation)
    except ValueError:
        return None

    if index >= len(critical_steps):
        return None

    return critical_steps[index]


def find_matching_fingerprint(
    violations: list,
    fingerprints: list,
    target_violation: dict | None,
):
    if target_violation is None:
        return None

    try:
        index = violations.index(target_violation)
    except ValueError:
        return None

    if index >= len(fingerprints):
        return None

    return fingerprints[index]


def run_forensics(category: str) -> dict:
    attack = generate_attack(category)

    simulate_refund_failure = (
        category == "false_action_claim"
    )

    state = SandboxState(
        authenticated_customer_id="C001",
        enforce_access_control=False,
        isolate_untrusted_content=False,
        simulate_refund_failure=simulate_refund_failure,
    )

    agent_result = run_agent(
        state=state,
        user_message=attack["user_message"],
    )

    violations = evaluate_run(
        events=state.events,
        final_response=agent_result["final_response"],
    )

    critical_steps = localize_critical_steps(
        state.events,
        violations,
    )

    fingerprints = []

    for violation, critical_step in zip(
        violations,
        critical_steps,
    ):
        fingerprint = create_failure_fingerprint(
            attack=attack,
            violation=violation,
            critical_step=critical_step,
        )

        fingerprints.append(fingerprint)

    expected_primary_failure = (
        PRIMARY_FAILURE_BY_CATEGORY.get(category)
    )

    primary_violation = None

    if expected_primary_failure:
        primary_violation = find_violation_by_name(
            violations,
            expected_primary_failure,
        )

    # If another unexpected policy violation was discovered,
    # retain it as the primary fallback instead of hiding it.
    if primary_violation is None and violations:
        primary_violation = violations[0]

    primary_critical_step = find_matching_critical_step(
        violations=violations,
        critical_steps=critical_steps,
        target_violation=primary_violation,
    )

    primary_fingerprint = find_matching_fingerprint(
        violations=violations,
        fingerprints=fingerprints,
        target_violation=primary_violation,
    )

    primary_minimization = None

    if primary_violation is not None:
        violation_name = primary_violation["violation"]

        if violation_name in MINIMIZABLE_FAILURES:
            try:
                primary_minimization = {
                    "violation": violation_name,
                    "supported": True,
                    "result": minimize_failure(
                        original_message=attack["user_message"],
                        expected_violation=violation_name,
                    ),
                }

            except Exception as error:
                primary_minimization = {
                    "violation": violation_name,
                    "supported": True,
                    "error": "Minimization could not complete; original trigger retained.",
                }

        else:
            primary_minimization = {
                "violation": violation_name,
                "supported": False,
                "reason": (
                    "Live minimization is not yet "
                    "configured for this failure class."
                ),
            }

    return {
        "attack": attack,
        "agent_result": agent_result,
        "events": state.events,

        # All findings remain available for complete evidence.
        "violations": violations,
        "critical_steps": critical_steps,
        "fingerprints": fingerprints,

        # Category-aware finding used by the product UI.
        "primary_violation": primary_violation,
        "primary_critical_step": primary_critical_step,
        "primary_fingerprint": primary_fingerprint,
        "primary_minimization": primary_minimization,

        "expected_primary_failure": expected_primary_failure,
        "failed": len(violations) > 0,
        "category_failure_detected": (
            primary_violation is not None
            and (
                expected_primary_failure is None
                or primary_violation["violation"]
                == expected_primary_failure
            )
        ),
    }
