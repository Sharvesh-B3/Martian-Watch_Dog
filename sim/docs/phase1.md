# Phase 1 — Contract Freeze and Integration Agreement

**Status:** Technical contract implemented end to end; formal named Role 1/Role 2 sign-off remains pending.
**Scope:** Role 1 simulator and broker contracts, plus explicit hand-offs to Roles 2 and 3.

## Goal

Freeze the device identities, MQTT channel purposes, JSON envelopes, attack names, control semantics, timing assumptions, and ownership boundaries before implementation is refactored. No later phase should invent an interface locally.

## Locked project decisions

- The core topology contains exactly five devices: `smart_lock_01`, `rfid_scanner_01`, `air_quality_01`, `power_meter_01`, and `decoy_twin_01`.
- Every device runs as a separate Docker Compose service with its own MQTT client identity.
- Role 2 triggers attacks by publishing to an MQTT scenario-trigger channel from `POST /api/sim/trigger`.
- Decoy containment uses explicit simulated routing; it must not be presented as transparent broker/network routing.
- Mosquitto uses authenticated accounts and topic ACLs.
- Existing proof-of-concept behavior is reusable evidence, but no task is complete until it passes the final contract.

## Decisions that must be recorded with Role 2

Do not silently select defaults for these items. Record the agreed values in the contract documentation before Phase 2 begins.

Role 1's provisional values are now recorded in `sim/contracts/README.md` and `sim/contracts/mqtt_topics.md`. Role 2 must explicitly accept or request changes; its approval has not been inferred.

- MQTT root namespace and the exact topic for each semantic channel:
  - per-device telemetry;
  - per-device control;
  - per-device control acknowledgement;
  - attack scenario trigger;
  - attack scenario status;
  - Decoy Twin capture/events;
  - test-only ground truth, isolated from production agent input.
- MQTT QoS and retained-message policy for every channel.
- Telemetry schema version and compatibility policy.
- Normal telemetry interval, scenario timing, attack dwell time, and reset behavior.
- Timestamp format, clock-skew tolerance, unique event ID format, request/correlation ID propagation, and duplicate handling.
- Canonical control action names and acknowledgement states.
- Which telemetry fields are explicitly untrusted and therefore pass through Role 2's guardrail.
- Credential creation, local secret storage, rotation, and ownership.

## Deliverables

- `sim/contracts/mqtt_topics.md` — exact topic map, publishers, subscribers, QoS, retain policy, and ACL ownership.
- Versioned JSON Schemas under `sim/contracts/` for telemetry, attack triggers/status, control commands/acknowledgements, and Decoy Twin events.
- Valid and invalid fixture payloads under `sim/contracts/examples/`.
- A responsibility matrix identifying Role 1, Role 2, and Role 3 ownership.
- Written sign-off from Role 2 that the backend can consume and produce the agreed messages.
- Written confirmation that canonical device IDs and statuses map to `frontend/src/types/watchdog.ts`.

## Execution checklist

### 1. Inventory and reconcile the current proof of concept

- [x] Map every current topic, payload field, device ID, action, and attack in `sim/devices/sim_devices.py`, `sim/attacks/red_team.py`, and `sim/monitor.py`.
- [x] List every mismatch against `plan.md`, `struct.md`, `frontend/src/types/watchdog.ts`, and `frontend/src/api/client.ts`.
- [x] Mark reusable logic separately from behavior that must be replaced; do not delete the proof of concept in this phase.

### 2. Freeze identities and state vocabulary

- [x] Record the five canonical device IDs and device types.
- [x] Define normal, warning, quarantined, standby, active-decoy, and restored state semantics.
- [x] Confirm the lower-case device statuses exposed to Role 3.
- [x] Define how device-specific metrics are nested without changing the common envelope.

### 3. Freeze the telemetry contract

- [x] Define required envelope fields, including schema version, event ID, device ID/type, zone, timestamp, status, and metrics.
- [x] Define device-specific metric requirements and physical ranges for all five devices.
- [x] Identify untrusted free-text/metadata fields used for prompt-injection testing.
- [x] Define validation behavior for missing, malformed, stale, duplicate, and future-dated messages.
- [x] Create representative normal and anomalous payload fixtures.

### 4. Freeze scenario-trigger contracts

- [x] Use only the public attack names `spoof_sensor`, `coordinated_intrusion`, and `prompt_injection`.
- [x] Define trigger fields, scenario status events, correlation IDs, idempotency behavior, and error responses.
- [x] Define the exact event sequence and timing constraints for each scenario.
- [x] Keep ground-truth labels on a test-only channel that Role 2's detector does not consume.

### 5. Freeze containment contracts

- [x] Define quarantine, Decoy Twin activation, restore, and full-lab reset semantics.
- [x] Define command IDs, approval/incident references, issue time, expiry, and acknowledgement fields.
- [x] Define idempotent handling for duplicate commands.
- [x] Define how explicit simulated routing changes the destination of subsequent attack traffic.
- [x] Define the observable telemetry and acknowledgement expected after each command.

### 6. Freeze security and ownership

- [x] Produce an ACL matrix for simulator, attacker/controller, backend, and read-only observer accounts.
- [x] Confirm that only the backend account can publish high-risk control commands.
- [x] Confirm that the attacker account cannot publish control commands or forge acknowledgements.
- [x] Confirm that secrets and generated Mosquitto password files will not be committed.
- [ ] Assign contract-change approval to named Role 1 and Role 2 owners.

## Acceptance criteria

- [x] Every MQTT topic has one documented purpose, authorized publishers/subscribers, QoS, and retain policy.
- [x] Every message class has a versioned schema and at least one valid and invalid fixture.
- [x] The five device IDs and three attack names exactly match frontend-facing contracts.
- [ ] Role 2 can explain how `/api/sim/trigger`, telemetry ingestion, and approved controls map to MQTT without undocumented behavior.
- [x] Role 3 can map device status and metrics without reading raw MQTT.
- [x] All unresolved decisions are explicitly listed; none are hidden as implementation defaults.
- [ ] Role 1 and Role 2 approve the contract before Phase 2 starts.

## Dependencies and hand-offs

- **Input from Role 2:** backend schema expectations, correlation-window semantics, control publisher behavior, and credential needs.
- **Input from Role 3:** canonical device IDs/statuses and attack names already exposed by the frontend.
- **Output to Phase 2:** approved topic map, schemas, fixtures, timing values, and ACL matrix.
- **Blocking rule:** Phase 2 must not freeze code around an unsigned or incomplete contract.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Role 1 and Role 2 implement different topics or payloads | Require fixture-based contract review before coding | Pause implementation and return to the last signed contract version |
| Frontend names differ from simulator names | Treat frontend canonical IDs and attack names as an explicit sign-off item | Keep adapters outside device logic until all teams agree |
| A test-only ground-truth label leaks into detection | Use a separate ACL-protected channel and consumer list | Disable the ground-truth publisher until isolation is verified |
| The contract grows beyond hackathon scope | Separate required MVP fields from optional extensions | Remove unsigned optional fields without changing the signed core |

## Completion gate

Phase 1 is complete only when the contracts and ACL matrix exist, all acceptance criteria pass, and Role 2 has explicitly approved the integration boundary.

**Current blockers:** name the Role 1 and Role 2 contract owners; obtain Role 2 review/sign-off and its explanation of the API/MQTT boundary.

**Gate decision (updated 2026-11-25):** Compressed technical Phases A–C were authorized and completed against contract version 1.0. The FastAPI/MQTT/frontend E2E tests demonstrate compatibility; only named human ownership/signature remains open.

## Current verification evidence

- `sim/contracts/validate_examples.py` passes 10 Draft 2020-12 schemas and 41 fixtures, with valid and invalid coverage for every message class.
- The valid fixture set contains 30 messages; the negative set contains 11 intentional failures with confirmed contract errors.
- Git ignore checks confirm `sim/.env` and `sim/broker/generated/passwd` are excluded.
- `sim/contracts/role2_handoff.md` maps the existing frontend API/HITL flow to the signed MQTT boundary without granting Role 2 private-topic access.
- `sim/contracts/signoff.md` records every remaining human review item; all Role 2 approval fields remain visibly pending.
