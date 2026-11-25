"""Anomaly prefilter plus structured Sense -> Think -> Act -> Explain reasoning.

Reasoning is supplied by the injected LLM client: the direct Gemini API by default,
with an optional local OpenAI-compatible fallback.
"""

from dataclasses import asdict, dataclass

from backend.app.audit_db import AuditDB
from backend.app.correlation_window import Signal
from backend.app.guardrail import wrap_untrusted
from backend.app.llm_client import AgentDecision, LLMClient
from backend.app.mqtt_client import MqttBridge
from backend.app.schemas import (
    Actor,
    AuditEntry,
    AuditEntryEvent,
    DeviceStatus,
    Incident,
    NewIncidentEvent,
)
from backend.app.stream_hub import StreamHub


@dataclass(frozen=True)
class AgentResult:
    incident: Incident
    decision: AgentDecision | None


class Agent:
    """Turns correlation signals into persisted, explainable incidents."""

    def __init__(
        self,
        db: AuditDB,
        bridge: MqttBridge,
        hub: StreamHub,
        llm_client: LLMClient,
    ) -> None:
        self._db = db
        self._bridge = bridge
        self._hub = hub
        self._llm = llm_client
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def process(self, signal: Signal) -> AgentResult:
        if not self._enabled:
            return self._bypass(signal)

        decision = self._llm.reason(self._build_prompt(signal))
        incident = self._build_incident(signal, decision)
        self._persist_incident(incident)
        return AgentResult(incident=incident, decision=decision)

    # --------------------------------- active --------------------------------

    def _build_prompt(self, signal: Signal) -> str:
        untrusted = wrap_untrusted(asdict(signal), "correlation_window")
        return (
            "Analyse this detection and return the required JSON object.\n"
            "The deterministic assessment below is authoritative: do not "
            "contradict category, severity, risk_level or auto_execute.\n"
            f"category={signal.category.value}, severity={signal.severity}, "
            f"risk_level={signal.risk_level}, auto_execute={signal.auto_execute}.\n\n"
            f"{untrusted}"
        )

    def _build_incident(self, signal: Signal, decision: AgentDecision) -> Incident:
        return Incident(
            id=self._db.next_id("inc"),
            timestamp=self._db.utc_now(),
            severity=signal.severity,
            category=signal.category,
            title=decision.sense,
            plain_english_explanation=(
                f"{decision.think} {decision.explain}".strip()
            ),
            correlated_device_ids=list(signal.device_ids),
            prompt_injection_detected=signal.prompt_injection_detected,
            sanitized_excerpt=signal.sanitized_excerpt,
            proposed_action=decision.act,
            approval_status="auto_executed" if signal.auto_execute else "pending",
        )

    # -------------------------------- bypassed -------------------------------

    def _bypass(self, signal: Signal) -> AgentResult:
        label = signal.category.value.replace("_", " ")
        incident = Incident(
            id=self._db.next_id("inc"),
            timestamp=self._db.utc_now(),
            severity=signal.severity,
            category=signal.category,
            title=f"Unmitigated {label}",
            plain_english_explanation=(
                f"Attack ({signal.category.value}) succeeded while the Watchdog "
                "Agent was BYPASSED. No AI reasoning, containment or HITL gate "
                "was applied."
            ),
            correlated_device_ids=list(signal.device_ids),
            prompt_injection_detected=False,
            sanitized_excerpt=None,
            proposed_action="No containment executed — Watchdog Agent bypassed.",
            approval_status="rejected",
        )
        self._persist_incident(incident)
        self._audit(
            Actor.SYSTEM,
            "UNMITIGATED_BREACH",
            f"Attack ({signal.category.value}) succeeded while the Watchdog Agent was bypassed.",
        )
        known_ids = {device.id for device in self._bridge.device_snapshot()}
        for device_id in signal.device_ids:
            if device_id in known_ids:
                self._bridge.set_device_status(
                    device_id, DeviceStatus.WARNING, {"agent_bypassed": True}
                )
        return AgentResult(incident=incident, decision=None)

    # -------------------------------- helpers --------------------------------

    def _persist_incident(self, incident: Incident) -> None:
        self._db.insert_incident(incident)
        self._hub.publish(NewIncidentEvent(incident=incident))

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
