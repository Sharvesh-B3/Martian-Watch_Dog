"""Ensure backend schemas stay 1:1 with the frontend TypeScript contracts."""

import re
from pathlib import Path
from typing import get_args

import pytest

from backend.app import schemas

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_TS = REPO_ROOT / "frontend" / "src" / "types" / "watchdog.ts"


@pytest.fixture(scope="module")
def watchdog_ts() -> str:
    assert WATCHDOG_TS.exists(), f"missing frontend contract: {WATCHDOG_TS}"
    return WATCHDOG_TS.read_text(encoding="utf-8")


def _ts_type_union(ts: str, name: str) -> set[str]:
    match = re.search(rf"export type {name}\s*=\s*([^;]+);", ts, re.S)
    assert match, f"type {name} not found in watchdog.ts"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _ts_field_union(ts: str, interface: str, field: str) -> set[str]:
    match = re.search(
        rf"export interface {interface}\s*\{{.*?^\s*{field}:\s*([^;]+);",
        ts,
        re.S | re.M,
    )
    assert match, f"{interface}.{field} not found in watchdog.ts"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _ts_interface_fields(ts: str, name: str) -> set[str]:
    match = re.search(
        rf"export interface {name}\s*\{{(.*?)^}}", ts, re.S | re.M
    )
    assert match, f"interface {name} not found in watchdog.ts"
    fields: set[str] = set()
    for line in match.group(1).splitlines():
        line = line.split("//", 1)[0].strip()
        if line:
            fields.add(line.split(":", 1)[0].strip().rstrip("?"))
    return fields


@pytest.mark.parametrize(
    ("enum_cls", "ts_name"),
    [
        (schemas.DeviceStatus, "DeviceStatus"),
        (schemas.AttackCategory, "AttackCategory"),
        (schemas.ApprovalStatus, "ApprovalStatus"),
    ],
)
def test_exported_enum_matches_ts_type(enum_cls: type, ts_name: str, watchdog_ts: str):
    assert {member.value for member in enum_cls} == _ts_type_union(
        watchdog_ts, ts_name
    )


def test_inline_unions_match_ts(watchdog_ts: str):
    assert {member.value for member in schemas.DeviceType} == _ts_field_union(
        watchdog_ts, "DeviceNode", "type"
    )
    assert {member.value for member in schemas.Actor} == _ts_field_union(
        watchdog_ts, "AuditEntry", "actor"
    )
    assert set(get_args(schemas.Severity)) == _ts_field_union(
        watchdog_ts, "Incident", "severity"
    )
    assert set(get_args(schemas.RequestApprovalStatus)) == _ts_field_union(
        watchdog_ts, "ApprovalRequest", "status"
    )


@pytest.mark.parametrize(
    "model_cls",
    [
        schemas.DeviceNode,
        schemas.Incident,
        schemas.ApprovalRequest,
        schemas.AuditEntry,
    ],
)
def test_interface_fields_match_model(model_cls: type, watchdog_ts: str):
    assert set(model_cls.model_fields) == _ts_interface_fields(
        watchdog_ts, model_cls.__name__
    )
