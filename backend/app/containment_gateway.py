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

    def reset_to_real(self) -> GatewayRouteResult: ...


class ContainmentGatewayClient:
    def __init__(self, settings: Any) -> None:
        self._base_url = str(settings.GATEWAY_CONTROL_URL).rstrip("/")
        self._timeout = float(settings.GATEWAY_TIMEOUT_SECONDS)

    def _post_route(
        self, path: str, incident_id: str | None, expected: str
    ) -> GatewayRouteResult:
        try:
            response = httpx.post(
                f"{self._base_url}{path}",
                json={"incident_id": incident_id} if incident_id else {},
                timeout=self._timeout,
            )
            response.raise_for_status()
            result = GatewayRouteResult.from_payload(response.json())
        except Exception as exc:
            raise ContainmentGatewayError(
                f"Containment gateway did not confirm route={expected}: {exc}"
            ) from exc
        if result.route_target != expected:
            raise ContainmentGatewayError(
                f"Containment gateway returned route={result.route_target or 'unknown'}"
            )
        return result

    def route_to_decoy(self, incident_id: str) -> GatewayRouteResult:
        return self._post_route("/route/decoy", incident_id, "decoy")

    def reset_to_real(self) -> GatewayRouteResult:
        return self._post_route("/route/real", "RESET", "real")


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

    def reset_to_real(self) -> GatewayRouteResult:
        return GatewayRouteResult(
            route_target="real",
            upstream="test-real:1883",
            disconnected_sessions=1,
            active_sessions=0,
            real_bytes=0,
            decoy_bytes=0,
            switch_count=0,
            attacker_reconnects=0,
        )
