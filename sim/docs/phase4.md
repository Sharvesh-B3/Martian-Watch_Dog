# Phase 4 — HITL Containment and Decoy Twin Routing

**Status:** Superseded and completed by compressed Phase B — HITL controls, acknowledgements, quarantine, Decoy routing/capture, restore and reset passed live.
**Scope:** Approved control handling, quarantine, acknowledgements, Decoy Twin activation, explicit simulated routing, restoration, and reset.

## Goal

Complete the Sense → Think → Act loop. After Role 2 records human approval, authenticated MQTT controls must quarantine the target, activate `decoy_twin_01`, redirect subsequent simulated attacker traffic to the decoy path, and report truthful observable outcomes.

## Containment boundary

Role 1 executes valid controls but does not decide whether approval is warranted. Role 2 owns HITL authorization and audit logging. MQTT ACLs must prevent the attacker/controller account from bypassing Role 2 and issuing containment commands directly.

## Deliverables

- Contract-valid control consumers for target devices and the Decoy Twin.
- Idempotent command processing and per-command acknowledgements.
- Persistent quarantine/restore state transitions.
- Decoy standby, activation, capture, and restore behavior.
- Explicit simulated redirection of subsequent scenario traffic.
- A full-lab reset flow suitable for repeated demonstrations.

## Execution checklist

### 1. Implement safe control processing

- [ ] Accept controls only on the authorized per-device channel and from the backend account permitted by ACL.
- [ ] Validate schema version, command ID, target ID, action, issue time, expiry, and required incident/approval references.
- [ ] Reject malformed, expired, unsupported, or wrongly targeted commands without changing device state.
- [ ] Apply duplicate commands idempotently and return the original/equivalent acknowledgement.
- [ ] Publish accepted, applied, rejected, and failed acknowledgement states as defined in Phase 1.
- [ ] Never report “applied” before the local state transition succeeds.

### 2. Implement smart-lock quarantine and restoration

- [ ] Move `smart_lock_01` into a persistent quarantined state after a valid quarantine control.
- [ ] Represent physical lock/closed status consistently with the quarantined state.
- [ ] Prevent attack-scenario unlock transitions from changing the quarantined lock.
- [ ] Publish updated telemetry and a control acknowledgement carrying the command/request references.
- [ ] Restore the lock only through the signed restore/reset behavior.

### 3. Implement Decoy Twin activation

- [ ] Keep `decoy_twin_01` in standby before approved activation.
- [ ] Activate it only after a valid backend control.
- [ ] Publish contract-defined decoy state, active-trap count, captured-payload count, and last-capture metadata.
- [ ] Ensure capture payload rendering cannot turn hostile text into trusted instructions.
- [ ] Support idempotent activation and a signed restore-to-standby transition.

### 4. Implement explicit simulated routing

- [ ] Define the mapping between a quarantined target/scenario and its Decoy Twin capture destination.
- [ ] Direct subsequent simulated malicious traffic from the attack controller to the decoy route after activation.
- [ ] Stop applying that traffic to the quarantined real-device state.
- [ ] Increment capture metrics only when a message is actually received/recorded by the decoy.
- [ ] Preserve correlation IDs across trigger, attack evidence, approval control, and decoy capture events.
- [ ] Label documentation and UI-facing descriptions as simulated routing rather than transparent network rerouting.

### 5. Implement restoration and full reset

- [ ] Define an ordered reset that stops active scenarios, clears routing, restores quarantined devices, and returns the decoy to standby.
- [ ] Make reset safe to retry after partial failure.
- [ ] Publish acknowledgements or status for every reset step.
- [ ] Confirm normal telemetry resumes without stale warning/quarantine fields.
- [ ] Preserve audit ownership: Role 1 emits facts; Role 2 persists the audit trail.

### 6. Verify the complete containment sequence

- [ ] Trigger `coordinated_intrusion` through Role 2.
- [ ] Confirm no containment occurs before human approval.
- [ ] Approve containment and verify backend controls carry the approval/incident references.
- [ ] Verify lock quarantine, Decoy Twin activation, and explicit simulated redirection.
- [ ] Verify subsequent attack traffic increases decoy captures rather than unlocking the quarantined lock.
- [ ] Restore/reset and rerun the sequence from a clean state.

## Acceptance criteria

- [ ] High-risk state never changes before a valid backend control is received.
- [ ] The attacker/controller account is denied when attempting to publish a control command or forge an acknowledgement.
- [ ] Quarantine survives normal telemetry cycles and blocks later simulated unlock attempts.
- [ ] Decoy activation is observable through telemetry and acknowledgement events.
- [ ] Capture counts reflect actual simulated redirected traffic rather than activation alone.
- [ ] Duplicate commands do not duplicate state changes or capture counters.
- [ ] Restore/reset returns all five devices and the controller to the signed baseline.
- [ ] The demonstration and documentation accurately describe the routing as simulated.

## Dependencies and hand-offs

- **Requires:** Phase 1 control contracts, Phase 2 ACLs/device state machines, and Phase 3 controller/correlation IDs.
- **Input from Role 2:** approved-control publisher, approval/incident references, expiry policy, and audit ingestion.
- **Output to Role 2:** command acknowledgements, device state telemetry, and Decoy Twin capture events.
- **Output to Role 3:** backend-generated `device_update`/audit events reflecting quarantined and decoy states; Role 3 does not consume MQTT directly.
- **Output to Phase 5:** a full end-to-end state machine ready for adversarial and recovery tests.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Direct MQTT publication bypasses HITL | Enforce backend-only control ACLs and test denial | Disable control topics until ACL ownership is restored |
| Acknowledgement claims success too early | Couple “applied” to completed local transition | Treat uncertain commands as failed and restore baseline state |
| Simulated routing is overstated to judges | Use explicit terminology and observable route events | Disable the routing claim; demonstrate quarantine and decoy activation separately |
| Reset only partially succeeds | Make each step idempotent and independently acknowledged | Stop scenarios, restore from the last known state snapshot, then verify all five devices |
| Hostile captured text reaches trusted reasoning | Preserve untrusted framing and sanitization boundaries | Store only safe metadata until guardrail handling is verified |

## Completion gate

Phase 4 is complete only when pre-approval safety, backend-only controls, quarantine, real capture counting, simulated routing, idempotency, and complete reset all pass together.
