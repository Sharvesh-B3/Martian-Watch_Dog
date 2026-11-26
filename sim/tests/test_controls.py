import json

from sim.attacks.controller import AttackController
from sim.common.settings import SimSettings


class RecordingClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0):  # noqa: ANN201
        self.published.append((topic, json.loads(payload), qos))


def test_controller_dispatches_device_specific_commands() -> None:
    controller = AttackController(SimSettings(run_id="test-run"))
    client = RecordingClient()
    controller.client = client  # type: ignore[assignment]

    controller.activate("coordinated_intrusion", "scenario-1")

    assert {
        (topic, payload["action"])
        for topic, payload, _ in client.published
    } == {
        ("campus/lab1/sim/attack/cctv_01", "DROP_HEARTBEAT"),
        ("campus/lab1/sim/attack/rfid_01", "SUPPRESS_BADGE"),
        ("campus/lab1/sim/attack/door_lock_01", "FORCE_UNLOCK"),
        ("campus/lab1/sim/attack/meter_01", "PORT_SCAN"),
    }
    assert {item[1]["scenario_id"] for item in client.published} == {
        "scenario-1"
    }


def test_controller_emits_attacker_probe_for_active_intrusion() -> None:
    controller = AttackController(SimSettings(run_id="test-run"))
    client = RecordingClient()
    controller.client = client  # type: ignore[assignment]
    controller.activate("coordinated_intrusion", "scenario-1")
    client.published.clear()

    controller.publish_attacker_probes()

    assert len(client.published) == 1
    topic, payload, qos = client.published[0]
    assert topic == "campus/lab1/attacker/session/scenario-1"
    assert payload["scenario_id"] == "scenario-1"
    assert payload["source"] == "10.0.4.66"
    assert qos == 1


def test_new_scenario_supersedes_older_scenario_of_same_type() -> None:
    controller = AttackController(SimSettings(run_id="test-run"))
    client = RecordingClient()
    controller.client = client  # type: ignore[assignment]
    controller.activate("coordinated_intrusion", "scenario-1")
    controller.activate("coordinated_intrusion", "scenario-2")
    client.published.clear()

    controller.publish_attacker_probes()

    assert len(client.published) == 1
    assert client.published[0][1]["scenario_id"] == "scenario-2"
