from __future__ import annotations

import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = yaml.safe_load(
    (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
)

DEVICE_SERVICES = {
    "smart_lock_01": ("watchdog-smart-lock-01", "MQTT_SMART_LOCK_PASSWORD"),
    "rfid_scanner_01": (
        "watchdog-rfid-scanner-01",
        "MQTT_RFID_SCANNER_PASSWORD",
    ),
    "air_quality_01": ("watchdog-air-quality-01", "MQTT_AIR_QUALITY_PASSWORD"),
    "power_meter_01": ("watchdog-power-meter-01", "MQTT_POWER_METER_PASSWORD"),
    "decoy_twin_01": ("watchdog-decoy-twin-01", "MQTT_DECOY_TWIN_PASSWORD"),
}


class ComposeStructureTests(unittest.TestCase):
    def test_exact_phase2_services_are_declared(self) -> None:
        self.assertEqual(
            set(COMPOSE["services"]),
            {"mosquitto", "attack_controller", "backend", *DEVICE_SERVICES},
        )

    def test_shared_simulator_image_has_one_build_owner(self) -> None:
        build_services = [
            name
            for name, service in COMPOSE["services"].items()
            if "build" in service
        ]
        self.assertEqual(set(build_services), {"smart_lock_01", "backend"})
        for service_name in DEVICE_SERVICES:
            self.assertEqual(
                COMPOSE["services"][service_name]["image"],
                "aegis-watchdog-sim:local",
            )

    def test_lab_network_is_internal_and_host_port_is_loopback_only(self) -> None:
        self.assertIs(COMPOSE["networks"]["watchdog-lab"]["internal"], True)
        self.assertIs(COMPOSE["networks"]["watchdog-host-access"]["internal"], False)
        self.assertEqual(
            COMPOSE["services"]["mosquitto"]["ports"],
            ["127.0.0.1:${MQTT_HOST_PORT:-1884}:1883"],
        )
        self.assertEqual(
            set(COMPOSE["services"]["mosquitto"]["networks"]),
            {"watchdog-lab", "watchdog-host-access"},
        )
        for service_name in DEVICE_SERVICES:
            self.assertEqual(
                COMPOSE["services"][service_name]["networks"],
                ["watchdog-lab"],
            )

    def test_broker_security_files_use_hardened_runtime_entrypoint(self) -> None:
        broker = COMPOSE["services"]["mosquitto"]
        self.assertEqual(
            broker["entrypoint"],
            ["/bin/ash", "/run/watchdog/entrypoint.sh"],
        )
        self.assertIn(
            "./sim/broker/generated/passwd:/run/watchdog/passwd:ro",
            broker["volumes"],
        )

    def test_each_device_receives_only_its_selected_password_reference(self) -> None:
        all_password_keys = {password_key for _, password_key in DEVICE_SERVICES.values()}
        for service_name, (client_id, own_password_key) in DEVICE_SERVICES.items():
            environment = COMPOSE["services"][service_name]["environment"]
            self.assertEqual(environment["MQTT_CLIENT_ID"], client_id)
            self.assertIn(own_password_key, environment["MQTT_PASSWORD"])
            for other_password_key in all_password_keys - {own_password_key}:
                self.assertNotIn(other_password_key, str(environment))

    def test_health_and_dependency_gates_are_present(self) -> None:
        broker = COMPOSE["services"]["mosquitto"]
        self.assertIn("healthcheck", broker)
        self.assertIn("MQTT_OBSERVER_PASSWORD", str(broker["healthcheck"]))
        for service_name in DEVICE_SERVICES:
            service = COMPOSE["services"][service_name]
            self.assertEqual(
                service["depends_on"]["mosquitto"]["condition"],
                "service_healthy",
            )
            self.assertEqual(
                service["healthcheck"]["test"],
                ["CMD", "python", "-m", "sim.common.healthcheck"],
            )


if __name__ == "__main__":
    unittest.main()
