"""Environment-backed settings for independent simulator processes."""

from dataclasses import dataclass
import os

from sim.common.protocol import TOPIC_PREFIX, new_run_id


@dataclass(frozen=True)
class SimSettings:
    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    topic_prefix: str = TOPIC_PREFIX
    interval_seconds: float = 2.0
    seed: int = 42
    noise: float = 0.0
    run_id: str = ""
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "SimSettings":
        return cls(
            broker_host=os.getenv("SIM_MQTT_HOST", "127.0.0.1"),
            broker_port=int(os.getenv("SIM_MQTT_PORT", "1883")),
            topic_prefix=os.getenv("SIM_TOPIC_PREFIX", TOPIC_PREFIX).rstrip("/"),
            interval_seconds=float(os.getenv("SIM_INTERVAL_SECONDS", "2")),
            seed=int(os.getenv("SIM_SEED", "42")),
            noise=max(0.0, float(os.getenv("SIM_NOISE", "0"))),
            run_id=os.getenv("SIM_RUN_ID") or new_run_id(),
            log_level=os.getenv("SIM_LOG_LEVEL", "INFO").upper(),
        )
