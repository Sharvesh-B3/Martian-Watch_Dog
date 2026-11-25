"""Single MQTT attack controller implementing the three canonical scenarios."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.messages import new_uuid, serialize_payload, utc_now, validate_payload
from sim.common.mqtt import configure_logging


LOGGER = logging.getLogger("watchdog.attack_controller")
SCHEMA_DIR = Path(os.getenv("SCHEMA_DIR", "/app/sim/contracts"))


class AttackController:
    def __init__(self) -> None:
        self.host = os.environ["MQTT_HOST"]
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.username = os.environ["MQTT_USERNAME"]
        self.password = os.environ["MQTT_PASSWORD"]
        self.client_id = os.getenv("MQTT_CLIENT_ID", "watchdog-attack-controller")
        self.health_file = Path(os.getenv("HEALTH_FILE", "/tmp/watchdog-health.json"))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._active_request: str | None = None
        self._seen: dict[str, float] = {}
        self._completed: dict[str, str] = {}
        self._routed: set[str] = set()
        self._epoch = 0

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(self.username, self.password)
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def run(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self._stop.set())
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()
        try:
            while not self._stop.wait(1):
                self._write_health(self.client.is_connected())
        finally:
            self.client.disconnect()
            self.client.loop_stop()
            self._write_health(False)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code.is_failure:
            LOGGER.error("Controller connection rejected: %s", reason_code)
            self._write_health(False)
            return
        client.subscribe(
            [
                ("campus/lab1/sim/attack/trigger", 1),
                ("campus/lab1/sim/reset", 1),
                ("campus/lab1/decoy/events", 1),
            ]
        )
        self._write_health(True)
        LOGGER.info("Attack controller connected")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        del client, userdata, flags, properties
        self._write_health(False)
        if not self._stop.is_set():
            LOGGER.warning("Attack controller disconnected: %s", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if message.topic == "campus/lab1/sim/attack/trigger":
                self._handle_trigger(payload)
            elif message.topic == "campus/lab1/sim/reset":
                self._handle_reset(payload)
            elif message.topic == "campus/lab1/decoy/events":
                self._handle_decoy_event(payload)
        except Exception:
            LOGGER.exception("Controller rejected message on %s", message.topic)

    def _handle_trigger(self, payload: dict[str, Any]) -> None:
        validate_payload(SCHEMA_DIR, "attack_trigger.schema.json", payload)
        request_id = payload["request_id"]
        attack_type = payload["attack_type"]
        if self._expired(payload["expires_at"]):
            self._status(request_id, attack_type, "rejected", "TRIGGER_EXPIRED")
            return
        with self._lock:
            self._prune_seen()
            if request_id in self._seen:
                self._status(request_id, attack_type, "duplicate", "TRIGGER_DUPLICATE")
                return
            if self._active_request is not None:
                self._status(request_id, attack_type, "busy", "CONTROLLER_BUSY")
                return
            self._seen[request_id] = time.time()
            self._active_request = request_id
            epoch = self._epoch
        self._status(request_id, attack_type, "accepted", "SCENARIO_ACCEPTED")
        threading.Thread(
            target=self._run_scenario,
            args=(request_id, attack_type, epoch),
            daemon=True,
        ).start()

    def _run_scenario(self, request_id: str, attack_type: str, epoch: int) -> None:
        evidence_ids: list[str] = []
        try:
            self._status(request_id, attack_type, "started", "SCENARIO_STARTED")
            if attack_type == "spoof_sensor":
                steps = [("air_quality_01", "pm25_spike", 0), ("air_quality_01", "pm25_spike", 2), ("air_quality_01", "pm25_spike", 2)]
            elif attack_type == "prompt_injection":
                steps = [("air_quality_01", "prompt_note", 0), ("air_quality_01", "prompt_note", 2), ("air_quality_01", "prompt_note", 2)]
            else:
                steps = [("power_meter_01", "port_scan", 0), ("smart_lock_01", "unauthorized_unlock", 1), ("power_meter_01", "port_scan", 3)]
            for sequence, (target, evidence, delay) in enumerate(steps, start=1):
                if delay and self._stop.wait(delay):
                    return
                with self._lock:
                    if epoch != self._epoch:
                        return
                event_id = self._inject(request_id, attack_type, target, evidence, sequence)
                evidence_ids.append(event_id)
            self._ground_truth(request_id, attack_type, evidence_ids)
            self._status(request_id, attack_type, "completed", "SCENARIO_COMPLETED")
            with self._lock:
                self._completed[request_id] = attack_type
        except Exception as exc:
            LOGGER.exception("Scenario %s failed", request_id)
            self._status(request_id, attack_type, "failed", "SCENARIO_FAILED", str(exc))
        finally:
            with self._lock:
                if self._active_request == request_id:
                    self._active_request = None

    def _inject(self, request_id, attack_type, target, evidence, sequence) -> str:
        event_id = new_uuid()
        now = datetime.now(timezone.utc)
        payload = {
            "schema_version": "1.0",
            "event_id": event_id,
            "request_id": request_id,
            "attack_type": attack_type,
            "target_device_id": target,
            "evidence": evidence,
            "sequence": sequence,
            "total": 3,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
        }
        validate_payload(SCHEMA_DIR, "injection.schema.json", payload)
        self._publish(f"campus/lab1/sim/inject/{target}", payload)
        return event_id

    def _status(self, request_id, attack_type, status, code, detail=None) -> None:
        payload = {
            "schema_version": "1.0",
            "event_id": new_uuid(),
            "request_id": request_id,
            "attack_type": attack_type,
            "status": status,
            "timestamp": utc_now(),
            "code": code,
            "detail": detail,
            "emitted_by": "attack_controller",
        }
        validate_payload(SCHEMA_DIR, "attack_status.schema.json", payload)
        self._publish("campus/lab1/sim/attack/status", payload)

    def _ground_truth(self, request_id, attack_type, evidence_ids) -> None:
        expected = {
            "spoof_sensor": ["air_quality_01"],
            "prompt_injection": ["air_quality_01"],
            "coordinated_intrusion": ["smart_lock_01", "rfid_scanner_01", "power_meter_01"],
        }[attack_type]
        payload = {
            "schema_version": "1.0",
            "event_id": new_uuid(),
            "request_id": request_id,
            "attack_type": attack_type,
            "timestamp": utc_now(),
            "phase": "evidence_emitted",
            "expected_device_ids": expected,
            "evidence_event_ids": evidence_ids,
            "note": "Observer-only expected evidence.",
        }
        validate_payload(SCHEMA_DIR, "ground_truth.schema.json", payload)
        self._publish("campus/lab1/test/ground_truth", payload)

    def _handle_reset(self, payload: dict[str, Any]) -> None:
        validate_payload(SCHEMA_DIR, "control.schema.json", payload)
        if payload["action"] != "RESET" or self._expired(payload["expires_at"]):
            return
        with self._lock:
            self._epoch += 1
            self._active_request = None
            self._completed.clear()
            self._routed.clear()
        self._status(payload["command_id"], "reset", "completed", "RESET_COMPLETED")

    def _handle_decoy_event(self, payload: dict[str, Any]) -> None:
        validate_payload(SCHEMA_DIR, "decoy_event.schema.json", payload)
        if payload["event_type"] != "activated":
            return
        request_id = payload["request_id"]
        with self._lock:
            attack_type = self._completed.get(request_id, "coordinated_intrusion")
            if request_id in self._routed:
                return
            self._routed.add(request_id)
        content = "UNAUTHORIZED_UNLOCK_PROBE"
        probe = {
            "schema_version": "1.0",
            "event_id": new_uuid(),
            "request_id": request_id,
            "route_command_id": payload["route_command_id"],
            "target_device_id": payload["target_device_id"],
            "attack_type": attack_type,
            "timestamp": utc_now(),
            "probe_kind": "post_containment",
            "content_type": "text/plain; charset=utf-8",
            "content": content,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
        validate_payload(SCHEMA_DIR, "decoy_input.schema.json", probe)
        self._publish(f"campus/lab1/decoy/input/{payload['target_device_id']}", probe)

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        info = self.client.publish(topic, serialize_payload(payload), qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Publish failed on {topic}: {info.rc}")
        self._write_health(True)

    def _write_health(self, connected: bool) -> None:
        self.health_file.parent.mkdir(parents=True, exist_ok=True)
        self.health_file.write_text(
            json.dumps({"connected": connected, "last_publish_epoch": time.time(), "updated_at": utc_now()}),
            encoding="utf-8",
        )

    @staticmethod
    def _expired(value: str) -> bool:
        return datetime.now(timezone.utc) > datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _prune_seen(self) -> None:
        cutoff = time.time() - 600
        self._seen = {key: observed for key, observed in self._seen.items() if observed >= cutoff}


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    AttackController().run()


if __name__ == "__main__":
    main()
