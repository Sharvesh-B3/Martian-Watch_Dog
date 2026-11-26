"""Client for the isolated TCP containment gateway."""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class ContainmentGatewayError(RuntimeError):
    """Raised when network rerouting cannot be confirmed."""


@dataclass(frozen=True)
class GatewayRouteResult:
    route_target: str
    upstream: str
    disconnected_sessions: int
    active_sessions: int
    real_bytes: int
    decoy_bytes: int
    switch_count: int
    attacker_reconnects: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GatewayRouteResult":
        return cls(
            route_target=str(payload.get("route_target", "")),
            upstream=str(payload.get("upstream", "")),
            disconnected_sessions=int(payload.get("disconnected_sessions", 0)),
            active_sessions=int(payload.get("active_sessions", 0)),
            real_bytes=int(payload.get("real_bytes", 0)),
            decoy_bytes=int(payload.get("decoy_bytes", 0)),
            switch_count=int(payload.get("switch_count", 0)),
            attacker_reconnects=int(payload.get("attacker_reconnects", 0)),
        )


class ContainmentGateway(Protocol):
    def route_to_decoy(self, incident_id: str) -> GatewayRouteResult: ...


class ContainmentGatewayClient:
    def __init__(self, settings: Any) -> None:
        self._base_url = str(settings.GATEWAY_CONTROL_URL).rstrip("/")
        self._timeout = float(settings.GATEWAY_TIMEOUT_SECONDS)

    def route_to_decoy(self, incident_id: str) -> GatewayRouteResult:
        try:
            response = httpx.post(
                f"{self._base_url}/route/decoy",
                json={"incident_id": incident_id},
                timeout=self._timeout,
            )
            response.raise_for_status()
            result = GatewayRouteResult.from_payload(response.json())
        except Exception as exc:
            raise ContainmentGatewayError(
                f"Containment gateway did not confirm reroute: {exc}"
            ) from exc
        if result.route_target != "decoy":
            raise ContainmentGatewayError(
                f"Containment gateway returned route={result.route_target or 'unknown'}"
            )
        return result


class TestContainmentGateway:
    """Deterministic default used by isolated unit tests."""

    def route_to_decoy(self, incident_id: str) -> GatewayRouteResult:
        return GatewayRouteResult(
            route_target="decoy",
            upstream="test-decoy:1883",
            disconnected_sessions=1,
            active_sessions=0,
            real_bytes=0,
            decoy_bytes=0,
            switch_count=1,
            attacker_reconnects=0,
        )
