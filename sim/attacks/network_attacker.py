"""Synthetic attacker whose MQTT connection is physically rerouted by the gateway."""

import json
import os
import signal
import threading
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.protocol import utc_now


class NetworkAttacker:
    def __init__(self) -> None:
        self.host = os.getenv("SIM_GATEWAY_HOST", "127.0.0.1")
        self.port = int(os.getenv("SIM_GATEWAY_PORT", "1884"))
        self.prefix = os.getenv("SIM_TOPIC_PREFIX", "campus/lab1").rstrip("/")
        self._stop = threading.Event()
        self._connected = threading.Event()
        self.sequence = 0
        self.environment = "UNKNOWN"
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="synthetic-network-attacker",
            clean_session=True,
        )
        self.client.reconnect_delay_set(1, 5)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
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
            return
        self._connected.set()
        client.subscribe(f"{self.prefix}/environment", qos=1)
        print(
            f"[network-attacker] connected to gateway {self.host}:{self.port}",
            flush=True,
        )

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
            print("[network-attacker] session dropped; reconnecting", flush=True)

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload.decode())
        except Exception:
            return
        environment = str(payload.get("environment", "UNKNOWN"))
        if environment != self.environment:
            self.environment = environment
            print(f"[network-attacker] broker environment: {environment}", flush=True)

    def run(self) -> None:
        self.client.connect(self.host, self.port, 30)
        self.client.loop_start()
        try:
            while not self._stop.wait(1):
                if not self._connected.is_set():
                    continue
                self.sequence += 1
                self.client.publish(
                    f"{self.prefix}/attacker/probe",
                    json.dumps(
                        {
                            "source": "10.0.4.66",
                            "command": f"ENUMERATE_LAB_ASSETS_{self.sequence}",
                            "sequence": self.sequence,
                            "environment_seen": self.environment,
                            "timestamp": utc_now(),
                        }
                    ),
                    qos=1,
                )
        finally:
            self.client.disconnect()
            self.client.loop_stop()

    def stop(self) -> None:
        self._stop.set()


if __name__ == "__main__":
    attacker = NetworkAttacker()
    signal.signal(signal.SIGINT, lambda *_: attacker.stop())
    signal.signal(signal.SIGTERM, lambda *_: attacker.stop())
    attacker.run()
