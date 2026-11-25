import json

from sim.common.settings import SimSettings
from sim.devices.decoy_twin import DecoyTwinDevice


class RecordingClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0):  # noqa: ANN201
        self.published.append((topic, json.loads(payload), qos))


def test_decoy_ignores_probes_until_activated() -> None:
    decoy = DecoyTwinDevice(SimSettings(run_id="test-run"))
    client = RecordingClient()
    decoy.client = client  # type: ignore[assignment]

    decoy.handle_extra_message(
        "campus/lab1/attacker/session/scenario-1",
        {"scenario_id": "scenario-1", "source": "10.0.4.66", "command": "SCAN"},
    )

    assert decoy.captured_payloads == 0
    assert client.published == []


def test_active_decoy_captures_and_publishes_safe_hash() -> None:
    decoy = DecoyTwinDevice(SimSettings(run_id="test-run"))
    client = RecordingClient()
    decoy.client = client  # type: ignore[assignment]
    assert decoy.apply_control("DECOY", {})

    for sequence in range(3):
        decoy.handle_extra_message(
            "campus/lab1/attacker/session/scenario-1",
            {
                "scenario_id": "scenario-1",
                "source": "10.0.4.66",
                "command": f"SCAN_{sequence}",
            },
        )

    assert decoy.captured_payloads == 3
    captures = [
        payload
        for topic, payload, _ in client.published
        if topic == "campus/lab1/decoy/capture"
    ]
    assert len(captures) == 3
    assert len(captures[-1]["payload_hash"]) == 16
    assert "SCAN_2" == captures[-1]["command"]
    assert decoy.metrics()["active_traps"] == 1
