"""Operator CLI that publishes the same attack trigger contract as Role 2."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from sim.common.messages import new_uuid, serialize_payload, validate_payload
from sim.verify_lab import load_env_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "attack_type",
        choices=("spoof_sensor", "coordinated_intrusion", "prompt_injection"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1884)
    parser.add_argument("--env-file", type=Path, default=Path("sim/.env"))
    args = parser.parse_args()

    environment = load_env_file(args.env_file)
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": "1.0",
        "request_id": new_uuid(),
        "attack_type": args.attack_type,
        "requested_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
        "requested_by": "backend",
    }
    validate_payload(Path("sim/contracts"), "attack_trigger.schema.json", payload)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"watchdog-trigger-{payload['request_id'][:8]}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(
        environment["MQTT_BACKEND_USERNAME"],
        environment["MQTT_BACKEND_PASSWORD"],
    )
    client.connect(args.host, args.port, 15)
    client.loop_start()
    info = client.publish(
        "campus/lab1/sim/attack/trigger",
        serialize_payload(payload),
        qos=1,
        retain=False,
    )
    info.wait_for_publish(5)
    client.disconnect()
    client.loop_stop()
    if not info.is_published():
        raise SystemExit("Attack trigger was not acknowledged")
    print(f"triggered={args.attack_type} request_id={payload['request_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
