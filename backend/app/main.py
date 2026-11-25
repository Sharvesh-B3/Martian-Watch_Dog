from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


NAMES = {
    "smart_lock_01": "Bio-Lab Main Door",
    "rfid_scanner_01": "Wing A Badge Reader",
    "air_quality_01": "Cleanroom Air Sensor",
    "power_meter_01": "Lab Rack PDU Meter",
    "decoy_twin_01": "Honeypot Decoy Node",
}


class AttackBody(BaseModel):
    attack_type: str


class DecisionBody(BaseModel):
    decision: str


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def broadcast(self, event: dict[str, Any]) -> None:
        failed: list[WebSocket] = []
        for client in tuple(self.clients):
            try:
                await client.send_json(event)
            except Exception:
                failed.append(client)
        for client in failed:
            self.clients.discard(client)

    def emit(self, event: dict[str, Any]) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self.loop)


class State:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.devices: dict[str, dict[str, Any]] = {}
        self.telemetry: dict[str, dict[str, Any]] = {}
        self.incidents: list[dict[str, Any]] = []
        self.approvals: list[dict[str, Any]] = []
        self.attack_status: dict[str, dict[str, Any]] = {}
        self.correlations: dict[str, str] = {}
        self.seen_incidents: set[tuple[str, str]] = set()
        self.db_path = Path(os.getenv("AUDIT_DB", "/data/watchdog.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS audit (id TEXT PRIMARY KEY, timestamp TEXT, actor TEXT, action TEXT, details TEXT)"
            )

    def audit(self, actor: str, action: str, details: str) -> dict[str, Any]:
        entry = {"id": uid("aud"), "timestamp": now(), "actor": actor, "action": action, "details": details}
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO audit(id,timestamp,actor,action,details) VALUES(?,?,?,?,?)",
                (entry["id"], entry["timestamp"], actor, action, details),
            )
        HUB.emit({"type": "audit_entry", "entry": entry})
        return entry

    def audit_log(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,timestamp,actor,action,details FROM audit ORDER BY timestamp DESC LIMIT 500"
            ).fetchall()
        return [dict(zip(("id", "timestamp", "actor", "action", "details"), row)) for row in rows]


HUB = Hub()
STATE = State()


class WatchdogMqtt:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.connected = threading.Event()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="watchdog-backend",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = lambda *_: self.connected.clear()
        self.client.on_message = self._on_message

    def start(self) -> None:
        self.client.connect_async(self.host, self.port, 30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code.is_failure:
            return
        self.connected.set()
        client.subscribe(
            [
                ("campus/lab1/telemetry/+", 1),
                ("campus/lab1/presence/+", 1),
                ("campus/lab1/control_ack/+", 1),
                ("campus/lab1/sim/attack/status", 1),
                ("campus/lab1/decoy/events", 1),
            ]
        )

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload.decode())
            if "/telemetry/" in message.topic:
                self._telemetry(payload)
            elif "/control_ack/" in message.topic:
                if payload.get("status") in {"applied", "failed", "rejected"}:
                    STATE.audit("SYSTEM", f"CONTROL_{payload['status'].upper()}", f"{payload['action']} on {payload['target_id']}")
            elif message.topic.endswith("/decoy/events"):
                STATE.audit("SYSTEM", f"DECOY_{payload['event_type'].upper()}", payload.get("safe_summary") or "Decoy event")
            elif message.topic.endswith("/sim/attack/status"):
                with STATE.lock:
                    STATE.attack_status[payload["request_id"]] = payload
        except Exception as exc:
            STATE.audit("SYSTEM", "MQTT_MESSAGE_ERROR", str(exc)[:500])

    def _telemetry(self, raw: dict[str, Any]) -> None:
        device_id = raw["device_id"]
        device = {
            "id": device_id,
            "name": NAMES[device_id],
            "type": raw["device_type"],
            "zone": "Isolated Sandbox" if device_id == "decoy_twin_01" else "Lab Wing A",
            "status": raw["status"],
            "metrics": raw["metrics"],
            "last_updated": raw["timestamp"],
        }
        with STATE.lock:
            STATE.devices[device_id] = device
            STATE.telemetry[device_id] = raw
        HUB.emit({"type": "device_update", "device": device})
        self._detect(raw)

    def _detect(self, raw: dict[str, Any]) -> None:
        correlation = raw.get("correlation_id")
        if not correlation:
            return
        note = (raw.get("metadata") or {}).get("note") or ""
        if "IGNORE PREVIOUS INSTRUCTIONS" in note.upper():
            created = self._incident(
                correlation,
                "prompt_injection",
                "high",
                "Live Prompt Injection Intercepted",
                "Untrusted sensor metadata contained an instruction override. The guardrail framed and blocked it before reasoning.",
                ["air_quality_01"],
                True,
                note,
                "Rate-limit air_quality_01 MQTT topic (Auto-executed)",
                "auto_executed",
            )
            if created:
                STATE.audit("GUARDRAIL", "INJECTION_NEUTRALIZED", "Blocked adversarial metadata from air_quality_01.")
        elif raw["device_id"] == "air_quality_01" and raw["metrics"].get("pm25", 0) >= 100:
            self._incident(
                correlation,
                "sensor_spoofing",
                "medium",
                "Spoofed Sensor Reading Filtered",
                "PM2.5 jumped outside the signed physical baseline while neighbouring values remained normal.",
                ["air_quality_01"],
                False,
                None,
                "Drop spoofed sample and rate-limit sensor topic (Auto-executed)",
                "auto_executed",
            )
        else:
            with STATE.lock:
                lock = STATE.telemetry.get("smart_lock_01", {})
                power = STATE.telemetry.get("power_meter_01", {})
                rfid = STATE.telemetry.get("rfid_scanner_01", {})
            if lock.get("correlation_id") == correlation and not lock.get("metrics", {}).get("locked", True) and power.get("correlation_id") == correlation and power.get("metrics", {}).get("outbound_conns", 0) > 50 and not rfid.get("metrics", {}).get("authorized", False):
                self._incident(
                    correlation,
                    "coordinated_intrusion",
                    "critical",
                    "Correlated Physical + Cyber Intrusion Detected",
                    "The smart lock unlocked without an authorized RFID scan while the power meter showed an outbound port scan in the same correlation window.",
                    ["smart_lock_01", "rfid_scanner_01", "power_meter_01"],
                    False,
                    None,
                    "Quarantine smart_lock_01 and activate the Decoy Twin",
                    "pending",
                )

    def _incident(self, correlation, category, severity, title, explanation, devices, injection, excerpt, action, approval_status) -> bool:
        key = (category, correlation)
        with STATE.lock:
            if key in STATE.seen_incidents:
                return False
            STATE.seen_incidents.add(key)
            incident = {
                "id": uid("inc"), "timestamp": now(), "severity": severity, "category": category,
                "title": title, "plain_english_explanation": explanation,
                "correlated_device_ids": devices, "prompt_injection_detected": injection,
                "sanitized_excerpt": excerpt, "proposed_action": action, "approval_status": approval_status,
            }
            STATE.incidents.insert(0, incident)
            STATE.correlations[incident["id"]] = correlation
        HUB.emit({"type": "new_incident", "incident": incident})
        STATE.audit("AI_AGENT", "INCIDENT_DETECTED", f"{title} ({incident['id']})")
        if approval_status == "pending":
            approval = {
                "id": uid("apr"), "incident_id": incident["id"], "created_at": now(),
                "target_device_id": "smart_lock_01",
                "recommended_action": "Lockdown & Quarantine + Activate Decoy Twin",
                "risk_summary": "Locks the simulated door and explicitly routes later probes to the Decoy Twin.",
                "status": "pending",
            }
            with STATE.lock:
                STATE.approvals.insert(0, approval)
            HUB.emit({"type": "new_approval", "approval": approval})
        return True

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        info = self.client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=False)
        info.wait_for_publish(5)
        if not info.is_published():
            raise RuntimeError(f"MQTT publish timed out: {topic}")


MQTT = WatchdogMqtt()


def trigger_payload(attack_type: str) -> tuple[str, dict[str, Any]]:
    if attack_type not in {"spoof_sensor", "coordinated_intrusion", "prompt_injection"}:
        raise HTTPException(422, "Unknown attack_type")
    request_id = str(uuid.uuid4())
    current = datetime.now(timezone.utc)
    return request_id, {
        "schema_version": "1.0", "request_id": request_id, "attack_type": attack_type,
        "requested_at": current.isoformat().replace("+00:00", "Z"),
        "expires_at": (current + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
        "requested_by": "backend",
    }


def control_payload(target: str, action: str, incident: str | None, approval: str | None, correlation: str) -> dict[str, Any]:
    current = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0", "command_id": str(uuid.uuid4()), "correlation_id": correlation,
        "target_id": target, "action": action, "incident_id": incident, "approval_id": approval,
        "issued_at": current.isoformat().replace("+00:00", "Z"),
        "expires_at": (current + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"), "actor": "backend",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    HUB.loop = asyncio.get_running_loop()
    MQTT.start()
    yield
    MQTT.stop()


app = FastAPI(title="Aegis Watchdog", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "mqtt_connected": MQTT.connected.is_set()}


@app.get("/api/incidents")
def incidents():
    with STATE.lock:
        return list(STATE.incidents)


@app.get("/api/approvals")
def approvals():
    with STATE.lock:
        return list(STATE.approvals)


@app.get("/api/audit-log")
def audit_log():
    return STATE.audit_log()


@app.post("/api/sim/trigger")
def trigger(body: AttackBody):
    request_id, payload = trigger_payload(body.attack_type)
    MQTT.publish("campus/lab1/sim/attack/trigger", payload)
    STATE.audit("HUMAN_OPERATOR", "SIM_ATTACK_TRIGGERED", f"{body.attack_type} ({request_id})")
    return {"ok": True, "triggered": body.attack_type, "request_id": request_id}


@app.post("/api/sim/reset")
def reset_lab():
    correlation = str(uuid.uuid4())
    payload = control_payload("lab1", "RESET", None, None, correlation)
    MQTT.publish("campus/lab1/sim/reset", payload)
    STATE.audit("HUMAN_OPERATOR", "LAB_RESET_REQUESTED", payload["command_id"])
    return {"ok": True, "command_id": payload["command_id"], "correlation_id": correlation}


@app.get("/api/sim/status/{request_id}")
def sim_status(request_id: str):
    with STATE.lock:
        status = STATE.attack_status.get(request_id)
    if not status:
        raise HTTPException(404, "status not available")
    return status


@app.post("/api/approvals/{approval_id}/decide")
def decide(approval_id: str, body: DecisionBody):
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(422, "decision must be approved or rejected")
    with STATE.lock:
        approval = next((item for item in STATE.approvals if item["id"] == approval_id), None)
        if not approval:
            raise HTTPException(404, "approval not found")
        if approval["status"] != "pending":
            return {"ok": True, "id": approval_id, "status": approval["status"]}
        approval["status"] = body.decision
        incident = next(item for item in STATE.incidents if item["id"] == approval["incident_id"])
        incident["approval_status"] = body.decision
        correlation = STATE.correlations[incident["id"]]
    HUB.emit({"type": "new_approval", "approval": approval})
    HUB.emit({"type": "new_incident", "incident": incident})
    if body.decision == "approved":
        MQTT.publish(
            "campus/lab1/control/smart_lock_01",
            control_payload("smart_lock_01", "QUARANTINE", incident["id"], approval_id, correlation),
        )
        MQTT.publish(
            "campus/lab1/control/decoy_twin_01",
            control_payload("decoy_twin_01", "ACTIVATE_DECOY", incident["id"], approval_id, correlation),
        )
        STATE.audit("HUMAN_OPERATOR", "CONTAINMENT_APPROVED", f"Approved {approval_id}")
    else:
        STATE.audit("HUMAN_OPERATOR", "ACTION_REJECTED", f"Rejected {approval_id}")
    return {"ok": True, "id": approval_id, "status": body.decision}


@app.websocket("/api/stream")
async def stream(socket: WebSocket):
    await socket.accept()
    HUB.clients.add(socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        HUB.clients.discard(socket)
