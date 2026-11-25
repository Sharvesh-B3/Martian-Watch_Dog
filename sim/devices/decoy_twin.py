"""Standby baseline model for decoy_twin_01."""

from __future__ import annotations

from typing import Any, Mapping

from sim.common.config import DeviceIdentity
from sim.common.mqtt import run_device
from sim.common.state import DeviceModel


IDENTITY = DeviceIdentity(
    device_id="decoy_twin_01",
    device_type="decoy_twin",
    client_id="watchdog-decoy-twin-01",
    mqtt_username="device_decoy_twin_01",
    default_seed=105,
    normal_status="decoy",
)


class DecoyTwinModel(DeviceModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode = "standby"
        self._active_traps = 0
        self._captured_payloads = 0

    def sample_metrics(self) -> Mapping[str, Any]:
        return {
            "mode": self._mode,
            "active_traps": self._active_traps,
            "captured_payloads": self._captured_payloads,
        }

    def apply_action(self, action: str, correlation_id: str) -> None:
        with self._lock:
            if action == "ACTIVATE_DECOY":
                self._mode = "active"
                self._active_traps = 1
                self._correlation_id = correlation_id
                return
        super().apply_action(action, correlation_id)

    def capture(self, request_id: str) -> tuple[int, int]:
        with self._lock:
            if self._mode != "active":
                raise ValueError("Decoy Twin is not active")
            self._correlation_id = request_id
            self._captured_payloads += 1
            return self._active_traps, self._captured_payloads

    def _reset_locked(self) -> None:
        super()._reset_locked()
        self._mode = "standby"
        self._active_traps = 0
        self._captured_payloads = 0


def main() -> None:
    run_device(DecoyTwinModel, IDENTITY)


if __name__ == "__main__":
    main()
