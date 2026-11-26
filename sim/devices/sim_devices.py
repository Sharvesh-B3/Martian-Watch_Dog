"""Compatibility wrapper for the new multi-process lab launcher."""

if __package__ in {None, ""}:
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sim.run_lab import main


if __name__ == "__main__":
    main()
