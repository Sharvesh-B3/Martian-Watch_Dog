"""CLI entry point for a persistent sensor-spoofing scenario."""

if __package__ in {None, ""}:
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sim.attacks.red_team import publish_one


if __name__ == "__main__":
    publish_one("spoof_sensor")
