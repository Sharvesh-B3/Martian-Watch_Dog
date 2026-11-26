"""Incident, audit-log and simulation-trigger routes."""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.app.containment_gateway import ContainmentGatewayError
from backend.app.llm_client import LLMUnavailable
from backend.app.pipeline import run_pipeline
from backend.app.schemas import Actor, AuditEntry, AuditEntryEvent, TriggerRequest
from sim.attacks.scenarios import build_direct_frames, build_trigger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["incidents"])


@router.get("/incidents")
def list_incidents(request: Request) -> list[Any]:
    return request.app.state.db.list_incidents()


@router.get("/audit-log")
def list_audit_log(request: Request) -> list[Any]:
    return request.app.state.db.list_audit()


@router.post("/sim/trigger")
def trigger_sim_attack(request: Request, body: TriggerRequest) -> Any:
    """Publish attack telemetry, then run the full detection pipeline."""
    trigger = build_trigger(body.attack_type)
    try:
        request.app.state.bridge.publish_telemetry("redteam/trigger", trigger)
    except Exception as exc:
        logger.warning("MQTT scenario trigger failed: %s", exc)

    scenario_id = str(trigger["scenario_id"])
    for suffix, payload in build_direct_frames(
        body.attack_type,
        scenario_id=scenario_id,
        timestamp=str(trigger["timestamp"]),
    ):
        try:
            request.app.state.bridge.publish_telemetry(suffix, payload)
        except Exception as exc:  # broker may be down; in-process path still runs
            logger.warning("MQTT publish failed for %s: %s", suffix, exc)
        prefix = request.app.state.settings.MQTT_TOPIC_PREFIX.rstrip("/")
        request.app.state.bridge.handle_payload(f"{prefix}/{suffix}", payload)

    try:
        run_pipeline(request.app)
    except LLMUnavailable as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    return {"ok": True, "triggered": body.attack_type}


@router.post("/sim/reset")
def reset_sim_lab(request: Request) -> dict[str, Any]:
    """Restore devices, held attacks and the gateway route to baseline."""
    request.app.state.window.clear()
    request.app.state.bridge.reset_devices()
    request.app.state.bridge.publish_lab_reset()
    try:
        request.app.state.gateway.reset_to_real()
    except ContainmentGatewayError as exc:
        logger.warning("Lab reset could not confirm gateway route: %s", exc)

    db = request.app.state.db
    entry = AuditEntry(
        id=db.next_id("aud"),
        timestamp=db.utc_now(),
        actor=Actor.SYSTEM,
        action="LAB_RESET",
        details="Operator reset restored devices and network route to baseline.",
    )
    db.insert_audit(entry)
    request.app.state.hub.publish(AuditEntryEvent(entry=entry))
    return {"ok": True, "reset": True}
