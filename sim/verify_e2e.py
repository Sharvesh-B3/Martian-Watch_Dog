"""Focused end-to-end MVP verification through the public FastAPI boundary."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable


def request(base: str, path: str, data: dict[str, Any] | None = None) -> Any:
    body = None if data is None else json.dumps(data).encode()
    method = "GET" if data is None else "POST"
    req = urllib.request.Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def wait_for(check: Callable[[], Any], timeout: float = 30) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for end-to-end condition")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    health = request(base, "/health")
    if not health.get("mqtt_connected"):
        raise RuntimeError("Backend health is not MQTT-connected")

    request(base, "/api/sim/reset", {})
    existing_incidents = {item["id"] for item in request(base, "/api/incidents")}

    for attack_type, category in (
        ("spoof_sensor", "sensor_spoofing"),
        ("prompt_injection", "prompt_injection"),
        ("coordinated_intrusion", "coordinated_intrusion"),
    ):
        triggered = request(base, "/api/sim/trigger", {"attack_type": attack_type})
        request_id = triggered["request_id"]
        wait_for(
            lambda: (
                status
                if (status := request(base, f"/api/sim/status/{request_id}"))["status"]
                in {"completed", "failed", "rejected", "busy"}
                else None
            )
        )
        status = request(base, f"/api/sim/status/{request_id}")
        if status["status"] != "completed":
            raise RuntimeError(f"{attack_type} ended as {status['status']}")
        incident = wait_for(
            lambda: next(
                (
                    item
                    for item in request(base, "/api/incidents")
                    if item["id"] not in existing_incidents and item["category"] == category
                ),
                None,
            )
        )
        existing_incidents.add(incident["id"])

    approval = wait_for(
        lambda: next(
            (item for item in request(base, "/api/approvals") if item["status"] == "pending"),
            None,
        )
    )
    existing_audit = {item["id"] for item in request(base, "/api/audit-log")}
    decision = request(
        base,
        f"/api/approvals/{approval['id']}/decide",
        {"decision": "approved"},
    )
    if decision["status"] != "approved":
        raise RuntimeError("Approval was not applied")
    wait_for(
        lambda: next(
            (
                item
                for item in request(base, "/api/audit-log")
                if item["id"] not in existing_audit and item["action"] == "DECOY_CAPTURE"
            ),
            None,
        )
    )
    request(base, "/api/sim/reset", {})
    print("E2E PASS: 3 attacks, 3 incidents, HITL approval, quarantine, Decoy capture, audit, reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
