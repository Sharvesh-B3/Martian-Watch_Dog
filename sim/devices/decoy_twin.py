"""Active Decoy Twin that captures synthetic attacker probes."""

from collections.abc import Mapping
import hashlib
import json
import os
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.mqtt_device import BaseMqttDevice, run_device
from sim.common.protocol import utc_now
from sim.common.settings import SimSettings


class DecoyTwinDevice(BaseMqttDevice):
    def __init__(self, settings: SimSettings) -> None:
        super().__init__("decoy_twin_01", settings)
        self.active = False
        self.captured_payloads = 0
        self.last_source = "NONE"
        self.last_command = "NONE"
        self.last_payload_hash = "NONE"
        self.decoy_host = os.getenv("SIM_DECOY_MQTT_HOST", "127.0.0.1")
        self.decoy_port = int(os.getenv("SIM_DECOY_MQTT_PORT", "1885"))
        self.decoy_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="decoy-twin-capture",
        )
        self.decoy_client.on_connect = self._on_decoy_connect
        self.decoy_client.on_message = self._on_decoy_message

    def extra_subscriptions(self) -> tuple[str, ...]:
        return ()

    def _on_decoy_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        if getattr(reason_code, "is_failure", False):
            return
        client.subscribe(f"{self.settings.topic_prefix}/attacker/#", qos=1)
        client.publish(
            f"{self.settings.topic_prefix}/environment",
            json.dumps({"environment": "DECOY_LAB", "timestamp": utc_now()}),
            qos=1,
            retain=True,
        )
        self.log(f"capture broker connected at {self.decoy_host}:{self.decoy_port}")

    def _on_decoy_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload.decode())
        except Exception:
            return
        if isinstance(payload, dict):
            self.handle_extra_message(message.topic, payload)

    def run(self) -> None:
        self.decoy_client.connect(self.decoy_host, self.decoy_port, 30)
        self.decoy_client.loop_start()
        try:
            super().run()
        finally:
            self.decoy_client.disconnect()
            self.decoy_client.loop_stop()

    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        return False

    def on_decoy(self) -> bool:
        self.active = True
        self.state = "DECOY_ACTIVE"
        return True

    def on_reset(self) -> None:
        self.active = False
        self.captured_payloads = 0
        self.last_source = "NONE"
        self.last_command = "NONE"
        self.last_payload_hash = "NONE"

    def handle_extra_message(
        self, topic: str, payload: Mapping[str, Any]
    ) -> None:
        with self._lock:
            if not self.active:
                return
            encoded = json.dumps(payload, sort_keys=True, default=str).encode()
            self.captured_payloads += 1
            self.scenario_id = str(payload.get("scenario_id") or "") or self.scenario_id
            self.last_source = str(payload.get("source", "unknown"))
            self.last_command = str(payload.get("command", "unknown"))
            self.last_payload_hash = hashlib.sha256(encoded).hexdigest()[:16]
            capture = {
                "device_id": self.device_id,
                "scenario_id": self.scenario_id,
                "source": self.last_source,
                "command": self.last_command,
                "payload_hash": self.last_payload_hash,
                "captured_payloads": self.captured_payloads,
                "timestamp": utc_now(),
            }
        self.client.publish(
            f"{self.settings.topic_prefix}/decoy/capture",
            json.dumps(capture),
            qos=1,
        )
        self.publish_telemetry()

    def metrics(self) -> dict[str, str | int | float | bool]:
        return {
            "active_traps": 1 if self.active else 0,
            "captured_payloads": self.captured_payloads,
            "last_source": self.last_source,
            "last_command": self.last_command,
            "last_payload_hash": self.last_payload_hash,
        }


if __name__ == "__main__":
    run_device(DecoyTwinDevice)
