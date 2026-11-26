"""Import-safe interactive and one-shot Red Team controls."""

if __package__ in {None, ""}:
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
from uuid import uuid4

import paho.mqtt.client as mqtt

from sim.attacks.scenarios import (
    AttackType,
    publish_reset,
    publish_trigger,
    validate_attack_type,
)
from sim.common.protocol import utc_now
from sim.common.settings import SimSettings


def connect_client(settings: SimSettings | None = None) -> mqtt.Client:
    settings = settings or SimSettings.from_env()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"red-team-{uuid4().hex[:8]}",
    )
    client.connect(settings.broker_host, settings.broker_port, 60)
    client.loop_start()
    return client


def publish_one(attack_type: AttackType | str) -> str:
    validated = validate_attack_type(str(attack_type))
    settings = SimSettings.from_env()
    client = connect_client(settings)
    try:
        scenario_id = publish_trigger(
            client,
            validated,
            prefix=settings.topic_prefix,
        )
        print(
            f"[+] Triggered {validated} as {scenario_id}; state remains active "
            "until RESTORE/RESET.",
            flush=True,
        )
        return scenario_id
    finally:
        client.disconnect()
        client.loop_stop()


def send_control(
    client: mqtt.Client,
    settings: SimSettings,
    device_id: str,
    action: str,
) -> None:
    client.publish(
        f"{settings.topic_prefix}/control/{device_id}",
        json.dumps({"action": action.upper(), "timestamp": utc_now()}),
        qos=1,
    )


def main() -> None:
    settings = SimSettings.from_env()
    client = connect_client(settings)
    try:
        while True:
            print("\n=== AEGIS RED TEAM CONTROL PANEL ===")
            print("[1] Coordinated Intrusion (CCTV + Door + RFID + Port Scan)")
            print("[2] Sensor Spoofing")
            print("[3] Prompt Injection")
            print("[4] Manual Device Control")
            print("[r] Reset All Scenarios and Devices")
            print("[q] Quit")
            choice = input("Select > ").strip().lower()

            attack_by_choice: dict[str, AttackType] = {
                "1": "coordinated_intrusion",
                "2": "spoof_sensor",
                "3": "prompt_injection",
            }
            if choice in attack_by_choice:
                scenario_id = publish_trigger(
                    client,
                    attack_by_choice[choice],
                    prefix=settings.topic_prefix,
                )
                print(f"[+] Scenario active: {scenario_id}")
            elif choice == "4":
                device_id = input(
                    "Device ID (door_lock_01, aq_sensor_01, decoy_twin_01, ...): "
                ).strip()
                action = input(
                    "Action (QUARANTINE / DECOY / RESTORE / RESET): "
                ).strip()
                send_control(client, settings, device_id, action)
                print(f"[+] Sent {action.upper()} to {device_id}")
            elif choice == "r":
                publish_reset(client, prefix=settings.topic_prefix)
                print("[+] Reset published to controller and all devices")
            elif choice == "q":
                break
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
