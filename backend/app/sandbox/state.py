from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from .customers import CUSTOMERS
from .orders import ORDERS


class SandboxState:
    def __init__(
        self,
        authenticated_customer_id: str = "C001",
        enforce_access_control: bool = False,
        isolate_untrusted_content: bool = False,
        simulate_refund_failure: bool = False,
    ):
        self.customers = deepcopy(CUSTOMERS)
        self.orders = deepcopy(ORDERS)
        self.events = []
        self.session_id = "session-1"
        self.clock = datetime.now(timezone.utc).timestamp()
        self.clock_step = 0
        self.deterministic_clock = False
        self.verification_evidence = None
        self.enforce_identity_verification = True
        self.ground_action_claims = True
        self.refund_faults = []
        self.action_results = {}
        self.action_keys = {}
        self.request_prefix = "request"
        self.scenario = {}
        self.run_id = str(uuid4())

        self.authenticated_customer_id = (
            authenticated_customer_id
        )

        self.enforce_access_control = (
            enforce_access_control
        )

        self.isolate_untrusted_content = (
            isolate_untrusted_content
        )

        self.simulate_refund_failure = (
            simulate_refund_failure
        )

    def log_event(
        self,
        event_type: str,
        details: dict,
    ):
        self.events.append(
            {
                "schema_version": "1.0",
                "run_id": self.run_id,
                "sequence": len(self.events),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "details": details,
            }
        )
