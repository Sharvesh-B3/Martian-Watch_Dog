from pathlib import Path
from types import SimpleNamespace

from backend.app.agent import AgentResult
from backend.app.audit_db import AuditDB
from backend.app.correlation_window import CorrelationWindow
from backend.app.hitl_engine import HitlEngine
from backend.app.mqtt_client import MqttBridge
from backend.app.schemas import Actor, AttackCategory, DeviceStatus, Incident
from backend.app.stream_hub import StreamHub


class RecordingClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))


def make_engine(tmp_path: Path) -> tuple[HitlEngine, AuditDB, MqttBridge, RecordingClient, StreamHub]:
    settings = SimpleNamespace(
        MQTT_HOST="127.0.0.1",
        MQTT_PORT=1883,
        MQTT_TOPIC_PREFIX="campus/lab1",
    )
    hub = StreamHub()
    bridge = MqttBridge(settings, hub, CorrelationWindow(60))  # type: ignore[arg-type]
    client = RecordingClient()
    bridge._client = client  # type: ignore[assignment]
    db = AuditDB(tmp_path / "watchdog.db")
    return HitlEngine(db, bridge, hub), db, bridge, client, hub


def make_result(
    db: AuditDB,
    *,
    approval_status: str,
    category: AttackCategory = AttackCategory.COORDINATED_INTRUSION,
    device_ids: tuple[str, ...] = ("smart_lock_01", "power_meter_01"),
    severity: str = "critical",
) -> AgentResult:
    incident = Incident(
        id=db.next_id("inc"),
        timestamp=db.utc_now(),
        severity=severity,
        category=category,
        title="t",
        plain_english_explanation="e",
        correlated_device_ids=list(device_ids),
        prompt_injection_detected=False,
        sanitized_excerpt=None,
        proposed_action="Quarantine and reroute attacker.",
        approval_status=approval_status,
    )
    db.insert_incident(incident)
    return AgentResult(incident=incident, decision=None)


def drain(hub: StreamHub) -> list[dict]:
    queue = hub.subscribe()
    events: list[dict] = []
    while not queue.empty():
        events.append(queue.get_nowait())
    hub.unsubscribe(queue)
    return events


def test_low_risk_auto_action_warns_source_and_audits(tmp_path: Path) -> None:
    engine, db, bridge, client, hub = make_engine(tmp_path)
    queue = hub.subscribe()
    result = make_result(
        db,
        approval_status="auto_executed",
        category=AttackCategory.SENSOR_SPOOFING,
        device_ids=("air_quality_01",),
        severity="medium",
    )

    assert engine.handle_signals([result]) == []

    device = next(
        device for device in bridge.device_snapshot() if device.id == "air_quality_01"
    )
    assert device.status == DeviceStatus.WARNING
    assert device.metrics["rate_limited"] is True
    assert device.metrics["drop_sample"] is True
    assert client.published == []
    assert any(entry.action == "AUTO_ACTION_EXECUTED" for entry in db.list_audit())
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    assert any(
        event["type"] == "device_update"
        and event["device"]["id"] == "air_quality_01"
        for event in events
    )
    assert any(
        event["type"] == "audit_entry"
        and event["entry"]["action"] == "AUTO_ACTION_EXECUTED"
        for event in events
    )


def test_high_risk_creates_pending_approval_for_first_device(tmp_path: Path) -> None:
    engine, db, _, _, hub = make_engine(tmp_path)
    queue = hub.subscribe()
    result = make_result(db, approval_status="pending")

    approvals = engine.handle_signals([result])

    assert len(approvals) == 1
    approval = approvals[0]
    assert approval.target_device_id == "smart_lock_01"
    assert approval.incident_id == result.incident.id
    assert approval.status == "pending"
    assert any(entry.action == "HITL_APPROVAL_REQUESTED" for entry in db.list_audit())
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    assert any(event["type"] == "new_approval" for event in events)


def test_approve_publishes_containment_and_activates_decoy(tmp_path: Path) -> None:
    engine, db, bridge, client, hub = make_engine(tmp_path)
    result = make_result(db, approval_status="pending")
    approval = engine.handle_signals([result])[0]
    queue = hub.subscribe()
    while not queue.empty():
        queue.get_nowait()

    updated = engine.decide(approval.id, "approved")

    assert updated is not None and updated.status == "approved"
    assert client.published == [
        ("campus/lab1/control/door_lock_01", '{"action": "QUARANTINE"}', 1),
        ("campus/lab1/control/door_lock_01", '{"action": "DECOY"}', 1),
    ]
    devices = {device.id: device for device in bridge.device_snapshot()}
    assert devices["smart_lock_01"].status == DeviceStatus.QUARANTINED
    assert devices["decoy_twin_01"].status == DeviceStatus.DECOY
    assert devices["decoy_twin_01"].metrics["active_traps"] == 1
    assert devices["decoy_twin_01"].metrics["captured_payloads"] == 0
    incident = next(item for item in db.list_incidents() if item.id == result.incident.id)
    assert incident.approval_status == "approved"
    audits = db.list_audit()
    assert any(
        entry.action == "APPROVAL_APPROVED"
        and entry.actor == Actor.HUMAN_OPERATOR
        for entry in audits
    )
    assert any(
        entry.action == "DECOY_ACTIVATED" and entry.actor == Actor.AI_AGENT
        for entry in audits
    )
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    hub.unsubscribe(queue)
    assert {"device_update", "new_approval", "new_incident", "audit_entry"} <= {
        event["type"] for event in events
    }


def test_reject_only_updates_records_and_audits(tmp_path: Path) -> None:
    engine, db, bridge, client, _ = make_engine(tmp_path)
    result = make_result(db, approval_status="pending")
    approval = engine.handle_signals([result])[0]
    bridge.set_device_status("smart_lock_01", DeviceStatus.WARNING)

    updated = engine.decide(approval.id, "rejected")

    assert updated is not None and updated.status == "rejected"
    assert client.published == []
    device = next(
        device for device in bridge.device_snapshot() if device.id == "smart_lock_01"
    )
    assert device.status == DeviceStatus.WARNING
    incident = next(item for item in db.list_incidents() if item.id == result.incident.id)
    assert incident.approval_status == "rejected"
    assert any(entry.action == "APPROVAL_REJECTED" for entry in db.list_audit())


def test_second_decision_is_a_no_op(tmp_path: Path) -> None:
    engine, db, _, client, _ = make_engine(tmp_path)
    result = make_result(db, approval_status="pending")
    approval = engine.handle_signals([result])[0]
    engine.decide(approval.id, "approved")

    again = engine.decide(approval.id, "rejected")

    assert again is not None and again.status == "approved"
    assert len(client.published) == 2
    assert sum(entry.action == "APPROVAL_REJECTED" for entry in db.list_audit()) == 0
