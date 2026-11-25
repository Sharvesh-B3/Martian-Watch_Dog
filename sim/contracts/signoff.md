# Phase 1 Integration Contract Sign-off

**Contract version under review:** 1.0  
**Role 1 owner identifier:** Pending — intentionally kept generic  
**Role 2 owner identifier:** Unassigned  
**Overall status:** **Paused at Phase 1 gate pending Role 2 assignment/review**  
**Approval rule:** No checked box may be inferred from repository access, silence, or implementation work.

## Review package

- `README.md` — decisions, state semantics, scenarios, controls, Decoy routing, compatibility, and ownership.
- `mqtt_topics.md` — exact channels, QoS/retain policy, principals, permissions, and required denials.
- `poc_inventory.md` — current implementation gaps and migration protections.
- `role2_handoff.md` — derived REST/HITL-to-MQTT flow and review boundary.
- Ten Draft 2020-12 `*.schema.json` message contracts.
- `examples/valid/` and `examples/invalid/` fixtures.
- `validate_examples.py` — executable schema/fixture gate.

## Role 1 preparation

- [x] Topic purposes, publishers, subscribers, QoS, retain policy, and private/public boundaries are documented.
- [x] Canonical device IDs, types, statuses, metrics, zone, and timing are documented.
- [x] All three scenario sequences and private injection behavior are documented.
- [x] Control actions, approval references, expiry, acknowledgements, replay handling, reset, and Decoy routing are documented.
- [x] Every message class has strict valid and invalid fixtures.
- [x] The local validator passes all schemas and fixtures.
- [x] Generated broker/client credential paths are fixed and explicitly ignored by Git.
- [x] Password strength, all-accounts rotation, failure safety, and credential ownership are documented.
- [ ] Replace the generic Role 1 owner label with a person or team handle.

## Role 2 reviewer identity

- [ ] Assign the Role 2 owner/reviewer.
- **Name or handle:** `UNASSIGNED`
- **Review date:** `PENDING`
- **Backend contract/test reference:** `PENDING`

## Role 2 contract review

### MQTT boundary

- [ ] Confirm the backend can authenticate as `backend` without using any device/controller credential.
- [ ] Confirm the backend publishes only attack triggers, per-device controls, and lab reset.
- [ ] Confirm the backend subscribes only to public telemetry, presence, control acknowledgements, attack status, and safe Decoy events.
- [ ] Confirm the backend is denied from private injections, raw Decoy input, and test ground truth.
- [ ] Confirm QoS 1 and non-retained behavior is acceptable for all channels.

### Telemetry ingestion

- [ ] Validate every valid telemetry/presence fixture in Role 2 tests.
- [ ] Reject every invalid telemetry/presence fixture for a contract reason.
- [ ] Confirm UUIDv4, RFC 3339 UTC, 5-second future skew, and 60-second stale-telemetry behavior.
- [ ] Confirm presence uses `session_started_at` and that Role 2 records trusted receive time as `observed_at`, including for broker-published Last Wills.
- [ ] Confirm 10-minute event/request deduplication.
- [ ] Confirm `metadata.note` is treated as untrusted before any LLM reasoning.
- [ ] Confirm machine zone `lab-wing-a` is mapped explicitly rather than silently renamed in MQTT.

### Attack trigger and correlation

- [ ] Confirm `POST /api/sim/trigger` accepts only `spoof_sensor`, `coordinated_intrusion`, and `prompt_injection`.
- [ ] Confirm the endpoint publishes `attack_trigger.schema.json` instead of importing Role 1 code or launching a subprocess.
- [ ] Distinguish accepted MQTT publication from scenario `completed` status.
- [ ] Handle `rejected`, `duplicate`, `busy`, and `failed` lifecycle states explicitly.
- [ ] Confirm the coordinated rule uses power-scan evidence, no authorized RFID in the 5 seconds before unlock, and the wider 60-second rolling window.
- [ ] Confirm Role 2 detection never consumes private injection or ground-truth messages.

### HITL controls and audit

- [ ] Publish `QUARANTINE` and `ACTIVATE_DECOY` only after persisted human approval.
- [ ] Include non-null incident and approval references for both high-risk actions.
- [ ] Set control expiry to 30 seconds and preserve the scenario correlation ID.
- [ ] Treat `accepted` as non-final and `applied` as the successful state transition.
- [ ] Handle `rejected`, `failed`, and `duplicate` without claiming containment success.
- [ ] Retain command IDs for 24-hour replay protection or agree a contract revision.
- [ ] Persist and stream device acknowledgements and safe Decoy events in the audit trail.

### Reset and Decoy Twin

- [ ] Publish a control-shaped `RESET` to `campus/lab1/sim/reset` with `target_id=lab1`.
- [ ] Wait for five device acknowledgements plus controller reset completion.
- [ ] Confirm explicit simulated routing wording is used in API/UI/audit descriptions.
- [ ] Confirm capture success is based on a received Decoy input and incremented counter, not activation alone.

### Frontend hand-off

- [ ] Confirm backend `DeviceNode` mappings preserve all five canonical IDs, device types, statuses, metrics, and timestamps.
- [ ] Confirm `lab-wing-a` is mapped to the intended display label.
- [ ] Confirm Role 3 receives data through REST/WebSocket only and has no MQTT credential.

## Executable review gate

- [ ] Run `validate_examples.py` successfully in the agreed Python environment.
- [ ] Add Role 2 compatibility tests using the valid fixtures.
- [ ] Add Role 2 rejection tests using the invalid fixtures.
- [ ] Record any requested contract changes before checking approval.

## Approval

- [ ] **Role 1 owner approves contract version 1.0 after named ownership is recorded.**
- [ ] **Role 2 owner approves contract version 1.0 and its API/MQTT mapping.**
- [ ] Update `README.md` and `sim/docs/phase1.md` with reviewer identity, date, and final status.

### Reviewer statement

> I reviewed contract version 1.0, its topics, schemas, fixtures, timing, ACL boundaries, attack evidence, and control semantics. I confirm that Role 2 can implement the API/MQTT boundary without undocumented assumptions.

- **Role 2 name/handle:** `UNASSIGNED`
- **Decision:** `PENDING`
- **Date:** `PENDING`
- **Notes/change request:** `PENDING`

Phase 2 may use these files for design exploration, but the formal Phase 1 completion gate remains open until both approval boxes are checked by assigned owners.
