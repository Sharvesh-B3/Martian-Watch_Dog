"""Deterministic RFID reader simulator."""

from collections.abc import Mapping
from typing import Any

from sim.common.mqtt_device import BaseMqttDevice, run_device
from sim.common.settings import SimSettings


class RfidScannerDevice(BaseMqttDevice):
    def __init__(self, settings: SimSettings) -> None:
        super().__init__("rfid_01", settings)
        self.event = "IDLE"
        self.badge_id: str | None = None
        self.scan_rate_per_min = 0
        self._event_until_sequence: int | None = None

    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        if action == "SUPPRESS_BADGE":
            self.state = "WARNING"
            self.event = "IDLE"
            self.badge_id = None
            self.scan_rate_per_min = 0
            self._event_until_sequence = None
            return True
        if action in {"BADGE_ACCEPTED", "BADGE_REJECTED"}:
            self.state = "NORMAL" if action == "BADGE_ACCEPTED" else "WARNING"
            self.event = "GRANTED" if action == "BADGE_ACCEPTED" else "DENIED"
            self.badge_id = str(payload.get("badge_id", "FAC-2049"))
            self.scan_rate_per_min = 1
            self._event_until_sequence = self.sequence + 1
            return True
        return False

    def on_reset(self) -> None:
        self.event = "IDLE"
        self.badge_id = None
        self.scan_rate_per_min = 0
        self._event_until_sequence = None

    def metrics(self) -> dict[str, str | int | float | bool]:
        if (
            self._event_until_sequence is not None
            and self.sequence > self._event_until_sequence
        ):
            self.state = "NORMAL"
            self.event = "IDLE"
            self.badge_id = None
            self.scan_rate_per_min = 0
            self._event_until_sequence = None
        metrics: dict[str, str | int | float | bool] = {
            "event": self.event,
            "scan_rate_per_min": self.scan_rate_per_min,
        }
        if self.badge_id is not None:
            metrics["badge_id"] = self.badge_id
        return metrics


if __name__ == "__main__":
    run_device(RfidScannerDevice)
