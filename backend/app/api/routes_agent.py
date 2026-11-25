"""Live Agent Active/Bypassed control route."""

from typing import Any

from fastapi import APIRouter, Request

from backend.app.schemas import (
    Actor,
    AgentModeRequest,
    AuditEntry,
    AuditEntryEvent,
)

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent/mode")
def set_agent_mode(request: Request, body: AgentModeRequest) -> dict[str, Any]:
    agent = request.app.state.agent
    if agent.enabled == body.enabled:
        return {"ok": True, "enabled": body.enabled}

    agent.set_enabled(body.enabled)
    action = "AGENT_ACTIVATED" if body.enabled else "AGENT_BYPASSED"
    details = (
        "Watchdog reasoning and containment restored."
        if body.enabled
        else "Watchdog bypassed for control demo; attacks will go unmitigated."
    )
    db = request.app.state.db
    entry = AuditEntry(
        id=db.next_id("aud"),
        timestamp=db.utc_now(),
        actor=Actor.SYSTEM,
        action=action,
        details=details,
    )
    db.insert_audit(entry)
    request.app.state.hub.publish(AuditEntryEvent(entry=entry))
    return {"ok": True, "enabled": body.enabled}
