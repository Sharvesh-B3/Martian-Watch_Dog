"""Contract-valid message construction and JSON serialization."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


class ContractValidationError(ValueError):
    """Raised before a simulator publishes a contract-invalid payload."""


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def new_uuid() -> str:
    return str(uuid.uuid4())


def build_telemetry(
    *,
    schema_dir: Path,
    device_id: str,
    device_type: str,
    status: str,
    metrics: Mapping[str, Any],
    correlation_id: str | None = None,
    note: str | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "event_id": event_id or new_uuid(),
        "correlation_id": correlation_id,
        "device_id": device_id,
        "device_type": device_type,
        "zone": "lab-wing-a",
        "timestamp": timestamp or utc_now(),
        "status": status,
        "metrics": dict(metrics),
        "metadata": {"note": note},
    }
    validate_payload(schema_dir, "telemetry.schema.json", payload)
    return payload


def build_presence(
    *,
    schema_dir: Path,
    device_id: str,
    device_type: str,
    client_id: str,
    session_started_at: str,
    state: str,
    reason: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "event_id": event_id or new_uuid(),
        "device_id": device_id,
        "device_type": device_type,
        "zone": "lab-wing-a",
        "client_id": client_id,
        "session_started_at": session_started_at,
        "state": state,
        "reason": reason,
    }
    validate_payload(schema_dir, "presence.schema.json", payload)
    return payload


def build_control_ack(
    *,
    schema_dir: Path,
    command_id: str,
    correlation_id: str,
    target_id: str,
    action: str,
    status: str,
    observed_state: str,
    code: str,
    detail: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "event_id": new_uuid(),
        "command_id": command_id,
        "correlation_id": correlation_id,
        "target_id": target_id,
        "action": action,
        "status": status,
        "observed_state": observed_state,
        "timestamp": utc_now(),
        "code": code,
        "detail": detail,
    }
    validate_payload(schema_dir, "control_ack.schema.json", payload)
    return payload


def build_decoy_event(
    *,
    schema_dir: Path,
    request_id: str,
    route_command_id: str,
    target_device_id: str,
    event_type: str,
    active_traps: int,
    captured_payloads: int,
    capture_id: str | None = None,
    payload_sha256: str | None = None,
    captured_bytes: int = 0,
    safe_summary: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "event_id": new_uuid(),
        "request_id": request_id,
        "route_command_id": route_command_id,
        "decoy_device_id": "decoy_twin_01",
        "target_device_id": target_device_id,
        "timestamp": utc_now(),
        "event_type": event_type,
        "capture_id": capture_id,
        "payload_sha256": payload_sha256,
        "captured_bytes": captured_bytes,
        "active_traps": active_traps,
        "captured_payloads": captured_payloads,
        "safe_summary": safe_summary,
    }
    validate_payload(schema_dir, "decoy_event.schema.json", payload)
    return payload


def serialize_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def validate_payload(schema_dir: Path, schema_name: str, payload: Any) -> None:
    validator = _validator(str(schema_dir.resolve()), schema_name)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if not errors:
        return
    first = errors[0]
    location = "/".join(str(part) for part in first.absolute_path) or "<root>"
    raise ContractValidationError(
        f"{schema_name} rejected payload at {location}: {first.message}"
    )


@lru_cache(maxsize=16)
def _validator(schema_dir: str, schema_name: str) -> Draft202012Validator:
    path = Path(schema_dir) / schema_name
    try:
        with path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"Cannot load schema {path}: {exc}") from exc
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())
