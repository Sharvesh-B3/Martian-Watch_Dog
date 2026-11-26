from sim.attacks.scenarios import (
    SCENARIO_COMMANDS,
    build_direct_frames,
    build_trigger,
)


def test_attack_scenarios_are_separate() -> None:
    spoof = SCENARIO_COMMANDS["spoof_sensor"]
    injection = SCENARIO_COMMANDS["prompt_injection"]

    assert [(item.device_id, item.action) for item in spoof] == [
        ("aq_sensor_01", "SPOOF")
    ]
    assert [(item.device_id, item.action) for item in injection] == [
        ("aq_sensor_01", "PROMPT_INJECTION")
    ]


def test_coordinated_scenario_contains_all_evidence_sources() -> None:
    commands = {
        (item.device_id, item.action)
        for item in SCENARIO_COMMANDS["coordinated_intrusion"]
    }

    assert commands == {
        ("cctv_01", "DROP_HEARTBEAT"),
        ("rfid_01", "SUPPRESS_BADGE"),
        ("door_lock_01", "FORCE_UNLOCK"),
        ("meter_01", "PORT_SCAN"),
    }


def test_direct_frames_share_trigger_scenario_id() -> None:
    trigger = build_trigger(
        "coordinated_intrusion",
        scenario_id="scenario-42",
        timestamp="2026-11-26T00:00:00Z",
    )
    frames = build_direct_frames(
        "coordinated_intrusion",
        scenario_id=str(trigger["scenario_id"]),
        timestamp=str(trigger["timestamp"]),
    )

    assert {payload["scenario_id"] for _, payload in frames} == {"scenario-42"}
    assert {suffix for suffix, _ in frames} == {
        "cctv_cam",
        "door_lock",
        "smart_meter",
    }


def test_prompt_injection_keeps_readings_realistic() -> None:
    frames = build_direct_frames(
        "prompt_injection", scenario_id="injection-1"
    )
    payload = frames[0][1]

    assert payload["co2_ppm"] < 1000
    assert 10 <= payload["temp_c"] <= 35
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in payload["status"]
