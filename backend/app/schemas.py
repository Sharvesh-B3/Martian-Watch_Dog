"""Shared data contracts; must stay 1:1 with frontend/src/types/watchdog.ts."""

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    QUARANTINED = "quarantined"
    DECOY = "decoy"


class AttackCategory(str, Enum):
    SENSOR_SPOOFING = "sensor_spoofing"
    COORDINATED_INTRUSION = "coordinated_intrusion"
    PROMPT_INJECTION = "prompt_injection"
    ANOMALOUS_TRAFFIC = "anomalous_traffic"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_EXECUTED = "auto_executed"


class DeviceType(str, Enum):
    SMART_LOCK = "smart_lock"
    RFID_SCANNER = "rfid_scanner"
    AIR_QUALITY = "air_quality"
    POWER_METER = "power_meter"
    DECOY_TWIN = "decoy_twin"


class Actor(str, Enum):
    AI_AGENT = "AI_AGENT"
    HUMAN_OPERATOR = "HUMAN_OPERATOR"
    GUARDRAIL = "GUARDRAIL"
    SYSTEM = "SYSTEM"


Severity = Literal["low", "medium", "high", "critical"]
RequestApprovalStatus = Literal["pending", "approved", "rejected"]
AttackType = Literal["spoof_sensor", "coordinated_intrusion", "prompt_injection"]
ApprovalDecision = Literal["approved", "rejected"]


class DeviceNode(BaseModel):
    id: str
    name: str
    type: DeviceType
    zone: str
    status: DeviceStatus
    metrics: dict[str, str | int | float | bool]
    last_updated: str


class Incident(BaseModel):
    id: str
    timestamp: str
    severity: Severity
    category: AttackCategory
    title: str
    plain_english_explanation: str
    correlated_device_ids: list[str]
    prompt_injection_detected: bool
    sanitized_excerpt: str | None = None
    proposed_action: str
    approval_status: ApprovalStatus


class ApprovalRequest(BaseModel):
    id: str
    incident_id: str
    created_at: str
    target_device_id: str
    recommended_action: str
    risk_summary: str
    status: RequestApprovalStatus


class AuditEntry(BaseModel):
    id: str
    timestamp: str
    actor: Actor
    action: str
    details: str


class DeviceUpdateEvent(BaseModel):
    type: Literal["device_update"] = "device_update"
    device: DeviceNode


class NewIncidentEvent(BaseModel):
    type: Literal["new_incident"] = "new_incident"
    incident: Incident


class NewApprovalEvent(BaseModel):
    type: Literal["new_approval"] = "new_approval"
    approval: ApprovalRequest


class AuditEntryEvent(BaseModel):
    type: Literal["audit_entry"] = "audit_entry"
    entry: AuditEntry


StreamEvent = Annotated[
    Union[DeviceUpdateEvent, NewIncidentEvent, NewApprovalEvent, AuditEntryEvent],
    Field(discriminator="type"),
]


class TriggerRequest(BaseModel):
    attack_type: AttackType


class DecisionRequest(BaseModel):
    decision: ApprovalDecision


class AgentModeRequest(BaseModel):
    enabled: bool
