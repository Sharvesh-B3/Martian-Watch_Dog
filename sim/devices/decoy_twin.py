"""Active Decoy Twin that captures synthetic attacker probes."""

from collections.abc import Mapping
import hashlib
import json
from typing import Any

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

    def extra_subscriptions(self) -> tuple[str, ...]:
        return (f"{self.settings.topic_prefix}/attacker/#",)

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
