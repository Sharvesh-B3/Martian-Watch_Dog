"""Internal CCTV heartbeat used as coordinated-attack evidence."""

from collections.abc import Mapping
from typing import Any

from sim.common.mqtt_device import BaseMqttDevice, run_device
from sim.common.settings import SimSettings


class CctvCameraDevice(BaseMqttDevice):
    def __init__(self, settings: SimSettings) -> None:
        super().__init__("cctv_01", settings)
        self.offline = False

    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        if action != "DROP_HEARTBEAT":
            return False
        self.offline = True
        self.state = "WARNING"
        return True

    def on_reset(self) -> None:
        self.offline = False

    def metrics(self) -> dict[str, str | int | float | bool]:
        return {
            "heartbeat": "OFFLINE" if self.offline else "ONLINE",
            "fps": 0 if self.offline else 30,
            "tamper": self.offline,
        }


if __name__ == "__main__":
    run_device(CctvCameraDevice)
