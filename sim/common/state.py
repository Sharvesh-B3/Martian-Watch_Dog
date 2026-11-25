"""Thread-safe baseline device model used by all Phase 2 services."""

from __future__ import annotations

import random
import threading
from abc import ABC, abstractmethod
from typing import Any, Mapping

from sim.common.config import DeviceIdentity
from sim.common.messages import build_telemetry


class DeviceModel(ABC):
    """Owns device state and creates one complete telemetry envelope per sample."""

    def __init__(self, identity: DeviceIdentity, seed: int | None, schema_dir: Any):
        self.identity = identity
        self.schema_dir = schema_dir
        self.rng = random.Random(seed)
        self._lock = threading.RLock()
        self._status = identity.normal_status
        self._correlation_id: str | None = None
        self._note: str | None = None

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def telemetry(self) -> dict[str, Any]:
        with self._lock:
            status = self._status
            metrics = dict(self.sample_metrics())
            correlation_id = self._correlation_id
            note = self._note
        return build_telemetry(
            schema_dir=self.schema_dir,
            device_id=self.identity.device_id,
            device_type=self.identity.device_type,
            status=status,
            metrics=metrics,
            correlation_id=correlation_id,
            note=note,
        )

    def apply_injection(self, evidence: str, request_id: str) -> None:
        raise ValueError(f"{self.identity.device_id} does not support injection {evidence}")

    def apply_action(self, action: str, correlation_id: str) -> None:
        with self._lock:
            if action in {"RESTORE", "RESET"}:
                self._reset_locked()
                return
            if action == "QUARANTINE" and self.identity.device_type != "decoy_twin":
                self._status = "quarantined"
                self._correlation_id = correlation_id
                self._note = None
                return
            raise ValueError(f"Unsupported action {action} for {self.identity.device_id}")

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()

    def _reset_locked(self) -> None:
        self._status = self.identity.normal_status
        self._correlation_id = None
        self._note = None

    @abstractmethod
    def sample_metrics(self) -> Mapping[str, Any]:
        """Return one strict device-specific metrics object."""
