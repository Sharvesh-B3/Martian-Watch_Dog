"""Persistent MQTT Red Team controller for held attack scenarios."""

import json
import signal
import threading
from typing import Any

import paho.mqtt.client as mqtt

from sim.attacks.scenarios import SCENARIO_COMMANDS, validate_attack_type
from sim.common.protocol import utc_now
from sim.common.settings import SimSettings


class AttackController:
    def __init__(self, settings: SimSettings) -> None:
        self.settings = settings
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._active: dict[str, str] = {}
        self._probe_sequence = 0
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="sim-attack-controller",
        )
        self.client.reconnect_delay_set(1, 10)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        if getattr(reason_code, "is_failure", False):
            self.log(f"connection failed: {reason_code}")
            return
        prefix = self.settings.topic_prefix
        client.subscribe(
            [
                (f"{prefix}/redteam/trigger", 1),
                (f"{prefix}/redteam/reset", 1),
                (f"{prefix}/control/+", 1),
            ]
        )
        self.log("connected")

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return

        if message.topic.endswith("/redteam/trigger"):
            try:
                attack_type = validate_attack_type(str(payload.get("attack_type", "")))
            except ValueError as exc:
                self.log(str(exc))
                return
            scenario_id = str(payload.get("scenario_id") or "")
            if not scenario_id:
                return
            self.activate(attack_type, scenario_id)
            return

        if message.topic.endswith("/redteam/reset"):
            with self._lock:
                self._active.clear()
            self.log("all attack scenarios reset")
            return

        action = str(payload.get("action", "")).upper()
        if action in {"RESTORE", "RESET"}:
            with self._lock:
                self._active.clear()

    def activate(self, attack_type: str, scenario_id: str) -> None:
        validated = validate_attack_type(attack_type)
        with self._lock:
            if scenario_id in self._active:
                return
            self._active = {
                active_id: active_type
                for active_id, active_type in self._active.items()
                if active_type != validated
            }
            self._active[scenario_id] = validated
        command_base = {
            "attack_type": validated,
            "scenario_id": scenario_id,
            "timestamp": utc_now(),
        }
        for command in SCENARIO_COMMANDS[validated]:
            self.client.publish(
                f"{self.settings.topic_prefix}/sim/attack/{command.device_id}",
                json.dumps({**command_base, "action": command.action}),
                qos=1,
            )
        self.log(f"activated {validated} ({scenario_id})")

    def run(self) -> None:
        self.client.connect(
            self.settings.broker_host,
            self.settings.broker_port,
            keepalive=30,
        )
        self.client.loop_start()
        try:
            while not self._stop.wait(1.0):
                self.publish_attacker_probes()
        finally:
            self.client.disconnect()
            self.client.loop_stop()
            self.log("stopped")

    def publish_attacker_probes(self) -> None:
        with self._lock:
            coordinated = [
                scenario_id
                for scenario_id, attack_type in self._active.items()
                if attack_type == "coordinated_intrusion"
            ]
        for scenario_id in coordinated:
            self._probe_sequence += 1
            probe = {
                "scenario_id": scenario_id,
                "source": "10.0.4.66",
                "command": f"ENUMERATE_LAB_ASSETS_{self._probe_sequence}",
                "sequence": self._probe_sequence,
                "timestamp": utc_now(),
            }
            self.client.publish(
                f"{self.settings.topic_prefix}/attacker/session/{scenario_id}",
                json.dumps(probe),
                qos=1,
            )

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def log(message: str) -> None:
        print(f"[attack-controller] {message}", flush=True)


def main() -> None:
    controller = AttackController(SimSettings.from_env())
    signal.signal(signal.SIGINT, lambda *_: controller.stop())
    signal.signal(signal.SIGTERM, lambda *_: controller.stop())
    controller.run()


if __name__ == "__main__":
    main()
