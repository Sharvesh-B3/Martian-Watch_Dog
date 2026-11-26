"""Human-readable MQTT timeline for the isolated synthetic lab."""

if __package__ in {None, ""}:
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.settings import SimSettings


def describe_event(topic: str, data: dict[str, Any]) -> str | None:
    if "/presence/" in topic:
        return f"PRESENCE {data.get('device_id')}: {data.get('status')}"
    if "/sim/events/" in topic:
        result = "accepted" if data.get("accepted") else "rejected"
        return (
            f"COMMAND {data.get('device_id')}: {data.get('action')} "
            f"({result}, state={data.get('state')})"
        )
    if topic.endswith("/decoy/capture"):
        return (
            f"DECOY CAPTURE #{data.get('captured_payloads')} "
            f"source={data.get('source')} command={data.get('command')} "
            f"hash={data.get('payload_hash')}"
        )
    if topic.endswith("/redteam/trigger"):
        return (
            f"RED TEAM {data.get('attack_type')} "
            f"scenario={data.get('scenario_id')}"
        )
    if data.get("heartbeat") == "OFFLINE":
        return f"CCTV TAMPER scenario={data.get('scenario_id')}"
    if data.get("last_rfid") == "UNAUTHORIZED_BYPASS":
        return f"FORCED UNLOCK scenario={data.get('scenario_id')}"
    if data.get("anomaly_flag") not in {None, "", "NONE"}:
        return (
            f"PORT SCAN connections={data.get('network_conns')} "
            f"scenario={data.get('scenario_id')}"
        )
    if "IGNORE ALL PREVIOUS INSTRUCTIONS" in str(data.get("status", "")).upper():
        return f"PROMPT INJECTION scenario={data.get('scenario_id')}"
    if data.get("co2_ppm", 0) > 1000:
        return f"SENSOR SPOOF CO2={data.get('co2_ppm')}"
    return None


def main() -> None:
    settings = SimSettings.from_env()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="live-attack-monitor",
    )

    def on_connect(
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        client.subscribe(f"{settings.topic_prefix}/#", qos=1)
        print(f"[monitor] watching {settings.topic_prefix}/#", flush=True)

    def on_message(
        client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            data = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        description = describe_event(message.topic, data)
        if description:
            print(f"[monitor] {description}", flush=True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.broker_host, settings.broker_port, 60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
