from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent import Agent
from backend.app.api.routes_agent import router as agent_router
from backend.app.api.routes_approvals import router as approvals_router
from backend.app.api.routes_incidents import router as incidents_router
from backend.app.api.routes_stream import router as stream_router
from backend.app.audit_db import AuditDB
from backend.app.correlation_window import CorrelationWindow
from backend.app.hitl_engine import HitlEngine
from backend.app.llm_client import AgentDecision, LLMUnavailable
from backend.app.mqtt_client import MqttBridge
from backend.app.stream_hub import StreamHub


class RecordingClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))


class FakeLLM:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def reason(self, prompt: str) -> AgentDecision:
        if self.error is not None:
            raise self.error
        return AgentDecision(
            sense="Detected anomaly.",
            think="Deterministic rules are authoritative.",
            act="Quarantine and reroute attacker.",
            explain="Correlation confirms the incident.",
            severity="critical",
            category="coordinated_intrusion",
            risk_level="high",
            auto_execute=False,
        )


def make_app(tmp_path: Path, llm: FakeLLM | None = None) -> tuple[FastAPI, RecordingClient, AuditDB]:
    settings = SimpleNamespace(
        MQTT_HOST="127.0.0.1",
        MQTT_PORT=1883,
        MQTT_TOPIC_PREFIX="campus/lab1",
        DB_PATH=tmp_path / "watchdog.db",
        WINDOW_SECONDS=60,
        CORS_ORIGINS=[],
    )
    hub = StreamHub()
    window = CorrelationWindow(60)
    bridge = MqttBridge(settings, hub, window)  # type: ignore[arg-type]
    client = RecordingClient()
    bridge._client = client  # type: ignore[assignment]
    db = AuditDB(tmp_path / "watchdog.db")
    agent = Agent(db, bridge, hub, llm or FakeLLM())  # type: ignore[arg-type]
    hitl = HitlEngine(db, bridge, hub)

    app = FastAPI()
    app.state.settings = settings
    app.state.hub = hub
    app.state.window = window
    app.state.bridge = bridge
    app.state.db = db
    app.state.agent = agent
    app.state.hitl = hitl
    app.include_router(incidents_router)
    app.include_router(approvals_router)
    app.include_router(stream_router)
    app.include_router(agent_router)
    return app, client, db


def test_rest_lists_are_empty_on_fresh_db(tmp_path: Path) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)

    assert client.get("/api/incidents").json() == []
    assert client.get("/api/approvals").json() == []
    assert client.get("/api/audit-log").json() == []


def test_coordinated_trigger_publishes_and_creates_pending_approval(
    tmp_path: Path,
) -> None:
    app, mqtt, db = make_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/sim/trigger", json={"attack_type": "coordinated_intrusion"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "triggered": "coordinated_intrusion",
    }
    assert [topic for topic, _, _ in mqtt.published] == [
        "campus/lab1/cctv_cam",
        "campus/lab1/door_lock",
        "campus/lab1/smart_meter",
    ]
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["category"] == "coordinated_intrusion"
    assert incidents[0]["approval_status"] == "pending"
    approvals = client.get("/api/approvals").json()
    assert len(approvals) == 1
    assert approvals[0]["target_device_id"] == "smart_lock_01"
    assert any(
        entry.action == "HITL_APPROVAL_REQUESTED" for entry in db.list_audit()
    )


def test_repeated_coordinated_triggers_create_separate_approvals(
    tmp_path: Path,
) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)
    body = {"attack_type": "coordinated_intrusion"}

    assert client.post("/api/sim/trigger", json=body).status_code == 200
    assert client.post("/api/sim/trigger", json=body).status_code == 200

    assert len(client.get("/api/incidents").json()) == 2
    approvals = client.get("/api/approvals").json()
    assert len(approvals) == 2
    assert {approval["status"] for approval in approvals} == {"pending"}


def test_sensor_triggers_are_separate(tmp_path: Path) -> None:
    app, mqtt, _ = make_app(tmp_path)
    client = TestClient(app)

    spoof = client.post("/api/sim/trigger", json={"attack_type": "spoof_sensor"})
    spoof_incident = client.get("/api/incidents").json()[0]
    assert spoof.status_code == 200
    assert spoof_incident["category"] == "sensor_spoofing"
    assert spoof_incident["prompt_injection_detected"] is False
    assert client.get("/api/approvals").json() == []

    app2, mqtt2, _ = make_app(tmp_path / "second")
    client2 = TestClient(app2)
    injection = client2.post(
        "/api/sim/trigger", json={"attack_type": "prompt_injection"}
    )
    injection_incident = client2.get("/api/incidents").json()[0]
    assert injection.status_code == 200
    assert injection_incident["category"] == "prompt_injection"
    assert injection_incident["prompt_injection_detected"] is True
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in (
        injection_incident["sanitized_excerpt"] or ""
    )
    assert len(mqtt.published) == 1
    assert len(mqtt2.published) == 1


def test_llm_failure_returns_503_and_audits_without_incident(
    tmp_path: Path,
) -> None:
    app, _, db = make_app(tmp_path, FakeLLM(LLMUnavailable("router down")))
    client = TestClient(app)

    response = client.post("/api/sim/trigger", json={"attack_type": "spoof_sensor"})

    assert response.status_code == 503
    assert "router down" in response.json()["detail"]
    assert client.get("/api/incidents").json() == []
    assert client.get("/api/approvals").json() == []
    assert any(
        entry["actor"] == "SYSTEM" and entry["action"] == "LLM_UNAVAILABLE"
        for entry in client.get("/api/audit-log").json()
    )


def test_decision_endpoint_edges(tmp_path: Path) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)
    client.post("/api/sim/trigger", json={"attack_type": "coordinated_intrusion"})
    approval_id = client.get("/api/approvals").json()[0]["id"]

    missing = client.post(
        "/api/approvals/missing/decide", json={"decision": "approved"}
    )
    assert missing.status_code == 404

    approved = client.post(
        f"/api/approvals/{approval_id}/decide", json={"decision": "approved"}
    )
    assert approved.status_code == 200
    assert approved.json() == {
        "ok": True,
        "id": approval_id,
        "status": "approved",
    }

    repeated = client.post(
        f"/api/approvals/{approval_id}/decide", json={"decision": "rejected"}
    )
    assert repeated.status_code == 409


def test_agent_mode_repeat_is_noop(tmp_path: Path) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)

    bypassed = client.post("/api/agent/mode", json={"enabled": False})
    assert bypassed.json() == {"ok": True, "enabled": False}
    assert app.state.agent.enabled is False
    assert sum(
        entry["action"] == "AGENT_BYPASSED"
        for entry in client.get("/api/audit-log").json()
    ) == 1

    repeated = client.post("/api/agent/mode", json={"enabled": False})
    assert repeated.status_code == 200
    assert sum(
        entry["action"] == "AGENT_BYPASSED"
        for entry in client.get("/api/audit-log").json()
    ) == 1

    activated = client.post("/api/agent/mode", json={"enabled": True})
    assert activated.json() == {"ok": True, "enabled": True}
    assert any(
        entry["action"] == "AGENT_ACTIVATED"
        for entry in client.get("/api/audit-log").json()
    )


def test_records_survive_a_fresh_app_instance(tmp_path: Path) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)

    client.post("/api/sim/trigger", json={"attack_type": "coordinated_intrusion"})
    approval_id = client.get("/api/approvals").json()[0]["id"]
    decided = client.post(
        f"/api/approvals/{approval_id}/decide", json={"decision": "approved"}
    )
    assert decided.status_code == 200

    reopened, _, _ = make_app(tmp_path)
    reopened_client = TestClient(reopened)

    incidents = reopened_client.get("/api/incidents").json()
    approvals = reopened_client.get("/api/approvals").json()
    audit = reopened_client.get("/api/audit-log").json()
    assert len(incidents) == 1
    assert incidents[0]["approval_status"] == "approved"
    assert len(approvals) == 1
    assert approvals[0]["status"] == "approved"
    actions = {entry["action"] for entry in audit}
    assert {
        "HITL_APPROVAL_REQUESTED",
        "APPROVAL_APPROVED",
        "DECOY_ACTIVATED",
    } <= actions


def test_websocket_replays_devices_and_streams_all_event_types(
    tmp_path: Path,
) -> None:
    app, _, _ = make_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/api/stream") as websocket:
        assert websocket.receive_json()["type"] == "device_update"
        client.post(
            "/api/sim/trigger", json={"attack_type": "coordinated_intrusion"}
        )

        seen = set()
        for _ in range(40):
            seen.add(websocket.receive_json()["type"])
            if {
                "device_update",
                "new_incident",
                "new_approval",
                "audit_entry",
            } <= seen:
                break

    assert {
        "device_update",
        "new_incident",
        "new_approval",
        "audit_entry",
    } <= seen
