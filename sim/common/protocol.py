"""Stable MQTT topics and message helpers shared by Role 1 components."""

from datetime import datetime, timezone
from uuid import uuid4

TOPIC_PREFIX = "campus/lab1"

DEVICE_TOPICS = {
    "door_lock_01": "door_lock",
    "rfid_01": "rfid_scanner",
    "aq_sensor_01": "air_quality",
    "meter_01": "smart_meter",
    "cctv_01": "cctv_cam",
    "decoy_twin_01": "decoy_twin",
}

DEVICE_IDS = tuple(DEVICE_TOPICS)

INTERNAL_TOPIC_SEGMENTS = (
    "/control/",
    "/sim/attack/",
    "/sim/events/",
    "/presence/",
    "/redteam/",
    "/attacker/",
    "/decoy/capture",
    "/environment",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def new_run_id() -> str:
    return f"lab-{uuid4().hex[:10]}"


def new_scenario_id(attack_type: str) -> str:
    safe_type = attack_type.replace("_", "-")
    return f"atk-{safe_type}-{uuid4().hex[:10]}"


def telemetry_topic(device_id: str, prefix: str = TOPIC_PREFIX) -> str:
    return f"{prefix}/{DEVICE_TOPICS[device_id]}"


def control_topic(device_id: str, prefix: str = TOPIC_PREFIX) -> str:
    return f"{prefix}/control/{device_id}"


def attack_topic(device_id: str, prefix: str = TOPIC_PREFIX) -> str:
    return f"{prefix}/sim/attack/{device_id}"


def presence_topic(device_id: str, prefix: str = TOPIC_PREFIX) -> str:
    return f"{prefix}/presence/{device_id}"


def is_internal_topic(topic: str) -> bool:
    return any(segment in topic for segment in INTERNAL_TOPIC_SEGMENTS)
