from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sim.common.config import ConfigurationError, DeviceSettings
from sim.common.healthcheck import check_health
from sim.common.mqtt import DeviceRunner, JsonLogFormatter
from sim.devices.air_quality import AirQualityModel, IDENTITY as AIR_IDENTITY
from sim.devices.decoy_twin import DecoyTwinModel, IDENTITY as DECOY_IDENTITY
from sim.devices.power_meter import PowerMeterModel, IDENTITY as POWER_IDENTITY
from sim.devices.rfid_scanner import IDENTITY as RFID_IDENTITY, RfidScannerModel
from sim.devices.smart_lock import IDENTITY as LOCK_IDENTITY, SmartLockModel
from sim.setup_credentials import (
    ACCOUNTS,
    ENV_SAFE_TOKEN,
    generate_credentials,
    hash_password_file_with_docker,
    install_pair_atomically,
    render_env,
    verify_hashed_password_file,
)
from sim.verify_lab import VerificationError, load_env_file, verify_normal_profile


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPOSITORY_ROOT / "sim" / "contracts"


class ConfigurationTests(unittest.TestCase):
    def test_valid_environment_is_strict_and_hides_password_from_repr(self) -> None:
        environment = {
            "MQTT_HOST": "mosquitto",
            "MQTT_PORT": "1883",
            "MQTT_USERNAME": LOCK_IDENTITY.mqtt_username,
            "MQTT_PASSWORD": "top-secret-test-value",
            "MQTT_CLIENT_ID": LOCK_IDENTITY.client_id,
            "SIM_SEED": "101",
            "SCHEMA_DIR": str(SCHEMA_DIR),
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = DeviceSettings.from_env(LOCK_IDENTITY)

        self.assertEqual(settings.mqtt_host, "mosquitto")
        self.assertEqual(settings.mqtt_port, 1883)
        self.assertEqual(settings.seed, 101)
        self.assertEqual(settings.telemetry_interval_seconds, 2.0)
        self.assertNotIn("top-secret-test-value", repr(settings))

    def test_wrong_identity_is_rejected(self) -> None:
        environment = {
            "MQTT_HOST": "mosquitto",
            "MQTT_USERNAME": "device_air_quality_01",
            "MQTT_PASSWORD": "test-only",
            "MQTT_CLIENT_ID": LOCK_IDENTITY.client_id,
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError):
                DeviceSettings.from_env(LOCK_IDENTITY)

    def test_random_seed_mode_is_explicit(self) -> None:
        environment = {
            "MQTT_HOST": "mosquitto",
            "MQTT_USERNAME": LOCK_IDENTITY.mqtt_username,
            "MQTT_PASSWORD": "test-only",
            "MQTT_CLIENT_ID": LOCK_IDENTITY.client_id,
            "SIM_SEED": "random",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = DeviceSettings.from_env(LOCK_IDENTITY)
        self.assertIsNone(settings.seed)


class DeviceModelTests(unittest.TestCase):
    def test_every_device_emits_contract_valid_normal_telemetry(self) -> None:
        models = (
            SmartLockModel(LOCK_IDENTITY, 101, SCHEMA_DIR),
            RfidScannerModel(RFID_IDENTITY, 102, SCHEMA_DIR),
            AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR),
            PowerMeterModel(POWER_IDENTITY, 104, SCHEMA_DIR),
            DecoyTwinModel(DECOY_IDENTITY, 105, SCHEMA_DIR),
        )
        observed_ids = set()
        for model in models:
            payload = model.telemetry()
            observed_ids.add(payload["device_id"])
            self.assertEqual(payload["correlation_id"], None)
            self.assertEqual(payload["metadata"], {"note": None})

        self.assertEqual(
            observed_ids,
            {
                "smart_lock_01",
                "rfid_scanner_01",
                "air_quality_01",
                "power_meter_01",
                "decoy_twin_01",
            },
        )

    def test_air_quality_is_deterministic_and_in_normal_bounds(self) -> None:
        first = AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR)
        second = AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR)
        first_samples = [first.telemetry()["metrics"] for _ in range(10)]
        second_samples = [second.telemetry()["metrics"] for _ in range(10)]
        self.assertEqual(first_samples, second_samples)
        for metrics in first_samples:
            self.assertGreaterEqual(metrics["pm25"], 5)
            self.assertLessEqual(metrics["pm25"], 20)
            self.assertGreaterEqual(metrics["co2_ppm"], 410)
            self.assertLessEqual(metrics["co2_ppm"], 480)
            self.assertGreaterEqual(metrics["temp_c"], 20.0)
            self.assertLessEqual(metrics["temp_c"], 24.0)

    def test_power_meter_is_deterministic_and_in_normal_bounds(self) -> None:
        model = PowerMeterModel(POWER_IDENTITY, 104, SCHEMA_DIR)
        for _ in range(10):
            metrics = model.telemetry()["metrics"]
            self.assertGreaterEqual(metrics["load_kw"], 2.8)
            self.assertLessEqual(metrics["load_kw"], 3.8)
            self.assertGreaterEqual(metrics["voltage"], 228.0)
            self.assertLessEqual(metrics["voltage"], 232.0)
            self.assertIn(metrics["outbound_conns"], (1, 2, 3))

    def test_rfid_baseline_is_idle_only(self) -> None:
        model = RfidScannerModel(RFID_IDENTITY, 102, SCHEMA_DIR)
        for _ in range(5):
            self.assertEqual(
                model.telemetry()["metrics"],
                {"event": "idle", "badge_id": None, "authorized": False},
            )

    def test_decoy_baseline_is_standby(self) -> None:
        payload = DecoyTwinModel(DECOY_IDENTITY, 105, SCHEMA_DIR).telemetry()
        self.assertEqual(payload["status"], "decoy")
        self.assertEqual(
            payload["metrics"],
            {"mode": "standby", "active_traps": 0, "captured_payloads": 0},
        )

    def test_runner_uses_mqtt311_qos1_nonretained_presence_will(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = DeviceSettings(
                identity=LOCK_IDENTITY,
                mqtt_host="mosquitto",
                mqtt_port=1883,
                mqtt_password="test-only",
                seed=101,
                health_file=Path(directory) / "health.json",
                schema_dir=SCHEMA_DIR,
            )
            model = SmartLockModel(LOCK_IDENTITY, 101, SCHEMA_DIR)
            runner = DeviceRunner(settings, model)

        self.assertEqual(runner.client._protocol, 4)  # MQTTv311
        self.assertEqual(runner.client._will_topic, b"campus/lab1/presence/smart_lock_01")
        self.assertEqual(runner.client._will_qos, 1)
        self.assertIs(runner.client._will_retain, False)

    def test_rotating_last_will_uses_a_fresh_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = DeviceSettings(
                identity=LOCK_IDENTITY,
                mqtt_host="mosquitto",
                mqtt_port=1883,
                mqtt_password="test-only",
                seed=101,
                health_file=Path(directory) / "health.json",
                schema_dir=SCHEMA_DIR,
            )
            model = SmartLockModel(LOCK_IDENTITY, 101, SCHEMA_DIR)
            runner = DeviceRunner(settings, model)
            first = json.loads(runner.client._will_payload.decode("utf-8"))
            runner._configure_last_will()
            second = json.loads(runner.client._will_payload.decode("utf-8"))

        self.assertNotEqual(first["event_id"], second["event_id"])

    def test_smart_lock_attack_quarantine_and_reset(self) -> None:
        model = SmartLockModel(LOCK_IDENTITY, 101, SCHEMA_DIR)
        model.apply_injection("unauthorized_unlock", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
        self.assertFalse(model.telemetry()["metrics"]["locked"])
        model.apply_action("QUARANTINE", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
        self.assertEqual(model.telemetry()["status"], "quarantined")
        self.assertTrue(model.telemetry()["metrics"]["locked"])
        model.reset()
        self.assertEqual(model.telemetry()["status"], "normal")

    def test_prompt_injection_is_untrusted_metadata_with_normal_metrics(self) -> None:
        model = AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR)
        model.apply_injection("prompt_note", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
        payload = model.telemetry()
        self.assertEqual(payload["metrics"], {"pm25": 12, "co2_ppm": 430, "temp_c": 21.5})
        self.assertIn("IGNORE PREVIOUS", payload["metadata"]["note"])

    def test_power_scan_persists_until_reset(self) -> None:
        model = PowerMeterModel(POWER_IDENTITY, 104, SCHEMA_DIR)
        model.apply_injection("port_scan", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
        self.assertEqual(model.telemetry()["metrics"]["outbound_conns"], 148)
        model.reset()
        self.assertLessEqual(model.telemetry()["metrics"]["outbound_conns"], 3)

    def test_decoy_activation_capture_and_reset(self) -> None:
        model = DecoyTwinModel(DECOY_IDENTITY, 105, SCHEMA_DIR)
        model.apply_action("ACTIVATE_DECOY", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
        self.assertEqual(model.capture("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3"), (1, 1))
        self.assertEqual(model.telemetry()["metrics"]["captured_payloads"], 1)
        model.reset()
        self.assertEqual(model.telemetry()["metrics"]["mode"], "standby")


class HealthCheckTests(unittest.TestCase):
    def test_recent_connected_publish_is_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            path.write_text(
                json.dumps(
                    {
                        "connected": True,
                        "last_publish_epoch": 100.0,
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(check_health(path, max_age_seconds=15.0, now=110.0))
            self.assertFalse(check_health(path, max_age_seconds=5.0, now=110.0))

    def test_missing_or_disconnected_health_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            self.assertFalse(check_health(path, 15.0, now=100.0))
            path.write_text(
                json.dumps(
                    {
                        "connected": False,
                        "last_publish_epoch": None,
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(check_health(path, 15.0, now=100.0))


class LoggingTests(unittest.TestCase):
    def test_json_formatter_emits_machine_readable_bounded_fields(self) -> None:
        record = logging.LogRecord(
            name="watchdog.device",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Published %s",
            args=("smart_lock_01",),
            exc_info=None,
        )
        payload = json.loads(JsonLogFormatter().format(record))
        self.assertEqual(
            set(payload),
            {"timestamp", "level", "logger", "message"},
        )
        self.assertEqual(payload["message"], "Published smart_lock_01")


class CredentialTests(unittest.TestCase):
    def test_all_eight_credentials_are_unique_and_environment_safe(self) -> None:
        credentials = generate_credentials()
        self.assertEqual(len(credentials), 8)
        self.assertEqual(len(set(credentials.values())), 8)
        for value in credentials.values():
            self.assertIsNotNone(ENV_SAFE_TOKEN.fullmatch(value))
            self.assertGreaterEqual(len(value), 43)

    def test_rendered_env_has_fixed_usernames_without_missing_accounts(self) -> None:
        credentials = generate_credentials()
        rendered = render_env(credentials)
        for username_key, password_key, username in ACCOUNTS:
            self.assertIn(f"{username_key}={username}", rendered)
            self.assertIn(f"{password_key}={credentials[username]}", rendered)
        self.assertIn("MQTT_HOST_PORT=1884", rendered)

    def test_pair_install_replaces_password_db_and_env_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged_password = root / "staged-passwd"
            staged_env = root / "staged-env"
            target_password = root / "broker" / "generated" / "passwd"
            target_env = root / "sim" / ".env"
            staged_password.write_text("hashed", encoding="utf-8")
            staged_env.write_text("variables", encoding="utf-8")

            install_pair_atomically(
                staged_password,
                staged_env,
                target_password,
                target_env,
            )

            self.assertEqual(target_password.read_text(encoding="utf-8"), "hashed")
            self.assertEqual(target_env.read_text(encoding="utf-8"), "variables")

    @patch("sim.setup_credentials.subprocess.run")
    def test_hash_command_uses_file_upgrade_not_command_line_passwords(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stderr = ""
        run.return_value.stdout = ""
        with tempfile.TemporaryDirectory() as directory:
            password_file = Path(directory) / "passwd"
            password_file.write_text("observer:secret-value", encoding="utf-8")
            hash_password_file_with_docker(
                docker_executable="docker",
                image="eclipse-mosquitto:2",
                password_file=password_file,
            )

        command = run.call_args.args[0]
        self.assertIn("-U", command)
        self.assertNotIn("-b", command)
        self.assertNotIn("secret-value", " ".join(command))

    def test_hashed_password_database_verification_accepts_hash_records(self) -> None:
        credentials = generate_credentials()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "passwd"
            path.write_text(
                "".join(f"{username}:$7$test-hash-{index}\n" for index, (_, _, username) in enumerate(ACCOUNTS)),
                encoding="utf-8",
            )
            verify_hashed_password_file(path, credentials)

    def test_hashed_password_database_verification_rejects_plaintext(self) -> None:
        credentials = generate_credentials()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "passwd"
            path.write_text(
                "".join(f"{username}:{credentials[username]}\n" for _, _, username in ACCOUNTS),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                verify_hashed_password_file(path, credentials)


class BrokerPolicyTests(unittest.TestCase):
    def test_broker_requires_authentication_and_contract_files(self) -> None:
        config = (REPOSITORY_ROOT / "sim" / "broker" / "mosquitto.conf").read_text(
            encoding="utf-8"
        )
        self.assertIn("allow_anonymous false", config)
        self.assertIn("password_file /tmp/watchdog-mosquitto/passwd", config)
        self.assertIn("acl_file /tmp/watchdog-mosquitto/acl", config)

    def test_acl_declares_exactly_the_eight_fixed_principals(self) -> None:
        acl = (REPOSITORY_ROOT / "sim" / "broker" / "acl").read_text(
            encoding="utf-8"
        )
        users = {
            line.split(maxsplit=1)[1]
            for line in acl.splitlines()
            if line.startswith("user ")
        }
        self.assertEqual(users, {username for _, _, username in ACCOUNTS})

    def test_backend_has_no_private_topic_subscription(self) -> None:
        acl = (REPOSITORY_ROOT / "sim" / "broker" / "acl").read_text(
            encoding="utf-8"
        )
        backend_section = acl.split("user backend", maxsplit=1)[1].split(
            "user observer", maxsplit=1
        )[0]
        self.assertNotIn("sim/inject", backend_section)
        self.assertNotIn("decoy/input", backend_section)
        self.assertNotIn("test/ground_truth", backend_section)
        self.assertIn("topic write campus/lab1/control/+", backend_section)

    def test_observer_is_read_only(self) -> None:
        acl = (REPOSITORY_ROOT / "sim" / "broker" / "acl").read_text(
            encoding="utf-8"
        )
        observer_section = acl.split("user observer", maxsplit=1)[1]
        self.assertIn("topic read campus/lab1/#", observer_section)
        self.assertNotIn("topic write", observer_section)


class LiveVerifierUnitTests(unittest.TestCase):
    def test_generated_env_is_accepted_by_live_verifier_parser(self) -> None:
        credentials = generate_credentials()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(render_env(credentials), encoding="utf-8")
            parsed = load_env_file(path)
        self.assertEqual(parsed["MQTT_BACKEND_USERNAME"], "backend")
        self.assertEqual(parsed["MQTT_OBSERVER_PASSWORD"], credentials["observer"])

    def test_all_normal_models_pass_live_profile_checks(self) -> None:
        models = (
            SmartLockModel(LOCK_IDENTITY, 101, SCHEMA_DIR),
            RfidScannerModel(RFID_IDENTITY, 102, SCHEMA_DIR),
            AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR),
            PowerMeterModel(POWER_IDENTITY, 104, SCHEMA_DIR),
            DecoyTwinModel(DECOY_IDENTITY, 105, SCHEMA_DIR),
        )
        for model in models:
            verify_normal_profile(model.telemetry())

    def test_live_profile_rejects_attack_like_air_value(self) -> None:
        payload = AirQualityModel(AIR_IDENTITY, 103, SCHEMA_DIR).telemetry()
        payload["metrics"]["pm25"] = 490
        with self.assertRaises(VerificationError):
            verify_normal_profile(payload)


if __name__ == "__main__":
    unittest.main()
