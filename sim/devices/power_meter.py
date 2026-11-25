"""Power and network telemetry simulator."""

from collections.abc import Mapping
import math
from typing import Any

from sim.common.mqtt_device import BaseMqttDevice, run_device
from sim.common.settings import SimSettings


class PowerMeterDevice(BaseMqttDevice):
    def __init__(self, settings: SimSettings) -> None:
        super().__init__("meter_01", settings)
        self.port_scan_active = False

    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        if action != "PORT_SCAN":
            return False
        self.port_scan_active = True
        self.state = "WARNING"
        return True

    def on_reset(self) -> None:
        self.port_scan_active = False

    def metrics(self) -> dict[str, str | int | float | bool]:
        if self.port_scan_active:
            return {
                "power_kw": 2.1,
                "voltage": 230,
                "network_conns": 148,
                "anomaly_flag": "PORT_SCAN_SUBNET_10.0.4.0/24",
            }
        phase = self.sequence
        load = 2.1 + math.sin(phase / 9) * 0.2 + self.noise(0.15)
        voltage = 230 + math.sin(phase / 18) * 0.8 + self.noise(0.5)
        return {
            "power_kw": round(load, 2),
            "voltage": round(voltage, 1),
            "network_conns": 1 + phase % 3,
            "anomaly_flag": "NONE",
        }


if __name__ == "__main__":
    run_device(PowerMeterDevice)
