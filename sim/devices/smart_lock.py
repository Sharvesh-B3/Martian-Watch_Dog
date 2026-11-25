"""Normal baseline model for smart_lock_01."""

from __future__ import annotations

from typing import Any, Mapping

from sim.common.config import DeviceIdentity
from sim.common.mqtt import run_device
from sim.common.state import DeviceModel


IDENTITY = DeviceIdentity(
    device_id="smart_lock_01",
    device_type="smart_lock",
    client_id="watchdog-smart-lock-01",
    mqtt_username="device_smart_lock_01",
    default_seed=101,
)


class SmartLockModel(DeviceModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._locked = True
        self._door_closed = True
        self._failed_attempts = 0

    def sample_metrics(self) -> Mapping[str, Any]:
        return {
            "locked": self._locked,
            "door_closed": self._door_closed,
            "failed_attempts": self._failed_attempts,
            "last_badge_id": None,
        }

    def apply_injection(self, evidence: str, request_id: str) -> None:
        if evidence != "unauthorized_unlock":
            return super().apply_injection(evidence, request_id)
        with self._lock:
            if self._status == "quarantined":
                return
            self._status = "warning"
            self._correlation_id = request_id
            self._locked = False
            self._door_closed = False
            self._failed_attempts = 1

    def apply_action(self, action: str, correlation_id: str) -> None:
        super().apply_action(action, correlation_id)
        if action == "QUARANTINE":
            with self._lock:
                self._locked = True
                self._door_closed = True

    def _reset_locked(self) -> None:
        super()._reset_locked()
        self._locked = True
        self._door_closed = True
        self._failed_attempts = 0


def main() -> None:
    run_device(SmartLockModel, IDENTITY)


if __name__ == "__main__":
    main()
