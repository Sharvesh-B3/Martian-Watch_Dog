from datetime import datetime, timedelta, timezone

from backend.app.correlation_window import CorrelationWindow
from backend.app.schemas import AttackCategory

BASE = datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def add_breach(window: CorrelationWindow, moment: datetime) -> None:
    window.add(
        "smart_lock_01",
        {
            "status": "UNLOCKED",
            "last_rfid": "UNAUTHORIZED_BYPASS",
            "timestamp": iso(moment),
        },
        timestamp=moment,
    )
    window.add(
        "power_meter_01",
        {
            "network_conns": 148,
            "anomaly_flag": "PORT_SCAN_SUBNET_10.0.4.0/24",
            "timestamp": iso(moment),
        },
        timestamp=moment,
    )


def test_coordinated_intrusion_is_high_risk_and_requires_approval() -> None:
    window = CorrelationWindow(60)
    add_breach(window, BASE)

    signals = window.evaluate(BASE)

    coordinated = [
        signal
        for signal in signals
        if signal.category == AttackCategory.COORDINATED_INTRUSION
    ]
    assert len(coordinated) == 1
    assert coordinated[0].severity == "critical"
    assert coordinated[0].risk_level == "high"
    assert coordinated[0].auto_execute is False
    assert coordinated[0].device_ids == (
        "smart_lock_01",
        "rfid_scanner_01",
        "power_meter_01",
    )


def test_badge_scan_in_window_clears_coordinated_rule() -> None:
    window = CorrelationWindow(60)
    add_breach(window, BASE)
    window.add(
        "rfid_scanner_01",
        {"event": "SCAN", "badge_id": "FAC-2049", "timestamp": iso(BASE)},
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)

    assert not any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in signals
    )


def test_evidence_outside_window_does_not_correlate() -> None:
    window = CorrelationWindow(60)
    later = BASE + timedelta(seconds=61)
    add_breach(window, BASE)
    window.add(
        "power_meter_01",
        {"network_conns": 148, "timestamp": iso(later)},
        timestamp=later,
    )

    signals = window.evaluate(later)

    assert not any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in signals
    )


def test_spoof_thresholds_and_normal_readings() -> None:
    window = CorrelationWindow(60)
    window.add(
        "air_quality_01",
        {"co2_ppm": 4500, "temp_c": 68.5, "timestamp": iso(BASE)},
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)
    spoof = [
        signal
        for signal in signals
        if signal.category == AttackCategory.SENSOR_SPOOFING
    ]
    assert len(spoof) == 1
    assert spoof[0].auto_execute is True

    normal = CorrelationWindow(60)
    normal.add(
        "air_quality_01",
        {"co2_ppm": 430, "temp_c": 22.5, "timestamp": iso(BASE)},
        timestamp=BASE,
    )
    assert not any(
        signal.category == AttackCategory.SENSOR_SPOOFING
        for signal in normal.evaluate(BASE)
    )


def test_isolated_port_scan_produces_anomalous_traffic() -> None:
    window = CorrelationWindow(60)
    window.add(
        "power_meter_01",
        {"network_conns": 148, "timestamp": iso(BASE)},
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)

    assert any(
        signal.category == AttackCategory.ANOMALOUS_TRAFFIC
        and signal.auto_execute
        for signal in signals
    )


def test_injection_signal_carries_excerpt() -> None:
    window = CorrelationWindow(60)
    window.add(
        "air_quality_01",
        {"timestamp": iso(BASE)},
        injection_detected=True,
        sanitized_excerpt="IGNORE ALL PREVIOUS INSTRUCTIONS",
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)
    injection = [
        signal
        for signal in signals
        if signal.category == AttackCategory.PROMPT_INJECTION
    ]

    assert len(injection) == 1
    assert injection[0].prompt_injection_detected
    assert injection[0].sanitized_excerpt == "IGNORE ALL PREVIOUS INSTRUCTIONS"
    assert injection[0].auto_execute is True


def test_same_signal_is_not_emitted_twice_within_window() -> None:
    window = CorrelationWindow(60)
    add_breach(window, BASE)

    first = window.evaluate(BASE)
    second = window.evaluate(BASE)

    assert sum(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in first + second
    ) == 1


def test_distinct_attack_inside_window_is_emitted_again() -> None:
    window = CorrelationWindow(60)
    add_breach(window, BASE)
    first = window.evaluate(BASE)

    second_attack = BASE + timedelta(seconds=10)
    add_breach(window, second_attack)
    second = window.evaluate(second_attack)

    assert sum(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in first
    ) == 1
    assert sum(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in second
    ) == 1


def test_mqtt_echo_with_same_evidence_is_deduplicated() -> None:
    window = CorrelationWindow(60)
    add_breach(window, BASE)
    first = window.evaluate(BASE)

    add_breach(window, BASE)
    echoed = window.evaluate(BASE)

    assert any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in first
    )
    assert not any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in echoed
    )


def test_held_scenario_does_not_reemit_after_window_rolls() -> None:
    window = CorrelationWindow(60)
    for moment in (BASE, BASE + timedelta(seconds=70)):
        window.add(
            "smart_lock_01",
            {
                "status": "UNLOCKED",
                "scenario_id": "held-scenario",
                "timestamp": iso(moment),
            },
            timestamp=moment,
        )
        window.add(
            "power_meter_01",
            {
                "network_conns": 148,
                "scenario_id": "held-scenario",
                "timestamp": iso(moment),
            },
            timestamp=moment,
        )
        signals = window.evaluate(moment)
        if moment == BASE:
            assert any(
                signal.category == AttackCategory.COORDINATED_INTRUSION
                for signal in signals
            )
        else:
            assert not any(
                signal.category == AttackCategory.COORDINATED_INTRUSION
                for signal in signals
            )


def test_different_scenario_ids_do_not_cross_correlate() -> None:
    window = CorrelationWindow(60)
    window.add(
        "smart_lock_01",
        {
            "status": "UNLOCKED",
            "scenario_id": "door-scenario",
            "timestamp": iso(BASE),
        },
        timestamp=BASE,
    )
    window.add(
        "power_meter_01",
        {
            "network_conns": 148,
            "scenario_id": "meter-scenario",
            "timestamp": iso(BASE),
        },
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)

    assert not any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in signals
    )


def test_tagged_and_legacy_evidence_do_not_cross_correlate() -> None:
    window = CorrelationWindow(60)
    window.add(
        "smart_lock_01",
        {
            "status": "UNLOCKED",
            "scenario_id": "tagged-scenario",
            "timestamp": iso(BASE),
        },
        timestamp=BASE,
    )
    window.add(
        "power_meter_01",
        {"network_conns": 148, "timestamp": iso(BASE)},
        timestamp=BASE,
    )

    signals = window.evaluate(BASE)

    assert not any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in signals
    )


def test_new_legacy_burst_is_not_hidden_by_newer_held_scenario() -> None:
    window = CorrelationWindow(60)
    tagged = BASE
    for canonical_id, payload in (
        (
            "smart_lock_01",
            {"status": "UNLOCKED", "scenario_id": "held"},
        ),
        (
            "power_meter_01",
            {"network_conns": 148, "scenario_id": "held"},
        ),
    ):
        window.add(canonical_id, payload, timestamp=tagged)
    assert any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in window.evaluate(tagged)
    )

    legacy = BASE + timedelta(seconds=1)
    window.add(
        "smart_lock_01", {"status": "UNLOCKED"}, timestamp=legacy
    )
    window.add(
        "power_meter_01", {"network_conns": 148}, timestamp=legacy
    )

    # A held scenario publishes again after the legacy burst and is therefore
    # newer, but its fingerprint has already been emitted.
    held_again = BASE + timedelta(seconds=2)
    window.add(
        "smart_lock_01",
        {"status": "UNLOCKED", "scenario_id": "held"},
        timestamp=held_again,
    )
    window.add(
        "power_meter_01",
        {"network_conns": 148, "scenario_id": "held"},
        timestamp=held_again,
    )

    signals = window.evaluate(held_again)

    assert any(
        signal.category == AttackCategory.COORDINATED_INTRUSION
        for signal in signals
    )
