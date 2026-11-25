"""Validate every Role 1 contract schema and example fixture.

This script requires the third-party ``jsonschema`` package with Draft 2020-12
support. Phase 1 validation uses the repository's ignored local virtual
environment; Phase 2 will pin runtime/test dependencies in ``sim/requirements.txt``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - explicit operator guidance
    raise SystemExit(
        "Missing dependency: install 'jsonschema' in the active environment "
        "before validating contract fixtures."
    ) from exc


ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"

# Longest/specific prefixes must appear before broader ones.
SCHEMA_BY_PREFIX = (
    ("attack_trigger_", "attack_trigger.schema.json"),
    ("attack_status_", "attack_status.schema.json"),
    ("control_ack_", "control_ack.schema.json"),
    ("decoy_input_", "decoy_input.schema.json"),
    ("decoy_event_", "decoy_event.schema.json"),
    ("ground_truth_", "ground_truth.schema.json"),
    ("telemetry_", "telemetry.schema.json"),
    ("presence_", "presence.schema.json"),
    ("injection_", "injection.schema.json"),
    ("control_", "control.schema.json"),
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def schema_name_for(path: Path) -> str:
    for prefix, schema_name in SCHEMA_BY_PREFIX:
        if path.name.startswith(prefix):
            return schema_name
    raise ValueError(f"No schema mapping for fixture: {path.relative_to(ROOT)}")


def format_error(error: Any) -> str:
    location = "/".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"


def main() -> int:
    failures: list[str] = []
    validators: dict[str, Draft202012Validator] = {}

    for schema_path in sorted(ROOT.glob("*.schema.json")):
        try:
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                failures.append(
                    f"{schema_path.name} does not declare Draft 2020-12 exactly"
                )
            if schema.get("additionalProperties") is not False:
                failures.append(
                    f"{schema_path.name} is not strict at the message-envelope level"
                )
            validators[schema_path.name] = Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            )
        except (json.JSONDecodeError, SchemaError) as exc:
            failures.append(f"Invalid schema {schema_path.name}: {exc}")

    expected_schemas = {schema for _, schema in SCHEMA_BY_PREFIX}
    missing_schemas = expected_schemas - validators.keys()
    extra_schemas = validators.keys() - expected_schemas
    if missing_schemas:
        failures.append(f"Missing mapped schemas: {sorted(missing_schemas)}")
    if extra_schemas:
        failures.append(f"Schemas without fixture mapping: {sorted(extra_schemas)}")

    coverage: dict[str, set[str]] = defaultdict(set)
    case_count = 0

    for expectation in ("valid", "invalid"):
        fixture_dir = EXAMPLES / expectation
        for fixture_path in sorted(fixture_dir.glob("*.json")):
            case_count += 1
            try:
                schema_name = schema_name_for(fixture_path)
                instance = load_json(fixture_path)
            except (ValueError, json.JSONDecodeError) as exc:
                failures.append(str(exc))
                continue

            validator = validators.get(schema_name)
            if validator is None:
                failures.append(
                    f"Cannot validate {fixture_path.name}: {schema_name} unavailable"
                )
                continue

            errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
            coverage[schema_name].add(expectation)

            if expectation == "valid" and errors:
                details = "; ".join(format_error(error) for error in errors)
                failures.append(f"Expected valid {fixture_path.name}: {details}")
            elif expectation == "invalid" and not errors:
                failures.append(
                    f"Expected invalid {fixture_path.name}, but it passed {schema_name}"
                )

            if (
                expectation == "valid"
                and schema_name == "decoy_input.schema.json"
                and not errors
            ):
                actual_hash = hashlib.sha256(instance["content"].encode("utf-8")).hexdigest()
                if actual_hash != instance["content_sha256"]:
                    failures.append(
                        f"{fixture_path.name} content_sha256 does not match content"
                    )

    for schema_name in sorted(expected_schemas):
        missing_expectations = {"valid", "invalid"} - coverage[schema_name]
        if missing_expectations:
            failures.append(
                f"{schema_name} lacks fixtures for: {sorted(missing_expectations)}"
            )

    if failures:
        print("Contract validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        f"Contract validation passed: {len(validators)} schemas, "
        f"{case_count} fixtures, valid/invalid coverage for every message class."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
