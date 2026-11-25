"""Safe live Phase 2 verification for an already running local MQTT lab.

The verifier is deliberately read-only: it never publishes controls, attack
triggers, injections, Decoy input, or malformed telemetry. Device write ACLs
are proven by observing their live output; all eight principals receive
positive and negative subscription checks where the signed ACL defines them.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.messages import ContractValidationError, validate_payload


CANONICAL_IDS = {
    "smart_lock_01",
    "rfid_scanner_01",
    "air_quality_01",
    "power_meter_01",
    "decoy_twin_01",
}

ACCOUNT_ENV_KEYS = {
    "smart_lock": ("MQTT_SMART_LOCK_USERNAME", "MQTT_SMART_LOCK_PASSWORD"),
    "rfid_scanner": (
        "MQTT_RFID_SCANNER_USERNAME",
        "MQTT_RFID_SCANNER_PASSWORD",
    ),
    "air_quality": ("MQTT_AIR_QUALITY_USERNAME", "MQTT_AIR_QUALITY_PASSWORD"),
    "power_meter": ("MQTT_POWER_METER_USERNAME", "MQTT_POWER_METER_PASSWORD"),
    "decoy_twin": ("MQTT_DECOY_TWIN_USERNAME", "MQTT_DECOY_TWIN_PASSWORD"),
    "attack_controller": (
        "MQTT_ATTACK_CONTROLLER_USERNAME",
        "MQTT_ATTACK_CONTROLLER_PASSWORD",
    ),
    "backend": ("MQTT_BACKEND_USERNAME", "MQTT_BACKEND_PASSWORD"),
    "observer": ("MQTT_OBSERVER_USERNAME", "MQTT_OBSERVER_PASSWORD"),
}


class VerificationError(RuntimeError):
    """Raised when observed lab behavior violates Phase 2 contracts."""


def load_env_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise VerificationError(f"Cannot read credential file {path}: {exc}") from exc

    values: dict[str, str] = {}
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise VerificationError(f"Invalid env line {line_number} in {path}")
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if not key or key in values:
            raise VerificationError(f"Invalid or duplicate env key on line {line_number}")
        values[key] = value.strip()

    required = {key for pair in ACCOUNT_ENV_KEYS.values() for key in pair}
    missing = sorted(key for key in required if not values.get(key))
    if missing:
        raise VerificationError(f"Credential file is missing values: {', '.join(missing)}")
    return values


class ProbeClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        label: str,
        username: str | None,
        password: str | None,
    ) -> None:
        self.host = host
        self.port = port
        self.label = label
        self.connected = threading.Event()
        self.connection_result: mqtt.ReasonCode | None = None
        self.subscription_results: dict[int, list[mqtt.ReasonCode]] = {}
        self.subscription_events: dict[int, threading.Event] = {}
        self.messages: queue.Queue[mqtt.MQTTMessage] = queue.Queue()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"watchdog-verify-{label}-{uuid.uuid4().hex[:8]}",
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        if username is not None:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message

    def start(self, timeout: float = 5.0) -> mqtt.ReasonCode:
        result = self.client.connect(self.host, self.port, keepalive=15)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise VerificationError(f"{self.label}: TCP/MQTT connect returned rc={result}")
        self.client.loop_start()
        if not self.connected.wait(timeout):
            self.stop()
            raise VerificationError(f"{self.label}: connection callback timed out")
        assert self.connection_result is not None
        return self.connection_result

    def stop(self) -> None:
        try:
            self.client.disconnect()
        except (OSError, RuntimeError):
            pass
        self.client.loop_stop()

    def subscription_allowed(self, topic: str, timeout: float = 5.0) -> bool:
        result, message_id = self.client.subscribe(topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise VerificationError(
                f"{self.label}: subscribe request for {topic} returned rc={result}"
            )
        event = threading.Event()
        self.subscription_events[message_id] = event
        if message_id in self.subscription_results:
            event.set()
        if not event.wait(timeout):
            raise VerificationError(f"{self.label}: SUBACK timed out for {topic}")
        reasons = self.subscription_results.pop(message_id)
        self.subscription_events.pop(message_id, None)
        return bool(reasons) and all(not reason.is_failure for reason in reasons)

    def publish_marker(self, topic: str, marker: str, timeout: float = 5.0) -> bool:
        info = self.client.publish(topic, payload=marker, qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return False
        try:
            info.wait_for_publish(timeout=timeout)
        except RuntimeError:
            return False
        return info.is_published()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, flags, properties
        self.connection_result = reason_code
        self.connected.set()

    def _on_subscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        message_id: int,
        reason_code_list: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, properties
        self.subscription_results[message_id] = list(reason_code_list)
        event = self.subscription_events.get(message_id)
        if event is not None:
            event.set()

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        del client, userdata
        self.messages.put(message)


def account_credentials(
    environment: dict[str, str],
    account: str,
) -> tuple[str, str]:
    username_key, password_key = ACCOUNT_ENV_KEYS[account]
    return environment[username_key], environment[password_key]


def verify_anonymous_denied(host: str, port: int) -> None:
    client = ProbeClient(
        host=host,
        port=port,
        label="anonymous",
        username=None,
        password=None,
    )
    try:
        reason = client.start()
        if not reason.is_failure:
            raise VerificationError("Anonymous MQTT connection was unexpectedly accepted")
    finally:
        client.stop()


def verify_subscription_acl(
    *,
    host: str,
    port: int,
    environment: dict[str, str],
) -> None:
    cases: dict[str, list[str]] = {
        "smart_lock": ["campus/lab1/control/smart_lock_01", "campus/lab1/sim/reset"],
        "rfid_scanner": ["campus/lab1/control/rfid_scanner_01", "campus/lab1/sim/reset"],
        "air_quality": [
            "campus/lab1/control/air_quality_01",
            "campus/lab1/sim/inject/air_quality_01",
        ],
        "power_meter": [
            "campus/lab1/control/power_meter_01",
            "campus/lab1/sim/inject/power_meter_01",
        ],
        "decoy_twin": [
            "campus/lab1/control/decoy_twin_01",
            "campus/lab1/decoy/input/+",
        ],
        "attack_controller": [
            "campus/lab1/sim/attack/trigger",
            "campus/lab1/decoy/events",
        ],
        "backend": ["campus/lab1/telemetry/+", "campus/lab1/control_ack/+"],
        "observer": ["campus/lab1/#"],
    }

    for account, allowed_topics in cases.items():
        username, password = account_credentials(environment, account)
        client = ProbeClient(
            host=host,
            port=port,
            label=f"acl-{account}",
            username=username,
            password=password,
        )
        try:
            reason = client.start()
            if reason.is_failure:
                raise VerificationError(f"{account}: valid credential was rejected: {reason}")
            for topic in allowed_topics:
                if not client.subscription_allowed(topic):
                    raise VerificationError(f"{account}: allowed subscription denied: {topic}")
        finally:
            client.stop()


def verify_write_acl(
    *,
    host: str,
    port: int,
    environment: dict[str, str],
) -> None:
    """Exercise one permitted and one forbidden write per principal.

    This is safe only in the Phase 2 topology, where no attack controller,
    backend consumer, or device control/injection subscriber is running.
    """

    allowed_topics = {
        "smart_lock": "campus/lab1/presence/smart_lock_01",
        "rfid_scanner": "campus/lab1/presence/rfid_scanner_01",
        "air_quality": "campus/lab1/presence/air_quality_01",
        "power_meter": "campus/lab1/presence/power_meter_01",
        "decoy_twin": "campus/lab1/decoy/events",
        "attack_controller": "campus/lab1/test/ground_truth",
        "backend": "campus/lab1/control/smart_lock_01",
    }

    observer_username, observer_password = account_credentials(environment, "observer")
    observer = ProbeClient(
        host=host,
        port=port,
        label="write-acl-observer",
        username=observer_username,
        password=observer_password,
    )
    try:
        reason = observer.start()
        if reason.is_failure or not observer.subscription_allowed("campus/lab1/#"):
            raise VerificationError("Observer could not monitor write-ACL probes")

        for account, topic in allowed_topics.items():
            marker = f"ACL_ALLOW_{account}_{uuid.uuid4().hex}"
            publisher = _account_probe(host, port, environment, account, "allow")
            try:
                if not publisher.publish_marker(topic, marker):
                    raise VerificationError(f"{account}: permitted write failed for {topic}")
                if not _wait_for_marker(observer.messages, marker, timeout=5.0):
                    raise VerificationError(
                        f"{account}: permitted write was not delivered on {topic}"
                    )
            finally:
                publisher.stop()

        for account in ACCOUNT_ENV_KEYS:
            marker = f"ACL_DENY_{account}_{uuid.uuid4().hex}"
            forbidden_topic = f"campus/lab1/forbidden/{account}"
            publisher = _account_probe(host, port, environment, account, "deny")
            try:
                # MQTT 3.1.1 may disconnect, withhold PUBACK, or complete the
                # flow while dropping an unauthorized publication. Delivery
                # to the authorized observer is the decisive failure signal.
                publisher.publish_marker(forbidden_topic, marker, timeout=2.0)
                if _wait_for_marker(observer.messages, marker, timeout=2.0):
                    raise VerificationError(
                        f"{account}: forbidden write was delivered on {forbidden_topic}"
                    )
            finally:
                publisher.stop()

        _verify_denied_read_delivery(
            host=host,
            port=port,
            environment=environment,
        )
    finally:
        observer.stop()


def _verify_denied_read_delivery(
    *,
    host: str,
    port: int,
    environment: dict[str, str],
) -> None:
    # Mosquitto may grant a wildcard SUBACK and enforce read ACLs only when a
    # matching message is delivered. Absence of this authorized unique marker
    # is therefore the decisive negative-read check.
    cases = (
        ("smart_lock", "campus/lab1/control/air_quality_01", "backend"),
        ("smart_lock", "campus/lab1/telemetry/+", "air_quality"),
        ("rfid_scanner", "campus/lab1/control/smart_lock_01", "backend"),
        ("rfid_scanner", "campus/lab1/test/ground_truth", "attack_controller"),
        ("air_quality", "campus/lab1/control/power_meter_01", "backend"),
        ("air_quality", "campus/lab1/test/ground_truth", "attack_controller"),
        ("power_meter", "campus/lab1/control/air_quality_01", "backend"),
        ("power_meter", "campus/lab1/decoy/events", "decoy_twin"),
        ("decoy_twin", "campus/lab1/control/smart_lock_01", "backend"),
        ("decoy_twin", "campus/lab1/test/ground_truth", "attack_controller"),
        ("attack_controller", "campus/lab1/control/+", "backend"),
        ("attack_controller", "campus/lab1/telemetry/+", "smart_lock"),
        ("backend", "campus/lab1/sim/inject/+", "attack_controller"),
        ("backend", "campus/lab1/test/ground_truth", "attack_controller"),
    )

    for reader_account, denied_filter, writer_account in cases:
        reader = _account_probe(host, port, environment, reader_account, "denied-read")
        try:
            if not reader.subscription_allowed(denied_filter):
                continue
            marker = f"ACL_READ_DENY_{reader_account}_{uuid.uuid4().hex}"
            concrete_topic = _concrete_probe_topic(denied_filter)
            writer = _account_probe(host, port, environment, writer_account, "read-source")
            try:
                if not writer.publish_marker(concrete_topic, marker):
                    raise VerificationError(
                        f"{writer_account}: could not publish denied-read probe to {concrete_topic}"
                    )
                if _wait_for_marker(reader.messages, marker, timeout=2.0):
                    raise VerificationError(
                        f"{reader_account}: received forbidden message matching {denied_filter}"
                    )
            finally:
                writer.stop()
        finally:
            reader.stop()


def _concrete_probe_topic(topic_filter: str) -> str:
    replacements = {
        "campus/lab1/telemetry/+": "campus/lab1/telemetry/smart_lock_01",
        "campus/lab1/control/+": "campus/lab1/control/smart_lock_01",
        "campus/lab1/sim/inject/+": "campus/lab1/sim/inject/smart_lock_01",
    }
    return replacements.get(topic_filter, topic_filter)


def _account_probe(
    host: str,
    port: int,
    environment: dict[str, str],
    account: str,
    suffix: str,
) -> ProbeClient:
    username, password = account_credentials(environment, account)
    client = ProbeClient(
        host=host,
        port=port,
        label=f"write-{account}-{suffix}",
        username=username,
        password=password,
    )
    reason = client.start()
    if reason.is_failure:
        client.stop()
        raise VerificationError(f"{account}: valid credential rejected during write test")
    return client


def _wait_for_marker(
    messages: queue.Queue[mqtt.MQTTMessage],
    marker: str,
    *,
    timeout: float,
) -> bool:
    deadline = time.monotonic() + timeout
    expected = marker.encode("utf-8")
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            message = messages.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if message.payload == expected:
            return True
    return False


def verify_normal_profile(payload: dict[str, Any]) -> None:
    device_id = payload["device_id"]
    status = payload["status"]
    metrics = payload["metrics"]

    if payload["correlation_id"] is not None or payload["metadata"] != {"note": None}:
        raise VerificationError(f"{device_id}: baseline contains attack correlation or note")

    if device_id == "smart_lock_01":
        expected = {
            "locked": True,
            "door_closed": True,
            "failed_attempts": 0,
            "last_badge_id": None,
        }
        if status != "normal" or metrics != expected:
            raise VerificationError("smart_lock_01 is not in the signed normal baseline")
    elif device_id == "rfid_scanner_01":
        expected = {"event": "idle", "badge_id": None, "authorized": False}
        if status != "normal" or metrics != expected:
            raise VerificationError("rfid_scanner_01 is not idle")
    elif device_id == "air_quality_01":
        if status != "normal" or not (
            5 <= metrics["pm25"] <= 20
            and 410 <= metrics["co2_ppm"] <= 480
            and 20 <= metrics["temp_c"] <= 24
        ):
            raise VerificationError("air_quality_01 is outside normal physical bounds")
    elif device_id == "power_meter_01":
        if status != "normal" or not (
            2.8 <= metrics["load_kw"] <= 3.8
            and 228 <= metrics["voltage"] <= 232
            and 1 <= metrics["outbound_conns"] <= 3
        ):
            raise VerificationError("power_meter_01 is outside normal physical bounds")
    elif device_id == "decoy_twin_01":
        expected = {"mode": "standby", "active_traps": 0, "captured_payloads": 0}
        if status != "decoy" or metrics != expected:
            raise VerificationError("decoy_twin_01 is not in standby")
    else:
        raise VerificationError(f"Unexpected telemetry device ID: {device_id}")


def verify_live_telemetry(
    *,
    host: str,
    port: int,
    environment: dict[str, str],
    schema_dir: Path,
    timeout: float,
) -> dict[str, int]:
    username, password = account_credentials(environment, "observer")
    client = ProbeClient(
        host=host,
        port=port,
        label="telemetry",
        username=username,
        password=password,
    )
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_ids: set[str] = set()
    deadline = time.monotonic() + timeout

    try:
        reason = client.start()
        if reason.is_failure:
            raise VerificationError(f"Observer credential rejected: {reason}")
        if not client.subscription_allowed("campus/lab1/telemetry/+"):
            raise VerificationError("Observer telemetry subscription was denied")

        while time.monotonic() < deadline:
            if all(len(samples[device_id]) >= 2 for device_id in CANONICAL_IDS):
                break
            remaining = max(0.0, deadline - time.monotonic())
            try:
                message = client.messages.get(timeout=min(1.0, remaining))
            except queue.Empty:
                continue
            if message.retain:
                raise VerificationError(f"Retained telemetry received on {message.topic}")
            try:
                payload = json.loads(message.payload.decode("utf-8"))
                validate_payload(schema_dir, "telemetry.schema.json", payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ContractValidationError) as exc:
                raise VerificationError(f"Invalid live telemetry on {message.topic}: {exc}") from exc
            expected_topic = f"campus/lab1/telemetry/{payload['device_id']}"
            if message.topic != expected_topic:
                raise VerificationError(
                    f"Topic/payload mismatch: {message.topic} != {expected_topic}"
                )
            if payload["event_id"] in event_ids:
                # QoS 1 is at-least-once. A redelivery is expected to be
                # deduplicated rather than treated as a second sample.
                continue
            event_ids.add(payload["event_id"])
            event_time = _parse_timestamp(payload["timestamp"])
            age = (datetime.now(timezone.utc) - event_time).total_seconds()
            if age < -5:
                raise VerificationError(
                    f"{payload['device_id']}: telemetry is more than 5s in the future"
                )
            if age > 60:
                raise VerificationError(
                    f"{payload['device_id']}: telemetry is more than 60s stale"
                )
            verify_normal_profile(payload)
            samples[payload["device_id"]].append(payload)

        missing = {
            device_id: 2 - len(samples[device_id])
            for device_id in CANONICAL_IDS
            if len(samples[device_id]) < 2
        }
        if missing:
            raise VerificationError(f"Timed out waiting for telemetry samples: {missing}")

        for device_id, device_samples in samples.items():
            first = _parse_timestamp(device_samples[0]["timestamp"])
            second = _parse_timestamp(device_samples[1]["timestamp"])
            cadence = (second - first).total_seconds()
            if not 1.0 <= cadence <= 5.0:
                raise VerificationError(
                    f"{device_id}: observed telemetry cadence {cadence:.3f}s, expected ~2s"
                )
        return {device_id: len(device_samples) for device_id, device_samples in samples.items()}
    finally:
        client.stop()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1884)
    parser.add_argument("--env-file", type=Path, default=Path("sim/.env"))
    parser.add_argument("--schema-dir", type=Path, default=Path("sim/contracts"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--skip-acl",
        action="store_true",
        help="Collect telemetry and test anonymous denial without per-account SUBACK checks.",
    )
    parser.add_argument(
        "--include-write-acl",
        action="store_true",
        help=(
            "Publish isolated ACL markers. Use only with the Phase 2 six-service "
            "topology before attack/control consumers are added."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        environment = load_env_file(args.env_file)
        verify_anonymous_denied(args.host, args.port)
        counts = verify_live_telemetry(
            host=args.host,
            port=args.port,
            environment=environment,
            schema_dir=args.schema_dir,
            timeout=args.timeout,
        )
        if not args.skip_acl:
            verify_subscription_acl(
                host=args.host,
                port=args.port,
                environment=environment,
            )
        if args.include_write_acl:
            verify_write_acl(
                host=args.host,
                port=args.port,
                environment=environment,
            )
    except (VerificationError, OSError) as exc:
        print(f"Phase 2 live verification FAILED: {exc}", file=sys.stderr)
        return 1

    summary = ", ".join(f"{device_id}={counts[device_id]}" for device_id in sorted(counts))
    print(f"Phase 2 live verification passed: {summary}")
    print("Anonymous access denied; allowed subscription ACL checks passed.")
    if args.include_write_acl:
        print("Allowed/forbidden write ACLs and denied-read delivery checks passed.")
    else:
        print("Operational write-ACL probes were skipped; add --include-write-acl in Phase 2 only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
