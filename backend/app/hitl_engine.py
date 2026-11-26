"""Human-in-the-loop enforcement for auto actions and pending approvals."""

from collections.abc import Iterable

from backend.app.agent import AgentResult
from backend.app.audit_db import AuditDB
from backend.app.containment_gateway import (
    ContainmentGateway,
    ContainmentGatewayError,
    TestContainmentGateway,
)
from backend.app.mqtt_client import MqttBridge
from backend.app.schemas import (
    Actor,
    ApprovalDecision,
    ApprovalRequest,
    AuditEntry,
    AuditEntryEvent,
    DeviceStatus,
    Incident,
    NewApprovalEvent,
    NewIncidentEvent,
)
from backend.app.stream_hub import StreamHub

AUTO_ACTION_FLAGS = {"rate_limited": True, "drop_sample": True}
DECOY_METRICS = {"active_traps": 1, "captured_payloads": 0}


class HitlEngine:
    """Applies low-risk actions and gates high-risk containment behind approval."""

    def __init__(
        self,
        db: AuditDB,
        bridge: MqttBridge,
        hub: StreamHub,
        gateway: ContainmentGateway | None = None,
    ) -> None:
        self._db = db
        self._bridge = bridge
        self._hub = hub
        self._gateway = gateway or TestContainmentGateway()

    def handle_signals(
        self, results: Iterable[AgentResult]
    ) -> list[ApprovalRequest]:
        """Enact each AgentResult; return the approvals that need a human."""
        approvals: list[ApprovalRequest] = []
        for result in results:
            incident = result.incident
            if incident.approval_status == "auto_executed":
                self._auto_execute(incident)
            elif incident.approval_status == "pending":
                approval = self._request_approval(incident)
                if approval is not None:
                    approvals.append(approval)
        return approvals

    def decide(
        self, approval_id: str, decision: ApprovalDecision
    ) -> ApprovalRequest | None:
        """Approve or reject a pending request; deciding twice is a no-op."""
        approval = next(
            (
                candidate
                for candidate in self._db.list_approvals()
                if candidate.id == approval_id
            ),
            None,
        )
        if approval is None or approval.status != "pending":
            return approval
        if decision == "approved":
            return self._approve(approval)
        return self._reject(approval)

    # --------------------------------- actions --------------------------------

    def _auto_execute(self, incident: Incident) -> None:
        target = incident.correlated_device_ids[0] if incident.correlated_device_ids else None
        if target is not None:
            self._bridge.set_device_status(
                target, DeviceStatus.WARNING, dict(AUTO_ACTION_FLAGS)
            )
        self._audit(
            Actor.AI_AGENT,
            "AUTO_ACTION_EXECUTED",
            (
                f"Auto-executed containment for {incident.id} "
                f"({incident.category.value}) on {target or 'no mapped device'}: "
                f"{incident.proposed_action}"
            ),
        )

    def _request_approval(self, incident: Incident) -> ApprovalRequest | None:
        if not incident.correlated_device_ids:
            return None
        approval = ApprovalRequest(
            id=self._db.next_id("apr"),
            incident_id=incident.id,
            created_at=self._db.utc_now(),
            target_device_id=incident.correlated_device_ids[0],
            recommended_action=incident.proposed_action,
            risk_summary=(
                f"{incident.severity} {incident.category.value}: "
                f"{incident.plain_english_explanation}"
            ),
            status="pending",
        )
        self._db.insert_approval(approval)
        self._hub.publish(NewApprovalEvent(approval=approval))
        self._audit(
            Actor.AI_AGENT,
            "HITL_APPROVAL_REQUESTED",
            (
                f"Approval requested for {incident.id}: "
                f"quarantine {approval.target_device_id} and activate Decoy Twin."
            ),
        )
        return approval

    # -------------------------------- decisions -------------------------------

    def _approve(self, approval: ApprovalRequest) -> ApprovalRequest | None:
        target = approval.target_device_id
        try:
            route = self._gateway.route_to_decoy(approval.incident_id)
        except ContainmentGatewayError as exc:
            self._audit(
                Actor.SYSTEM,
                "NETWORK_REROUTE_FAILED",
                f"Approval {approval.id} remains pending: {exc}",
            )
            raise

        self._bridge.publish_control(target, "QUARANTINE")
        self._bridge.publish_control("decoy_twin_01", "DECOY")
        self._bridge.set_device_status(target, DeviceStatus.QUARANTINED)
        self._bridge.set_device_status(
            "decoy_twin_01", DeviceStatus.DECOY, dict(DECOY_METRICS)
        )

        updated = self._db.update_approval(approval.id, {"status": "approved"})
        self._update_incident(approval.incident_id, "approved")
        if updated is not None:
            self._hub.publish(NewApprovalEvent(approval=updated))
        self._audit(
            Actor.HUMAN_OPERATOR,
            "APPROVAL_APPROVED",
            f"Human operator approved {approval.id} for {target}.",
        )
        self._audit(
            Actor.AI_AGENT,
            "DECOY_ACTIVATED",
            f"Decoy Twin activated for traffic from {target}.",
        )
        self._audit(
            Actor.SYSTEM,
            "NETWORK_REROUTE_APPLIED",
            (
                f"Gateway switched to {route.upstream}; disconnected "
                f"{route.disconnected_sessions} attacker session(s); "
                f"real_bytes={route.real_bytes}, decoy_bytes={route.decoy_bytes}."
            ),
        )
        return updated

    def _reject(self, approval: ApprovalRequest) -> ApprovalRequest | None:
        updated = self._db.update_approval(approval.id, {"status": "rejected"})
        self._update_incident(approval.incident_id, "rejected")
        if updated is not None:
            self._hub.publish(NewApprovalEvent(approval=updated))
        self._audit(
            Actor.HUMAN_OPERATOR,
            "APPROVAL_REJECTED",
            f"Human operator rejected {approval.id} for {approval.target_device_id}.",
        )
        return updated

    # -------------------------------- helpers ---------------------------------

    def _update_incident(self, incident_id: str, status: str) -> None:
        updated = self._db.update_incident(incident_id, {"approval_status": status})
        if updated is not None:
            self._hub.publish(NewIncidentEvent(incident=updated))

    def _audit(self, actor: Actor, action: str, details: str) -> AuditEntry:
        entry = AuditEntry(
            id=self._db.next_id("aud"),
            timestamp=self._db.utc_now(),
            actor=actor,
            action=action,
            details=details,
        )
        self._db.insert_audit(entry)
        self._hub.publish(AuditEntryEvent(entry=entry))
        return entry
