"""Shared correlation -> Agent -> HITL pipeline for MQTT and API triggers."""

import threading

from fastapi import FastAPI

from backend.app.llm_client import LLMUnavailable
from backend.app.schemas import Actor, AuditEntry, AuditEntryEvent

_PIPELINE_LOCK = threading.RLock()


def run_pipeline(app: FastAPI) -> None:
    """Evaluate pending signals, reason about them, then enforce HITL policy."""
    with _PIPELINE_LOCK:
        signals = app.state.window.evaluate()
        for signal in signals:
            try:
                result = app.state.agent.process(signal)
            except LLMUnavailable as exc:
                _audit_llm_failure(app, exc)
                raise
            app.state.hitl.handle_signals([result])


def _audit_llm_failure(app: FastAPI, error: LLMUnavailable) -> None:
    db = app.state.db
    entry = AuditEntry(
        id=db.next_id("aud"),
        timestamp=db.utc_now(),
        actor=Actor.SYSTEM,
        action="LLM_UNAVAILABLE",
        details=str(error),
    )
    db.insert_audit(entry)
    app.state.hub.publish(AuditEntryEvent(entry=entry))
