"""MQTT bridge between the isolated lab broker and the backend pipeline."""

import json
import logging
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from backend.app.correlation_window import CorrelationWindow
from backend.app.guardrail import sanitize_payload, sanitized_excerpt
from backend.app.schemas import (
    DeviceNode,
    DeviceStatus,
    DeviceType,
    DeviceUpdateEvent,
)
from backend.app.stream_hub import StreamHub
from sim.common.protocol import is_internal_topic

logger = logging.getLogger(__name__)

SIM_TO_CANONICAL = {
    "door_lock_01": "smart_lock_01",
    "rfid_01": "rfid_scanner_01",
    "aq_sensor_01": "air_quality_01",
    "meter_01": "power_meter_01",
    "decoy_twin_01": "decoy_twin_01",
}
CANONICAL_TO_SIM = {value: key for key, value in SIM_TO_CANONICAL.items()}

DEVICE_METADATA: dict[str, dict[str, Any]] = {
    "smart_lock_01": {
        "name": "Bio-Lab Main Door",
        "type": DeviceType.SMART_LOCK,
        "zone": "Lab Wing A",
        "metrics": {"locked": True, "door_closed": True, "failed_attempts": 0},
    },
    "rfid_scanner_01": {
        "name": "Wing A Badge Reader",
        "type": DeviceType.RFID_SCANNER,
        "zone": "Lab Wing A",
        "metrics": {"last_badge": "FAC-2049", "scan_rate_per_min": 2},
    },
    "air_quality_01": {
        "name": "Cleanroom Air Sensor",
        "type": DeviceType.AIR_QUALITY,
        "zone": "Lab Wing A",
        "metrics": {"pm25": 12, "co2_ppm": 430, "temp_c": 21.5},
    },
    "power_meter_01": {
        "name": "Lab Rack PDU Meter",
        "type": DeviceType.POWER_METER,
        "zone": "Lab Wing A",
        "metrics": {"load_kw": 3.4, "voltage": 230, "outbound_conns": 1},
    },
    "decoy_twin_01": {
        "name": "Honeypot Decoy Node",
        "type": DeviceType.DECOY_TWIN,
        "zone": "Isolated Sandbox",
        "metrics": {"active_traps": 0, "captured_payloads": 0},
    },
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


class MqttBridge:
    """Subscribes to lab telemetry and publishes approved control commands."""

    def __init__(
        self,
        settings: Any,
        hub: StreamHub,
        window: CorrelationWindow,
    ) -> None:
        self._settings = settings
        self._hub = hub
        self._window = window
        self._lock = threading.RLock()
        self._devices = self._build_initial_devices()
        self._pipeline_callback: Callable[[], None] | None = None
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="aegis-watchdog-backend",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------ lifecycle -------------------------------

    def start(self) -> None:
        self._client.connect(
            self._settings.MQTT_HOST, self._settings.MQTT_PORT, 60
        )
        self._client.loop_start()
        self.emit_initial_devices()
        logger.info("MQTT bridge connected to %s", self._settings.MQTT_HOST)

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT bridge stopped")

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if getattr(reason_code, "is_failure", False):
            logger.error("MQTT connection failed: %s", reason_code)
            return
        topic = f"{self._settings.MQTT_TOPIC_PREFIX}/#"
        client.subscribe(topic, qos=1)
        logger.info("Subscribed to %s", topic)

    def _on_disconnect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        logger.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if message.topic.endswith("/gateway/status") and isinstance(payload, dict):
            self._handle_gateway_status(payload)
            return
        if is_internal_topic(message.topic):
            return
        if isinstance(payload, dict):
            self.handle_payload(message.topic, payload)
            callback = self._pipeline_callback
            if callback is not None:
                try:
                    callback()
                except Exception:
                    logger.exception("Failed to schedule telemetry pipeline")

    def _handle_gateway_status(self, payload: Mapping[str, Any]) -> None:
        keys = (
            "route_target",
            "upstream",
            "active_sessions",
            "connection_count",
            "attacker_reconnects",
            "switch_count",
            "real_bytes",
            "decoy_bytes",
            "last_switch_at",
            "incident_id",
            "last_error",
        )
        metrics = {key: payload[key] for key in keys if key in payload}
        metrics["route_confirmed"] = payload.get("route_target") == "decoy"
        self.set_device_status(
            "decoy_twin_01",
            DeviceStatus.DECOY,
            metrics,
        )

    # ------------------------------- pipeline --------------------------------

    def handle_payload(self, topic: str, payload: Mapping[str, Any]) -> None:
        """Sanitize one telemetry frame, feed correlation and update devices."""
        sanitized = sanitize_payload(payload)
        sim_id = str(payload.get("device_id") or topic.rstrip("/").split("/")[-1])
        canonical_id = SIM_TO_CANONICAL.get(sim_id, sim_id)

        self._window.add(
            canonical_id,
            sanitized.payload,
            topic=topic,
            injection_detected=sanitized.detected,
            sanitized_excerpt=sanitized_excerpt(sanitized),
            timestamp=payload.get("timestamp"),
        )

        if canonical_id in self._devices:
            self._update_device(canonical_id, sanitized.payload)

    def publish_telemetry(self, topic_suffix: str, payload: Mapping[str, Any]) -> None:
        """Publish an attack/telemetry frame to the lab broker."""
        topic = (
            f"{self._settings.MQTT_TOPIC_PREFIX}/"
            f"{topic_suffix.lstrip('/')}"
        )
        self._client.publish(topic, json.dumps(payload), qos=1)

    def set_pipeline_callback(
        self, callback: Callable[[], None] | None
    ) -> None:
        """Set the non-blocking scheduler invoked after inbound MQTT frames."""
        self._pipeline_callback = callback

    def publish_control(self, canonical_id: str, action: str) -> bool:
        """Publish a control command to the mapped sim device."""
        sim_id = CANONICAL_TO_SIM.get(canonical_id)
        if sim_id is None:
            logger.warning("No sim topic mapped for %s", canonical_id)
            return False
        topic = f"{self._settings.MQTT_TOPIC_PREFIX}/control/{sim_id}"
        self._client.publish(
            topic, json.dumps({"action": action}), qos=1
        )
        logger.info("Published %s to %s", action, topic)
        return True

    # ----------------------------- device state ------------------------------

    def emit_initial_devices(self) -> None:
        with self._lock:
            devices = [device.model_copy(deep=True) for device in self._devices.values()]
        for device in devices:
            self._broadcast_device(device)

    def device_snapshot(self) -> list[DeviceNode]:
        with self._lock:
            return [device.model_copy(deep=True) for device in self._devices.values()]

    def set_device_status(
        self,
        canonical_id: str,
        status: DeviceStatus,
        metrics_patch: Mapping[str, Any] | None = None,
    ) -> DeviceNode | None:
        """Used by the agent/HITL engine to apply non-sim state changes."""
        with self._lock:
            device = self._devices.get(canonical_id)
            if device is None:
                return None
            device.status = status
            if metrics_patch:
                device.metrics.update(dict(metrics_patch))
            device.last_updated = utc_now()
            updated = device.model_copy(deep=True)
        self._broadcast_device(updated)
        return updated

    def _build_initial_devices(self) -> dict[str, DeviceNode]:
        devices: dict[str, DeviceNode] = {}
        for device_id, metadata in DEVICE_METADATA.items():
            status = (
                DeviceStatus.DECOY
                if device_id == "decoy_twin_01"
                else DeviceStatus.NORMAL
            )
            devices[device_id] = DeviceNode(
                id=device_id,
                name=metadata["name"],
                type=metadata["type"],
                zone=metadata["zone"],
                status=status,
                metrics=dict(metadata["metrics"]),
                last_updated=utc_now(),
            )
        return devices

    def _update_device(self, canonical_id: str, payload: Mapping[str, Any]) -> None:
        with self._lock:
            device = self._devices[canonical_id]
            metrics = dict(device.metrics)
            self._merge_metrics(canonical_id, payload, metrics)

            sim_state = str(payload.get("state", "")).upper()
            if canonical_id == "decoy_twin_01":
                status = DeviceStatus.DECOY
            elif sim_state == "QUARANTINED":
                status = DeviceStatus.QUARANTINED
            elif sim_state == "DECOY_ACTIVE":
                status = DeviceStatus.DECOY
            elif sim_state in {"WARNING", "COMPROMISED", "ATTACK_ACTIVE"}:
                status = DeviceStatus.WARNING
            elif sim_state == "NORMAL":
                status = (
                    DeviceStatus.NORMAL
                    if device.status in (DeviceStatus.QUARANTINED, DeviceStatus.DECOY)
                    else device.status
                )
            else:
                status = device.status

            device.status = status
            device.metrics = metrics
            device.last_updated = utc_now()
            updated = device.model_copy(deep=True)
        self._broadcast_device(updated)

    @staticmethod
    def _merge_metrics(
        canonical_id: str,
        payload: Mapping[str, Any],
        metrics: dict[str, str | int | float | bool],
    ) -> None:
        if canonical_id == "smart_lock_01":
            status = str(payload.get("status", "")).upper()
            if status:
                metrics["locked"] = status != "UNLOCKED"
            if "door_closed" in payload:
                metrics["door_closed"] = payload["door_closed"]
            if "failed_attempts" in payload:
                metrics["failed_attempts"] = payload["failed_attempts"]
            if "last_rfid" in payload:
                metrics["last_badge"] = payload["last_rfid"]
                if "failed_attempts" not in payload:
                    metrics["failed_attempts"] = (
                        3
                        if str(payload["last_rfid"]).upper()
                        == "UNAUTHORIZED_BYPASS"
                        else 0
                    )
        elif canonical_id == "rfid_scanner_01":
            if payload.get("badge_id"):
                metrics["last_badge"] = payload["badge_id"]
            if "scan_rate_per_min" in payload:
                metrics["scan_rate_per_min"] = payload["scan_rate_per_min"]
        elif canonical_id == "air_quality_01":
            for key in ("co2_ppm", "temp_c", "pm25"):
                if key in payload:
                    metrics[key] = payload[key]
        elif canonical_id == "power_meter_01":
            if "power_kw" in payload:
                metrics["load_kw"] = payload["power_kw"]
            if "network_conns" in payload:
                metrics["outbound_conns"] = payload["network_conns"]
        elif canonical_id == "decoy_twin_01":
            for key in (
                "active_traps",
                "captured_payloads",
                "last_source",
                "last_command",
                "last_payload_hash",
            ):
                if key in payload:
                    metrics[key] = payload[key]

    def _broadcast_device(self, device: DeviceNode) -> None:
        self._hub.publish(DeviceUpdateEvent(device=device))
