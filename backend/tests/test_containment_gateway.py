from types import SimpleNamespace

import httpx
import pytest

from backend.app.containment_gateway import (
    ContainmentGatewayClient,
    ContainmentGatewayError,
)


class Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise httpx.HTTPStatusError(
                "gateway failure",
                request=httpx.Request("POST", "http://gateway/route/decoy"),
                response=httpx.Response(self.status),
            )

    def json(self) -> dict:
        return self.payload


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        GATEWAY_CONTROL_URL="http://127.0.0.1:9000",
        GATEWAY_TIMEOUT_SECONDS=5,
    )


def test_reset_confirms_real_route(monkeypatch) -> None:  # noqa: ANN001
    def post(url: str, *, json: dict, timeout: float) -> Response:
        assert url.endswith("/route/real")
        assert json == {"incident_id": "RESET"}
        return Response(
            {
                "route_target": "real",
                "upstream": "127.0.0.1:1883",
                "disconnected_sessions": 1,
                "active_sessions": 0,
                "real_bytes": 0,
                "decoy_bytes": 0,
                "switch_count": 0,
                "attacker_reconnects": 0,
            }
        )

    monkeypatch.setattr(httpx, "post", post)
    result = ContainmentGatewayClient(settings()).reset_to_real()

    assert result.route_target == "real"
    assert result.disconnected_sessions == 1


def test_route_to_decoy_requires_confirmation(monkeypatch) -> None:  # noqa: ANN001
    def post(url: str, *, json: dict, timeout: float) -> Response:
        assert url.endswith("/route/decoy")
        assert json == {"incident_id": "inc-1"}
        return Response(
            {
                "route_target": "decoy",
                "upstream": "127.0.0.1:1885",
                "disconnected_sessions": 1,
                "active_sessions": 0,
                "real_bytes": 100,
                "decoy_bytes": 0,
                "switch_count": 1,
                "attacker_reconnects": 0,
            }
        )

    monkeypatch.setattr(httpx, "post", post)
    result = ContainmentGatewayClient(settings()).route_to_decoy("inc-1")

    assert result.route_target == "decoy"
    assert result.disconnected_sessions == 1


@pytest.mark.parametrize(
    "response",
    [
        Response({"route_target": "real"}),
        Response({}, status=503),
    ],
)
def test_route_failure_is_explicit(monkeypatch, response: Response) -> None:  # noqa: ANN001
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)

    with pytest.raises(ContainmentGatewayError):
        ContainmentGatewayClient(settings()).route_to_decoy("inc-1")
