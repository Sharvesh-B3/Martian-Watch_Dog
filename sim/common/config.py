"""Strict environment configuration for one simulated device service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or unsafe."""


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    device_type: str
    client_id: str
    mqtt_username: str
    default_seed: int
    normal_status: str = "normal"


@dataclass(frozen=True)
class DeviceSettings:
    identity: DeviceIdentity
    mqtt_host: str
    mqtt_port: int
    mqtt_password: str = field(repr=False)
    telemetry_interval_seconds: float = 2.0
    keepalive_seconds: int = 30
    connect_timeout_seconds: float = 30.0
    seed: int | None = None
    health_file: Path = Path("/tmp/watchdog-health.json")
    schema_dir: Path = Path(__file__).resolve().parents[1] / "contracts"

    @classmethod
    def from_env(cls, identity: DeviceIdentity) -> "DeviceSettings":
        host = _required("MQTT_HOST")
        password = _required("MQTT_PASSWORD")
        configured_username = _required("MQTT_USERNAME")
        configured_client_id = _required("MQTT_CLIENT_ID")

        if configured_username != identity.mqtt_username:
            raise ConfigurationError(
                f"MQTT_USERNAME must be {identity.mqtt_username!r} for {identity.device_id}"
            )
        if configured_client_id != identity.client_id:
            raise ConfigurationError(
                f"MQTT_CLIENT_ID must be {identity.client_id!r} for {identity.device_id}"
            )

        port = _integer("MQTT_PORT", default=1883, minimum=1, maximum=65535)
        interval = _float(
            "TELEMETRY_INTERVAL_SECONDS",
            default=2.0,
            minimum=0.25,
            maximum=60.0,
        )
        keepalive = _integer(
            "MQTT_KEEPALIVE_SECONDS",
            default=30,
            minimum=5,
            maximum=300,
        )
        connect_timeout = _float(
            "MQTT_CONNECT_TIMEOUT_SECONDS",
            default=30.0,
            minimum=1.0,
            maximum=300.0,
        )

        seed_value = os.getenv("SIM_SEED", str(identity.default_seed)).strip()
        if seed_value.lower() == "random":
            seed: int | None = None
        else:
            try:
                seed = int(seed_value)
            except ValueError as exc:
                raise ConfigurationError(
                    "SIM_SEED must be an integer or the literal 'random'"
                ) from exc

        health_file = Path(
            os.getenv("HEALTH_FILE", "/tmp/watchdog-health.json").strip()
        )
        if not str(health_file):
            raise ConfigurationError("HEALTH_FILE cannot be empty")

        schema_dir = Path(
            os.getenv(
                "SCHEMA_DIR",
                str(Path(__file__).resolve().parents[1] / "contracts"),
            ).strip()
        )

        return cls(
            identity=identity,
            mqtt_host=host,
            mqtt_port=port,
            mqtt_password=password,
            telemetry_interval_seconds=interval,
            keepalive_seconds=keepalive,
            connect_timeout_seconds=connect_timeout,
            seed=seed,
            health_file=health_file,
            schema_dir=schema_dir,
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable {name} is missing")
    return value


def _integer(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(name: str, *, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value
