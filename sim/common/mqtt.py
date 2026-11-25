"""MQTT 3.1.1 publisher runtime shared by every Phase 2 device service."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.config import DeviceIdentity, DeviceSettings
from sim.common.messages import (
    ContractValidationError,
    build_control_ack,
    build_decoy_event,
    build_presence,
    new_uuid,
    serialize_payload,
    utc_now,
    validate_payload,
)
from sim.common.state import DeviceModel


LOGGER = logging.getLogger("watchdog.device")


class JsonLogFormatter(logging.Formatter):
    """Emit bounded machine-readable logs without serializing credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


class DeviceRunner:
    """Connect, publish validated telemetry, maintain presence, and recover safely."""

    def __init__(self, settings: DeviceSettings, model: DeviceModel):
        self.settings = settings
        self.model = model
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._health_lock = threading.Lock()
        self._connect_count = 0
        self._processed_commands: dict[str, float] = {}
        self._session_started_at = utc_now()

        identity = settings.identity
        self._telemetry_topic = f"campus/lab1/telemetry/{identity.device_id}"
        self._presence_topic = f"campus/lab1/presence/{identity.device_id}"

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=identity.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(identity.mqtt_username, settings.mqtt_password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._configure_last_will()

    def run(self) -> None:
        self._install_signal_handlers()
        identity = self.settings.identity
        LOGGER.info(
            "Starting %s (%s) against mqtt://%s:%s",
            identity.device_id,
            identity.client_id,
            self.settings.mqtt_host,
            self.settings.mqtt_port,
        )

        self.client.connect_async(
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            keepalive=self.settings.keepalive_seconds,
        )
        self.client.loop_start()

        try:
            if not self._connected.wait(self.settings.connect_timeout_seconds):
                raise RuntimeError(
                    f"MQTT connection timed out after "
                    f"{self.settings.connect_timeout_seconds:.1f}s"
                )

            while not self._stop.is_set():
                if self._connected.is_set():
                    payload = self.model.telemetry()
                    self._publish_and_wait(self._telemetry_topic, payload)
                    self._write_health(connected=True, last_publish_epoch=time.time())
                self._stop.wait(self.settings.telemetry_interval_seconds)
        finally:
            self._graceful_shutdown()

    def stop(self) -> None:
        self._stop.set()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del userdata, connect_flags, properties
        if reason_code.is_failure:
            LOGGER.error("MQTT connection rejected for %s: %s", self.settings.identity.device_id, reason_code)
            self._connected.clear()
            self._write_health(connected=False, last_publish_epoch=None)
            return

        reason = "connected" if self._connect_count == 0 else "reconnected"
        self._connect_count += 1
        self._connected.set()
        online = build_presence(
            schema_dir=self.settings.schema_dir,
            device_id=self.settings.identity.device_id,
            device_type=self.settings.identity.device_type,
            client_id=self.settings.identity.client_id,
            session_started_at=self._session_started_at,
            state="online",
            reason=reason,
        )
        result = client.publish(
            self._presence_topic,
            payload=serialize_payload(online),
            qos=1,
            retain=False,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            LOGGER.error("Could not publish online presence: MQTT rc=%s", result.rc)
        LOGGER.info("Connected %s with MQTT 3.1.1", self.settings.identity.device_id)
        topics = [
            (f"campus/lab1/control/{self.settings.identity.device_id}", 1),
            ("campus/lab1/sim/reset", 1),
        ]
        if self.settings.identity.device_id in {
            "smart_lock_01",
            "air_quality_01",
            "power_meter_01",
        }:
            topics.append(
                (f"campus/lab1/sim/inject/{self.settings.identity.device_id}", 1)
            )
        if self.settings.identity.device_id == "decoy_twin_01":
            topics.append(("campus/lab1/decoy/input/+", 1))
        client.subscribe(topics)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self._connected.clear()
        self._write_health(connected=False, last_publish_epoch=None)
        if not self._stop.is_set():
            # The broker has just published the previous session's Will. Give
            # the reconnect a fresh session time and event ID so a later flap
            # is not hidden by the 10-minute event dedupe contract.
            self._session_started_at = utc_now()
            try:
                self._configure_last_will()
            except (ValueError, RuntimeError) as exc:
                LOGGER.error("Could not rotate Last Will before reconnect: %s", exc)
                self._stop.set()
            LOGGER.warning(
                "Disconnected %s (%s); Paho will retry with bounded backoff",
                self.settings.identity.device_id,
                reason_code,
            )

    def _publish_and_wait(self, topic: str, payload: dict[str, Any]) -> None:
        info = self.client.publish(
            topic,
            payload=serialize_payload(payload),
            qos=1,
            retain=False,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed on {topic}: rc={info.rc}")
        info.wait_for_publish(timeout=5.0)
        if not info.is_published():
            raise RuntimeError(f"MQTT QoS 1 acknowledgement timed out on {topic}")

    def _publish_from_callback(self, topic: str, payload: dict[str, Any]) -> None:
        info = self.client.publish(
            topic,
            payload=serialize_payload(payload),
            qos=1,
            retain=False,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT callback publish failed on {topic}: rc={info.rc}")

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if "/sim/inject/" in message.topic:
                validate_payload(self.settings.schema_dir, "injection.schema.json", payload)
                self._require_fresh(payload["expires_at"])
                if payload["target_device_id"] != self.settings.identity.device_id:
                    raise ValueError("Injection target does not match device")
                self.model.apply_injection(payload["evidence"], payload["request_id"])
                return
            if "/decoy/input/" in message.topic:
                self._handle_decoy_input(payload)
                return
            validate_payload(self.settings.schema_dir, "control.schema.json", payload)
            self._require_fresh(payload["expires_at"])
            is_reset = message.topic == "campus/lab1/sim/reset"
            if is_reset and payload["action"] != "RESET":
                raise ValueError("Reset topic requires RESET action")
            if not is_reset and payload["target_id"] != self.settings.identity.device_id:
                raise ValueError("Control target does not match device")
            self._handle_control(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ContractValidationError, ValueError) as exc:
            LOGGER.warning("Rejected message on %s: %s", message.topic, exc)
        except Exception:
            LOGGER.exception("Message handling failed on %s", message.topic)

    def _handle_control(self, payload: dict[str, Any]) -> None:
        command_id = payload["command_id"]
        self._prune_commands()
        if command_id in self._processed_commands:
            self._publish_ack(payload, "duplicate", "COMMAND_DUPLICATE")
            return
        self._publish_ack(payload, "accepted", "COMMAND_ACCEPTED")
        try:
            self.model.apply_action(payload["action"], payload["correlation_id"])
            self._processed_commands[command_id] = time.time()
            self._publish_ack(payload, "applied", f"{payload['action']}_APPLIED")
            if self.settings.identity.device_id == "decoy_twin_01":
                self._publish_decoy_transition(payload)
        except ValueError as exc:
            self._publish_ack(payload, "rejected", "ACTION_REJECTED", str(exc))
        except Exception as exc:
            self._publish_ack(payload, "failed", "ACTION_FAILED", str(exc))

    def _publish_ack(
        self,
        control: dict[str, Any],
        status: str,
        code: str,
        detail: str | None = None,
    ) -> None:
        ack = build_control_ack(
            schema_dir=self.settings.schema_dir,
            command_id=control["command_id"],
            correlation_id=control["correlation_id"],
            target_id=self.settings.identity.device_id,
            action=control["action"],
            status=status,
            observed_state=self.model.status,
            code=code,
            detail=detail,
        )
        self._publish_from_callback(
            f"campus/lab1/control_ack/{self.settings.identity.device_id}", ack
        )

    def _publish_decoy_transition(self, control: dict[str, Any]) -> None:
        metrics = self.model.telemetry()["metrics"]
        if control["action"] == "ACTIVATE_DECOY":
            event_type, summary = "activated", "Decoy route activated for smart_lock_01."
        elif control["action"] in {"RESTORE", "RESET"}:
            event_type, summary = "restored", "Decoy Twin restored to standby."
        else:
            return
        event = build_decoy_event(
            schema_dir=self.settings.schema_dir,
            request_id=control["correlation_id"],
            route_command_id=control["command_id"],
            target_device_id="smart_lock_01",
            event_type=event_type,
            active_traps=metrics["active_traps"],
            captured_payloads=metrics["captured_payloads"],
            safe_summary=summary,
        )
        self._publish_from_callback("campus/lab1/decoy/events", event)

    def _handle_decoy_input(self, payload: dict[str, Any]) -> None:
        validate_payload(self.settings.schema_dir, "decoy_input.schema.json", payload)
        capture = getattr(self.model, "capture", None)
        if capture is None:
            raise ValueError("Device cannot capture Decoy input")
        active_traps, captured_payloads = capture(payload["request_id"])
        event = build_decoy_event(
            schema_dir=self.settings.schema_dir,
            request_id=payload["request_id"],
            route_command_id=payload["route_command_id"],
            target_device_id=payload["target_device_id"],
            event_type="capture",
            active_traps=active_traps,
            captured_payloads=captured_payloads,
            capture_id=new_uuid(),
            payload_sha256=payload["content_sha256"],
            captured_bytes=len(payload["content"].encode("utf-8")),
            safe_summary="Captured one routed probe; raw content remains untrusted.",
        )
        self._publish_from_callback("campus/lab1/decoy/events", event)

    @staticmethod
    def _require_fresh(expires_at: str) -> None:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expiry:
            raise ValueError("Message expired")

    def _prune_commands(self) -> None:
        cutoff = time.time() - 86400
        self._processed_commands = {
            command_id: observed
            for command_id, observed in self._processed_commands.items()
            if observed >= cutoff
        }

    def _graceful_shutdown(self) -> None:
        self._stop.set()
        try:
            if self._connected.is_set():
                offline = build_presence(
                    schema_dir=self.settings.schema_dir,
                    device_id=self.settings.identity.device_id,
                    device_type=self.settings.identity.device_type,
                    client_id=self.settings.identity.client_id,
                    session_started_at=self._session_started_at,
                    state="offline",
                    reason="graceful_shutdown",
                )
                self._publish_and_wait(self._presence_topic, offline)
                self.client.disconnect()
        except Exception as exc:  # shutdown must still stop the network loop
            LOGGER.warning("Graceful presence publication failed: %s", exc)
        finally:
            self._connected.clear()
            self._write_health(connected=False, last_publish_epoch=None)
            self.client.loop_stop()
            LOGGER.info("Stopped %s", self.settings.identity.device_id)

    def _configure_last_will(self) -> None:
        identity = self.settings.identity
        offline = build_presence(
            schema_dir=self.settings.schema_dir,
            device_id=identity.device_id,
            device_type=identity.device_type,
            client_id=identity.client_id,
            session_started_at=self._session_started_at,
            state="offline",
            reason="last_will",
        )
        self.client.will_set(
            self._presence_topic,
            payload=serialize_payload(offline),
            qos=1,
            retain=False,
        )

    def _write_health(
        self,
        *,
        connected: bool,
        last_publish_epoch: float | None,
    ) -> None:
        path = self.settings.health_file
        state = {
            "device_id": self.settings.identity.device_id,
            "connected": connected,
            "last_publish_epoch": last_publish_epoch,
            "updated_at": utc_now(),
        }
        with self._health_lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f".{path.name}.tmp")
                with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(state, handle, separators=(",", ":"), sort_keys=True)
                    handle.write("\n")
                os.replace(temporary, path)
            except OSError as exc:
                LOGGER.error("Could not write health state %s: %s", path, exc)

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def request_stop(signum: int, frame: Any) -> None:
            del frame
            LOGGER.info("Received signal %s", signum)
            self.stop()

        for signal_name in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signal_name, request_stop)


def run_device(model_type: type[DeviceModel], identity: DeviceIdentity) -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    settings = DeviceSettings.from_env(identity)
    model = model_type(identity, settings.seed, settings.schema_dir)
    DeviceRunner(settings, model).run()
