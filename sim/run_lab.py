"""One-command launcher for the isolated multi-process IoT lab."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import signal

from sim.common.protocol import new_run_id

REPO_ROOT = Path(__file__).resolve().parents[1]

COMPONENT_MODULES = (
    "sim.devices.smart_lock",
    "sim.devices.rfid_scanner",
    "sim.devices.air_quality",
    "sim.devices.power_meter",
    "sim.devices.cctv_camera",
    "sim.devices.decoy_twin",
    "sim.attacks.controller",
    "sim.attacks.network_attacker",
)

BROKER_SERVICES = ("mosquitto", "mosquitto-decoy")


def broker_is_running() -> bool:
    result = subprocess.run(
        ["docker", "compose", "ps", "--status", "running", "--services"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(result.stdout.split())
    return all(service in running for service in BROKER_SERVICES)


def start_broker() -> bool:
    already_running = broker_is_running()
    if not already_running:
        subprocess.run(
            ["docker", "compose", "up", "-d", *BROKER_SERVICES],
            cwd=REPO_ROOT,
            check=True,
        )
    return not already_running


def wait_for_broker(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Mosquitto did not become ready at {host}:{port}")


def stop_children(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 5
    for child in children:
        if child.poll() is not None:
            continue
        remaining = max(0.0, deadline - time.monotonic())
        try:
            child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            child.kill()
    for child in children:
        if child.poll() is None:
            child.wait(timeout=2)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Aegis isolated IoT lab")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--no-noise", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--broker-host", default="127.0.0.1")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--keep-broker", action="store_true")
    parser.add_argument("--no-broker", action="store_true")
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    noise = 0.0 if args.no_noise else max(0.0, args.noise)
    run_id = new_run_id()
    started_broker = False
    children: list[subprocess.Popen[bytes]] = []

    def request_shutdown(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, request_shutdown)

    try:
        if not args.no_broker:
            started_broker = start_broker()
        wait_for_broker(args.broker_host, args.broker_port)
        wait_for_broker(args.broker_host, 1885)

        env = os.environ.copy()
        env.update(
            {
                "SIM_MQTT_HOST": args.broker_host,
                "SIM_MQTT_PORT": str(args.broker_port),
                "SIM_DECOY_MQTT_HOST": args.broker_host,
                "SIM_DECOY_MQTT_PORT": "1885",
                "SIM_GATEWAY_HOST": "127.0.0.1",
                "SIM_GATEWAY_PORT": "1884",
                "SIM_GATEWAY_CONTROL_URL": "http://127.0.0.1:9000",
                "SIM_SEED": str(args.seed),
                "SIM_NOISE": str(noise),
                "SIM_INTERVAL_SECONDS": str(args.interval),
                "SIM_RUN_ID": run_id,
                "SIM_LOG_LEVEL": args.log_level.upper(),
            }
        )
        modules = ["sim.containment_gateway"]
        children.append(
            subprocess.Popen(
                [sys.executable, "-m", "sim.containment_gateway"],
                cwd=REPO_ROOT,
                env=env,
            )
        )
        wait_for_broker("127.0.0.1", 9000)
        modules.extend(COMPONENT_MODULES)
        if args.monitor:
            modules.append("sim.monitor")

        print(
            f"[lab] launching {len(modules)} processes "
            f"(run_id={run_id}, seed={args.seed}, noise={noise})",
            flush=True,
        )
        for module in modules[1:]:
            children.append(
                subprocess.Popen(
                    [sys.executable, "-m", module],
                    cwd=REPO_ROOT,
                    env=env,
                )
            )

        while True:
            for module, child in zip(modules, children, strict=True):
                exit_code = child.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"Simulator component {module} exited with {exit_code}"
                    )
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[lab] shutdown requested", flush=True)
    finally:
        stop_children(children)
        if started_broker and not args.keep_broker:
            subprocess.run(
                ["docker", "compose", "stop", *BROKER_SERVICES],
                # Stop only brokers started by this launcher.
                cwd=REPO_ROOT,
                check=False,
            )
        print("[lab] all simulator processes stopped", flush=True)


if __name__ == "__main__":
    main()
