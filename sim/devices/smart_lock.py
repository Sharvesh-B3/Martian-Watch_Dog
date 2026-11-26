"""Deterministic smart-lock simulator."""

from collections.abc import Mapping
from typing import Any

from sim.common.mqtt_device import BaseMqttDevice, run_device
from sim.common.settings import SimSettings


class SmartLockDevice(BaseMqttDevice):
    def __init__(self, settings: SimSettings) -> None:
        super().__init__("door_lock_01", settings)
        self.locked = True
        self.door_closed = True
        self.last_rfid = "NONE"
        self.failed_attempts = 0
        self._authorized_unlock = False
        self._relock_at_sequence: int | None = None

    def on_attack(self, action: str, payload: Mapping[str, Any]) -> bool:
        if action == "FORCE_UNLOCK":
            self.state = "WARNING"
            self.locked = False
            self.door_closed = False
            self.last_rfid = "UNAUTHORIZED_BYPASS"
            self.failed_attempts = 3
            self._authorized_unlock = False
            self._relock_at_sequence = None
            return True
        if action == "AUTHORIZED_UNLOCK":
            self.state = "NORMAL"
            self.locked = False
            self.door_closed = False
            self.last_rfid = str(payload.get("badge_id", "FAC-2049"))
            self.failed_attempts = 0
            self._authorized_unlock = True
            self._relock_at_sequence = self.sequence + 3
            return True
        if action == "REJECTED_BADGE":
            self.state = "WARNING"
            self.locked = True
            self.door_closed = True
            self.last_rfid = "DENIED"
            self.failed_attempts += 1
            return True
        return False

    def on_quarantine(self) -> None:
        self.locked = True
        self.door_closed = True
        self._authorized_unlock = False
        self._relock_at_sequence = None

    def on_reset(self) -> None:
        self.locked = True
        self.door_closed = True
        self.last_rfid = "NONE"
        self.failed_attempts = 0
        self._authorized_unlock = False
        self._relock_at_sequence = None

    def metrics(self) -> dict[str, str | int | float | bool]:
        if (
            self._authorized_unlock
            and self._relock_at_sequence is not None
            and self.sequence >= self._relock_at_sequence
        ):
            self.locked = True
            self.door_closed = True
            self._authorized_unlock = False
            self._relock_at_sequence = None
        return {
            "status": "LOCKED" if self.locked else "UNLOCKED",
            "door_closed": self.door_closed,
            "last_rfid": self.last_rfid,
            "failed_attempts": self.failed_attempts,
        }


if __name__ == "__main__":
    run_device(SmartLockDevice)
