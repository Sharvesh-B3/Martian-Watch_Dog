from sim.common.settings import SimSettings
from sim.devices.air_quality import AirQualityDevice
from sim.devices.power_meter import PowerMeterDevice
from sim.devices.rfid_scanner import RfidScannerDevice
from sim.devices.smart_lock import SmartLockDevice


def settings(*, noise: float = 0.0) -> SimSettings:
    return SimSettings(seed=42, noise=noise, run_id="test-run")


def test_seeded_air_quality_is_repeatable() -> None:
    first = AirQualityDevice(settings(noise=0.5))
    second = AirQualityDevice(settings(noise=0.5))

    first_frames = [first.telemetry_frame() for _ in range(5)]
    second_frames = [second.telemetry_frame() for _ in range(5)]

    for left, right in zip(first_frames, second_frames, strict=True):
        left.pop("timestamp")
        right.pop("timestamp")
        assert left == right


def test_smart_lock_attack_holds_until_control() -> None:
    device = SmartLockDevice(settings())

    assert device.apply_attack(
        "FORCE_UNLOCK", {"scenario_id": "scenario-1"}
    )
    attacked = device.telemetry_frame()
    assert attacked["status"] == "UNLOCKED"
    assert attacked["state"] == "WARNING"
    assert attacked["scenario_id"] == "scenario-1"

    assert device.apply_control("QUARANTINE", {})
    quarantined = device.telemetry_frame()
    assert quarantined["status"] == "LOCKED"
    assert quarantined["state"] == "QUARANTINED"
    assert quarantined["failed_attempts"] == 3

    assert device.apply_control("RESET", {})
    restored = device.telemetry_frame()
    assert restored["state"] == "NORMAL"
    assert restored["scenario_id"] is None
    assert restored["failed_attempts"] == 0


def test_normal_power_metrics_never_cross_attack_threshold() -> None:
    device = PowerMeterDevice(settings(noise=1.0))

    frames = [device.telemetry_frame() for _ in range(120)]

    assert max(frame["network_conns"] for frame in frames) <= 3
    assert all(frame["anomaly_flag"] == "NONE" for frame in frames)


def test_authorized_unlock_relocks_after_three_frames() -> None:
    device = SmartLockDevice(settings())
    assert device.apply_attack(
        "AUTHORIZED_UNLOCK", {"badge_id": "FAC-2049"}
    )

    frames = [device.telemetry_frame() for _ in range(3)]

    assert frames[0]["status"] == "UNLOCKED"
    assert frames[-1]["status"] == "LOCKED"
    assert frames[-1]["last_rfid"] == "FAC-2049"


def test_rfid_scan_event_returns_to_idle() -> None:
    device = RfidScannerDevice(settings())
    assert device.apply_attack(
        "BADGE_ACCEPTED", {"badge_id": "FAC-2049"}
    )

    granted = device.telemetry_frame()
    idle = device.telemetry_frame()

    assert granted["event"] == "GRANTED"
    assert granted["badge_id"] == "FAC-2049"
    assert idle["event"] == "IDLE"
    assert "badge_id" not in idle
