"""Shared correlation -> Agent -> HITL pipeline for MQTT and API triggers."""

from fastapi import FastAPI

from backend.app.llm_client import LLMUnavailable
from backend.app.schemas import Actor, AuditEntry, AuditEntryEvent


def run_pipeline(app: FastAPI) -> None:
    """Evaluate pending signals, reason about them, then enforce HITL policy."""
    signals = app.state.window.evaluate()
    if not signals:
        return

    try:
        results = []
        for signal in signals:
            try:
                results.append(app.state.agent.process(signal))
            except LLMUnavailable as exc:
                _audit_llm_failure(app, exc)
                raise
        app.state.hitl.handle_signals(results)
    finally:
        # Each simulated trigger is an independent attack. Clearing after a
        # consumed signal lets the next trigger correlate from a clean window,
        # including after an LLM failure that the operator retries.
        app.state.window.clear()


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
