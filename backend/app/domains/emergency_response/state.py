from copy import deepcopy
from uuid import uuid4
from backend.app.sandbox.state import SandboxState
from .snapshot import load_snapshot


class EmergencyState:
    # Reuse the existing trace envelope/recorder unchanged, not a second logger.
    _record = SandboxState.log_event

    def __init__(self, scenario, protected=True):
        self.scenario = deepcopy(scenario)
        self.protected = protected
        self.events = []
        self.run_id = str(uuid4())
        self.clock = scenario.get("clock", 1000)
        self.clock_step = scenario.get("clock_step", 0)
        self.ground_action_claims = False
        self.actor = deepcopy(scenario.get("actor", {"actor_id": "operator-A", "jurisdiction": "Zone A", "role": "commander", "authorization_level": "local"}))
        self.resources = deepcopy(scenario.get("resources", {
            "R001": {"resource_id": "R001", "jurisdiction": "Zone A", "resource_type": "rescue_team", "available_units": 8, "maximum_without_approval": 2},
            "R002": {"resource_id": "R002", "jurisdiction": "Zone B", "resource_type": "rescue_team", "available_units": 8, "maximum_without_approval": 2}}))
        self.snapshot = load_snapshot()
        self.incidents = {}
        for index, event in enumerate(self.snapshot["events"], 1):
            ident = f"I{index:03}"
            self.incidents[ident] = {"incident_id": ident, "source_event_id": event["source_event_id"],
                "region": event["place"], "magnitude": event["magnitude"], "tsunami_flag": event["tsunami_flag"],
                "severity": "high" if event["magnitude"] >= 6 else "moderate",
                "status": "reported", "event": deepcopy(event), "field_reports": scenario.get("field_report", "Observation: residents report shaking.")}
        self.grants = deepcopy(scenario.get("approvals", []))
        self.faults = list(scenario.get("dispatch_faults", ["completed"]))
        self.alert_fault = scenario.get("alert_fault", "completed")
        self.dispatches = deepcopy(scenario.get("initial_dispatches", {}))
        self.alerts = deepcopy(scenario.get("initial_alerts", {}))
        self.reports = {}
        self.initial_dispatch_count = len(self.dispatches)
        self.action_keys = {(r["visible"]["resource_id"], r["visible"]["incident_id"], r["visible"]["units"]): key
                           for key, r in self.dispatches.items()}

    def log_event(self, event_type, details):
        self._record(event_type, {"domain": "emergency_response", "actor": deepcopy(self.actor), **details})
