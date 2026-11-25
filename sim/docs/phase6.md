# Phase 6 — End-to-End Integration, Runbook, and Handoff

**Status:** Planned — final Role 1 phase.  
**Scope:** Live backend/frontend integration, repeatable demo, documentation, isolation evidence, ownership handoff, and final sign-off.

## Goal

Prove the complete live workflow with mock mode disabled: normal telemetry reaches Role 2, Role 3 triggers each scenario, guardrails/correlation produce incidents, human approval produces authenticated controls, Role 1 applies containment, and the Decoy Twin captures explicitly redirected simulated traffic.

## Deliverables

- A completed root `README.md` setup and operations runbook.
- Updated declared-tools and lab-isolation documentation.
- A Role 1 handoff package containing contracts, fixtures, credentials procedure, test evidence, limitations, and ownership.
- A validated live demo sequence for all three scenarios and HITL containment.
- A documented clean reset and fallback procedure.

## Execution checklist

### 1. Integrate Role 2 with the broker

- [ ] Provision the backend identity according to the approved local credential procedure.
- [ ] Verify Role 2 subscribes only to approved telemetry/acknowledgement/decoy channels.
- [ ] Verify Role 2 publishes only approved scenario triggers and control commands.
- [ ] Verify `POST /api/sim/trigger` accepts only the three canonical frontend values and publishes the signed trigger envelope.
- [ ] Verify backend correlation uses simulator event time according to the signed clock/timing policy.
- [ ] Verify acknowledgements and device updates become backend stream/audit events.

### 2. Integrate Role 3 in live mode

- [ ] Switch the frontend from mock data using its documented environment setting.
- [ ] Verify all five canonical device IDs render without an adapter mismatch.
- [ ] Verify normal, warning, quarantined, standby/decoy, and restored states render correctly through backend events.
- [ ] Verify each demo button sends the exact canonical attack name.
- [ ] Verify Role 3 never requires direct MQTT credentials or broker access.

### 3. Validate each live scenario

- [ ] Run `spoof_sensor` and verify Role 2 observes a physics anomaly independently of prompt injection.
- [ ] Reset and run `prompt_injection`; verify the hostile untrusted field is intercepted before reasoning.
- [ ] Reset and run `coordinated_intrusion`; verify lock, missing RFID context, and power/network evidence correlate within the signed window.
- [ ] Confirm scenario lifecycle failures are visible and are never displayed as successful attacks.

### 4. Validate HITL containment end to end

- [ ] Confirm the coordinated incident creates a pending approval without changing high-risk device state.
- [ ] Approve containment in Role 3 and verify Role 2 publishes the signed controls.
- [ ] Verify `smart_lock_01` enters quarantine and acknowledges the command.
- [ ] Verify `decoy_twin_01` activates and subsequent simulated attack traffic increases real capture counters.
- [ ] Verify Role 2 persists and streams the operator decision and resulting facts.
- [ ] Reset and verify the full demonstration can be repeated without manual state repair.

### 5. Complete operations and isolation documentation

- [ ] Expand `README.md` with prerequisites, credential generation, environment setup, startup order, health verification, scenario operation, reset, shutdown, and troubleshooting.
- [ ] Document all declared tools and third-party services used by Role 1.
- [ ] Document that all devices/data are synthetic and the Decoy Twin routing is explicitly simulated.
- [ ] Include the topic/ACL overview without publishing real secrets.
- [ ] Include organiser-facing evidence for internal networking, loopback exposure, denied anonymous access, and no external runtime dependency.
- [ ] Document known limitations and stretch goals separately from completed behavior.

### 6. Rehearse and hand off

- [ ] Rehearse the agreed three-minute sequence with named operators and reset checkpoints.
- [ ] Measure scenario and recovery timing against the presentation window.
- [ ] Prepare a tested fallback that does not misrepresent mock behavior as a live MQTT run.
- [ ] Hand Role 2 the final contracts, fixtures, account permissions, and recovery notes.
- [ ] Hand Role 3 the final canonical IDs, scenario timing, states, and reset procedure.
- [ ] Assign an owner for broker operation, scenario triggering, reset, and troubleshooting during judging.

## Acceptance criteria

- [ ] A clean checkout can be configured and started by following `README.md` without undocumented steps.
- [ ] The frontend runs in live mode and all data travels through Role 2 rather than frontend mocks or direct MQTT access.
- [ ] All three scenario buttons trigger the correct Role 1 evidence and Role 2 handling.
- [ ] No high-risk containment occurs before explicit human approval.
- [ ] Approved containment produces authenticated controls, truthful acknowledgements, quarantine, Decoy Twin activation, and actual simulated capture increments.
- [ ] Full reset returns the lab to a verified normal baseline for another run.
- [ ] Isolation, ACL, synthetic-data, and declared-tools evidence is ready for inspection.
- [ ] Known limitations accurately distinguish simulated routing from broker-level rerouting.
- [ ] Roles 1, 2, and 3 sign off on the end-to-end demonstration.

## Dependencies and hand-offs

- **Requires:** all Phase 1–5 completion gates and an available Role 2 backend.
- **Role 1 owns:** broker/simulator operation, scenarios, control execution, decoy behavior, reset, and Role 1 troubleshooting.
- **Role 2 owns:** ingestion, guardrails, correlation, HITL authorization, controls, API/WebSocket, and audit persistence.
- **Role 3 owns:** operator UI, live-mode configuration, display, and presentation flow.
- **Final output:** a reproducible, documented, isolated end-to-end demonstration with explicit ownership.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Backend is unavailable or contract-incompatible | Integrate against Phase 1 fixtures early and track blockers by owner | Demonstrate Role 1 broker evidence independently and label frontend mock fallback honestly |
| Venue timing/network conditions disrupt external LLM calls | Keep Role 1 entirely local and prepare Role 2's agreed fallback | Use the pretested fallback while preserving truthful lab-state reporting |
| Demo state is dirty from rehearsal | Require baseline health/reset verification before every run | Perform the idempotent full reset or recreate the Compose lab |
| Credentials fail during judging | Test local generation and backup procedure without storing secrets in Git | Regenerate local credentials and rerun ACL smoke checks |
| Presentation overclaims Decoy Twin behavior | Use approved wording and show observable simulated route/capture events | Limit the claim to quarantine plus explicit simulated redirection |

## Completion gate

Phase 6 is complete only when the live end-to-end flow, reset, documentation, isolation evidence, and cross-team handoff all pass and each role signs off on its boundary.
