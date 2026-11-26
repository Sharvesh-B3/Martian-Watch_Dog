"""Approval listing and human decision routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.app.containment_gateway import ContainmentGatewayError
from backend.app.schemas import DecisionRequest

router = APIRouter(prefix="/api", tags=["approvals"])


@router.get("/approvals")
def list_approvals(request: Request) -> list[Any]:
    return request.app.state.db.list_approvals()


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    request: Request, approval_id: str, body: DecisionRequest
) -> dict[str, Any]:
    db = request.app.state.db
    current = next(
        (
            approval
            for approval in db.list_approvals()
            if approval.id == approval_id
        ),
        None,
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if current.status != "pending":
        raise HTTPException(status_code=409, detail="Approval already decided")

    try:
        updated = request.app.state.hitl.decide(approval_id, body.decision)
    except ContainmentGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"ok": True, "id": updated.id, "status": updated.status}
