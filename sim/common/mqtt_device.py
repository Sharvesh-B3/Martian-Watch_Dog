"""Reusable MQTT runtime for independently simulated IoT nodes."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
import argparse
import hashlib
import json
import random
import signal
import threading
from typing import Any, TypeVar

import paho.mqtt.client as mqtt

from sim.common.protocol import (
    attack_topic,
    control_topic,
    presence_topic,
    telemetry_topic,
    utc_now,
)
from sim.common.settings import SimSettings

DeviceT = TypeVar("DeviceT", bound="BaseMqttDevice")


class BaseMqttDevice(ABC):
    """Lifecycle, metadata and command handling shared by every device."""

    def __init__(self, device_id: str, settings: SimSettings) -> None:
        self.device_id = device_id
        self.settings = settings
        self.state = "NORMAL"
        self.scenario_id: str | None = None
        self.sequence = 0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._connected = threading.Event()
        seed_material = f"{settings.seed}:{device_id}".encode()
        stable_offset = int(hashlib.sha256(seed_material).hexdigest()[:8], 16)
        self.rng = random.Random(stable_offset)

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{device_id}",
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.will_set(
            presence_topic(device_id, settings.topic_prefix),
            json.dumps({"device_id": device_id, "status": "OFFLINE"}),
            qos=1,
            retain=True,
        )

    # ------------------------------ lifecycle ------------------------------

    def run(self) -> None:
        self.log("starting")
        self.client.connect(
            self.settings.broker_host,
            self.settings.broker_port,
            keepalive=30,
        )
        self.client.loop_start()
        try:
            while not self._stop.is_set():
                if self._connected.is_set():
                    self.publish_telemetry()
                self._stop.wait(self.settings.interval_seconds)
        finally:
            if self._connected.is_set():
                self._publish_presence("OFFLINE", wait=True)
            self.client.disconnect()
            self.client.loop_stop()
            self.log("stopped")

    def stop(self) -> None:
        self._stop.set()

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
        client.subscribe(
            [
                (control_topic(self.device_id, self.settings.topic_prefix), 1),
                (attack_topic(self.device_id, self.settings.topic_prefix), 1),
                *[(topic, 1) for topic in self.extra_subscriptions()],
            ]
        )
        self._connected.set()
        self._publish_presence("ONLINE")
        self.log("connected")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        self._connected.clear()
        if not self._stop.is_set():
            self.log(f"disconnected: {reason_code}")

    # ------------------------------ messages -------------------------------

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.log(f"ignored malformed JSON on {message.topic}")
            return
        if not isinstance(payload, dict):
            return

        if message.topic == control_topic(
            self.device_id, self.settings.topic_prefix
        ):
            action = str(payload.get("action", "")).upper()
            accepted = self.apply_control(action, payload)
            self._publish_command_ack("control", action, accepted)
            if accepted:
                self.publish_telemetry()
            return

        if message.topic == attack_topic(
            self.device_id, self.settings.topic_prefix
        ):
            action = str(payload.get("action", "")).upper()
            accepted = self.apply_attack(action, payload)
            self._publish_command_ack("attack", action, accepted)
            if accepted:
                self.publish_telemetry()
            return

        self.handle_extra_message(message.topic, payload)

    def apply_control(self, action: str, payload: Mapping[str, Any]) -> bool:
        with self._lock:
            if action in {"RESTORE", "RESET", "NORMAL"}:
                self.reset()
                return True
            if action in {"QUARANTINE", "QUARANTINED"}:
                self.state = "QUARANTINED"
                self.on_quarantine()
                return True
            if action == "DECOY":
                return self.on_decoy()
        return False

    def apply_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        with self._lock:
            accepted = self.on_attack(action, payload)
            if accepted:
                self.scenario_id = str(payload.get("scenario_id") or "") or None
        return accepted

    def extra_subscriptions(self) -> tuple[str, ...]:
        return ()

    def handle_extra_message(
        self, topic: str, payload: Mapping[str, Any]
    ) -> None:
        return None

    # ------------------------------ telemetry ------------------------------

    def telemetry_frame(self) -> dict[str, Any]:
        with self._lock:
            self.sequence += 1
            return {
                "device_id": self.device_id,
                "timestamp": utc_now(),
                "sequence": self.sequence,
                "run_id": self.settings.run_id,
                "scenario_id": self.scenario_id,
                "state": self.state,
                **self.metrics(),
            }

    def publish_telemetry(self) -> None:
        frame = self.telemetry_frame()
        self.client.publish(
            telemetry_topic(self.device_id, self.settings.topic_prefix),
            json.dumps(frame),
            qos=1,
        )

    def _publish_presence(self, status: str, *, wait: bool = False) -> None:
        result = self.client.publish(
            presence_topic(self.device_id, self.settings.topic_prefix),
            json.dumps(
                {
                    "device_id": self.device_id,
                    "status": status,
                    "run_id": self.settings.run_id,
                    "timestamp": utc_now(),
                }
            ),
            qos=1,
            retain=True,
        )
        if wait:
            result.wait_for_publish(timeout=2)

    def _publish_command_ack(
        self, command_type: str, action: str, accepted: bool
    ) -> None:
        self.client.publish(
            f"{self.settings.topic_prefix}/sim/events/{self.device_id}",
            json.dumps(
                {
                    "device_id": self.device_id,
                    "command_type": command_type,
                    "action": action,
                    "accepted": accepted,
                    "state": self.state,
                    "scenario_id": self.scenario_id,
                    "timestamp": utc_now(),
                }
            ),
            qos=1,
        )

    def noise(self, amplitude: float) -> float:
        if self.settings.noise <= 0:
            return 0.0
        return self.rng.uniform(-amplitude, amplitude) * self.settings.noise

    def reset(self) -> None:
        self.state = "NORMAL"
        self.scenario_id = None
        self.on_reset()

    def on_reset(self) -> None:
        return None

    def on_quarantine(self) -> None:
        return None

    def on_decoy(self) -> bool:
        return False

    @abstractmethod
    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def metrics(self) -> dict[str, str | int | float | bool]:
        raise NotImplementedError

    def log(self, message: str) -> None:
        print(f"[{self.device_id}] {message}", flush=True)


def run_device(device_class: type[DeviceT]) -> None:
    parser = argparse.ArgumentParser(description=device_class.__name__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--noise", type=float)
    parser.add_argument("--interval", type=float)
    args = parser.parse_args()
    settings = SimSettings.from_env()
    if args.seed is not None or args.noise is not None or args.interval is not None:
        settings = SimSettings(
            broker_host=settings.broker_host,
            broker_port=settings.broker_port,
            topic_prefix=settings.topic_prefix,
            interval_seconds=args.interval or settings.interval_seconds,
            seed=args.seed if args.seed is not None else settings.seed,
            noise=args.noise if args.noise is not None else settings.noise,
            run_id=settings.run_id,
            log_level=settings.log_level,
        )
    device = device_class(settings)
    signal.signal(signal.SIGINT, lambda *_: device.stop())
    signal.signal(signal.SIGTERM, lambda *_: device.stop())
    device.run()
