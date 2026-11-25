"""Deterministic idle baseline model for rfid_scanner_01."""

from __future__ import annotations

from typing import Any, Mapping

from sim.common.config import DeviceIdentity
from sim.common.mqtt import run_device
from sim.common.state import DeviceModel


IDENTITY = DeviceIdentity(
    device_id="rfid_scanner_01",
    device_type="rfid_scanner",
    client_id="watchdog-rfid-scanner-01",
    mqtt_username="device_rfid_scanner_01",
    default_seed=102,
)


class RfidScannerModel(DeviceModel):
    def sample_metrics(self) -> Mapping[str, Any]:
        return {
            "event": "idle",
            "badge_id": None,
            "authorized": False,
        }


def main() -> None:
    run_device(RfidScannerModel, IDENTITY)


if __name__ == "__main__":
    main()
