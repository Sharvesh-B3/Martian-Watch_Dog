"""Rolling 60-second multi-device correlation for the lab wing."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import threading
from typing import Any, Literal, Mapping

from backend.app.schemas import AttackCategory, Severity

RiskLevel = Literal["low", "high"]


@dataclass(frozen=True)
class Signal:
    """A detection handed to the agent for reasoning."""

    category: AttackCategory
    severity: Severity
    device_ids: tuple[str, ...]
    summary: str
    risk_level: RiskLevel
    auto_execute: bool
    prompt_injection_detected: bool = False
    sanitized_excerpt: str | None = None


@dataclass(frozen=True)
class _Record:
    timestamp: datetime
    canonical_id: str
    topic: str
    payload: dict[str, Any]
    injection_detected: bool
    sanitized_excerpt: str | None


class CorrelationWindow:
    """Timestamp-pruned telemetry buffer with cross-device rules."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._records: deque[_Record] = deque()
        self._last_emitted: dict[str, datetime] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def add(
        self,
        canonical_id: str,
        payload: Mapping[str, Any],
        *,
        topic: str = "",
        injection_detected: bool = False,
        sanitized_excerpt: str | None = None,
        timestamp: Any = None,
    ) -> None:
        record = _Record(
            timestamp=self._parse_timestamp(timestamp or payload.get("timestamp")),
            canonical_id=canonical_id,
            topic=topic,
            payload=dict(payload),
            injection_detected=injection_detected,
            sanitized_excerpt=sanitized_excerpt,
        )
        with self._lock:
            self._records.append(record)
            self._prune(record.timestamp)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._last_emitted.clear()

    def evaluate(self, reference: datetime | None = None) -> list[Signal]:
        with self._lock:
            return self._evaluate_locked(reference)

    def _evaluate_locked(self, reference: datetime | None = None) -> list[Signal]:
        if not self._records:
            return []
        reference = reference or self._records[-1].timestamp
        self._prune(reference)

        signals: list[Signal] = []
        records = list(self._records)

        for record in records:
            if record.injection_detected:
                self._emit(
                    signals,
                    Signal(
                        category=AttackCategory.PROMPT_INJECTION,
                        severity="high",
                        device_ids=(record.canonical_id,),
                        summary=(
                            f"Instruction override detected in telemetry from "
                            f"{record.canonical_id}; payload was sanitized before reasoning."
                        ),
                        risk_level="low",
                        auto_execute=True,
                        prompt_injection_detected=True,
                        sanitized_excerpt=record.sanitized_excerpt,
                    ),
                    reference,
                    self._fingerprint("prompt_injection", record),
                )

            if record.canonical_id == "air_quality_01" and (
                reasons := self._spoof_reasons(record.payload)
            ):
                self._emit(
                    signals,
                    Signal(
                        category=AttackCategory.SENSOR_SPOOFING,
                        severity="medium",
                        device_ids=(record.canonical_id,),
                        summary=(
                            f"Implausible air-quality reading from {record.canonical_id}: "
                            + "; ".join(reasons)
                            + "."
                        ),
                        risk_level="low",
                        auto_execute=True,
                    ),
                    reference,
                    self._fingerprint("sensor_spoofing", record),
                )

        unlocks = [r for r in records if self._is_unlock(r.payload)]
        port_scans = [
            r
            for r in records
            if r.canonical_id == "power_meter_01" and self._is_port_scan(r.payload)
        ]
        badges = [
            r
            for r in records
            if r.canonical_id == "rfid_scanner_01" and self._is_badge(r.payload)
        ]
        coordinated_pairs = [
            (unlock, port_scan)
            for unlock in unlocks
            for port_scan in port_scans
            if self._scenario_compatible(unlock, port_scan)
        ]

        if coordinated_pairs and not badges:
            ordered_pairs = sorted(
                coordinated_pairs,
                key=lambda pair: max(pair[0].timestamp, pair[1].timestamp),
                reverse=True,
            )
            unlock, port_scan = next(
                (
                    pair
                    for pair in ordered_pairs
                    if self._fingerprint(
                        "coordinated_intrusion", pair[0], pair[1]
                    )
                    not in self._last_emitted
                ),
                ordered_pairs[0],
            )
            connections = port_scan.payload.get("network_conns")
            flags = port_scan.payload.get("anomaly_flag")
            cctv_offline = any(
                r.canonical_id == "cctv_01"
                and str(r.payload.get("heartbeat", "")).upper() == "OFFLINE"
                for r in records
            )
            evidence = (
                f"{unlock.canonical_id} reported UNLOCKED / "
                f"UNAUTHORIZED_BYPASS while {port_scan.canonical_id} showed "
                f"{connections} outbound connections and anomaly flag {flags}"
            )
            if cctv_offline:
                evidence += "; cctv_01 heartbeat went OFFLINE"
            self._emit(
                signals,
                Signal(
                    category=AttackCategory.COORDINATED_INTRUSION,
                    severity="critical",
                    device_ids=(
                        "smart_lock_01",
                        "rfid_scanner_01",
                        "power_meter_01",
                    ),
                    summary=evidence + "; no RFID badge seen in the 60s window.",
                    risk_level="high",
                    auto_execute=False,
                ),
                reference,
                self._fingerprint("coordinated_intrusion", unlock, port_scan),
            )
        elif port_scans:
            self._emit(
                signals,
                Signal(
                    category=AttackCategory.ANOMALOUS_TRAFFIC,
                    severity="medium",
                    device_ids=("power_meter_01",),
                    summary=(
                        f"Outbound port-scan behavior detected on "
                        f"{port_scans[-1].canonical_id} without a paired door unlock."
                    ),
                    risk_level="low",
                    auto_execute=True,
                ),
                reference,
                self._fingerprint("anomalous_traffic", port_scans[-1]),
            )

        return signals

    # --------------------------------- helpers ------------------------------

    def _prune(self, reference: datetime) -> None:
        cutoff = reference - timedelta(seconds=self.window_seconds)
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()

    def _emit(
        self,
        signals: list[Signal],
        signal: Signal,
        reference: datetime,
        event_key: str,
    ) -> None:
        if event_key in self._last_emitted:
            return
        self._last_emitted[event_key] = reference
        signals.append(signal)

    @staticmethod
    def _fingerprint(kind: str, *records: _Record) -> str:
        """Deduplicate MQTT echoes without suppressing a later real attack."""
        scenario_ids = [
            str(record.payload.get("scenario_id"))
            for record in records
            if record.payload.get("scenario_id")
        ]
        if len(scenario_ids) == len(records) and len(set(scenario_ids)) == 1:
            return f"{kind}:scenario:{scenario_ids[0]}"
        evidence = [
            {
                "timestamp": record.timestamp.isoformat(),
                "canonical_id": record.canonical_id,
                "topic": record.topic,
                "payload": record.payload,
            }
            for record in records
        ]
        serialized = json.dumps(evidence, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{kind}:{digest}"

    @staticmethod
    def _scenario_compatible(first: _Record, second: _Record) -> bool:
        first_id = first.payload.get("scenario_id")
        second_id = second.payload.get("scenario_id")
        if first_id and second_id:
            return first_id == second_id
        if bool(first_id) != bool(second_id):
            return False
        # Legacy frames without scenario IDs must belong to the same short
        # burst; do not correlate unrelated evidence across the full window.
        return abs((first.timestamp - second.timestamp).total_seconds()) <= 0.01

    @staticmethod
    def _spoof_reasons(payload: Mapping[str, Any]) -> list[str]:
        reasons: list[str] = []
        co2 = payload.get("co2_ppm")
        temp = payload.get("temp_c")
        if isinstance(co2, (int, float)) and co2 > 1000:
            reasons.append(f"CO2 {co2} ppm exceeds 1000")
        if isinstance(temp, (int, float)) and not 10 <= temp <= 35:
            reasons.append(f"temperature {temp} C outside 10-35")
        return reasons

    @staticmethod
    def _is_unlock(payload: Mapping[str, Any]) -> bool:
        status = str(payload.get("status", "")).upper()
        last_rfid = str(payload.get("last_rfid", "")).upper()
        return status == "UNLOCKED" or last_rfid == "UNAUTHORIZED_BYPASS"

    @staticmethod
    def _is_port_scan(payload: Mapping[str, Any]) -> bool:
        connections = payload.get("network_conns")
        flag = str(payload.get("anomaly_flag", "")).upper()
        return (isinstance(connections, (int, float)) and connections > 50) or (
            "PORT_SCAN" in flag
        )

    @staticmethod
    def _is_badge(payload: Mapping[str, Any]) -> bool:
        badge_id = payload.get("badge_id")
        event = str(payload.get("event", "")).upper()
        return bool(badge_id) or event in {"SCAN", "GRANTED", "ACCEPTED"}
