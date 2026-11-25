"""Physically plausible normal baseline model for power_meter_01."""

from __future__ import annotations

from typing import Any, Mapping

from sim.common.config import DeviceIdentity
from sim.common.mqtt import run_device
from sim.common.state import DeviceModel


IDENTITY = DeviceIdentity(
    device_id="power_meter_01",
    device_type="power_meter",
    client_id="watchdog-power-meter-01",
    mqtt_username="device_power_meter_01",
    default_seed=104,
)


class PowerMeterModel(DeviceModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._port_scan = False

    def sample_metrics(self) -> Mapping[str, Any]:
        if self._port_scan:
            return {"load_kw": 3.4, "voltage": 230.0, "outbound_conns": 148}
        return {
            "load_kw": round(self.rng.uniform(2.8, 3.8), 2),
            "voltage": round(self.rng.uniform(228.0, 232.0), 1),
            "outbound_conns": self.rng.randint(1, 3),
        }

    def apply_injection(self, evidence: str, request_id: str) -> None:
        if evidence != "port_scan":
            return super().apply_injection(evidence, request_id)
        with self._lock:
            if self._status == "quarantined":
                return
            self._status = "warning"
            self._correlation_id = request_id
            self._port_scan = True

    def _reset_locked(self) -> None:
        super()._reset_locked()
        self._port_scan = False


def main() -> None:
    run_device(PowerMeterModel, IDENTITY)


if __name__ == "__main__":
    main()
