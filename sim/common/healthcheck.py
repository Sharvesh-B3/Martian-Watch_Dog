"""Docker health check for a running device publisher."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def check_health(path: Path, max_age_seconds: float, now: float | None = None) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        current = time.time() if now is None else now
        last_publish = float(state["last_publish_epoch"])
        return bool(state["connected"]) and 0 <= current - last_publish <= max_age_seconds
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def main() -> int:
    path = Path(os.getenv("HEALTH_FILE", "/tmp/watchdog-health.json"))
    try:
        max_age = float(os.getenv("HEALTH_MAX_AGE_SECONDS", "15"))
    except ValueError:
        return 1
    return 0 if check_health(path, max_age) else 1


if __name__ == "__main__":
    sys.exit(main())
