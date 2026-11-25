# Phase 3 — Attack Scenarios and MQTT Trigger Controller

**Status:** Superseded and completed by compressed Phase B — all three live scenarios and MQTT lifecycle behavior passed.
**Scope:** Attack controller, three canonical scenarios, repeatable state transitions, and backend trigger hand-off.

## Goal

Provide one MQTT-triggered controller that executes exactly the three public attack scenarios used by the frontend and backend, produces realistic malicious telemetry without leaking ground truth to the detector, and reports deterministic scenario lifecycle events.

## Public scenarios

- `spoof_sensor`
- `coordinated_intrusion`
- `prompt_injection`

The port-scan/lateral-movement event is evidence inside `coordinated_intrusion`, not a fourth public scenario.

## Deliverables

- A dedicated attack-controller Compose service authenticated with the Phase 1 attacker/controller account.
- One implementation module for each canonical scenario.
- An optional operator CLI that publishes the same trigger contract as Role 2 rather than duplicating attack logic.
- Scenario accepted/started/completed/failed status messages carrying the original request/correlation ID.
- Test-only ground-truth output isolated by ACL and consumer policy.
- Reset-safe, repeatable attack state transitions.

## Execution checklist

### 1. Implement the trigger controller

- [ ] Subscribe only to the signed scenario-trigger topic.
- [ ] Validate every trigger against the versioned schema before execution.
- [ ] Reject unknown attack names, malformed requests, stale requests, and unauthorized publishers.
- [ ] Apply the signed duplicate/idempotency policy using the request ID.
- [ ] Publish scenario lifecycle status without claiming success before all required events are emitted.
- [ ] Propagate the same request/correlation ID into logs, scenario events, and test-only ground truth.
- [ ] Serialize or reject overlapping scenarios according to the Phase 1 decision.

### 2. Implement `spoof_sensor`

- [ ] Inject a physically implausible but schema-valid sensor measurement into `air_quality_01` telemetry.
- [ ] Keep this scenario free of prompt-injection instructions so Role 2 can classify it independently.
- [ ] Preserve enough neighbouring normal telemetry for Role 2 to demonstrate physics-aware filtering.
- [ ] Hold or repeat the anomaly for the agreed dwell period so it is observable without permanently corrupting normal state.
- [ ] Restore normal telemetry automatically or through the signed reset behavior.

### 3. Implement `prompt_injection`

- [ ] Place adversarial instructions only in the contract-defined untrusted telemetry field.
- [ ] Keep the outer payload valid so rejection demonstrates guardrail behavior rather than JSON parsing failure.
- [ ] Include the agreed sensor context needed for the live demonstration.
- [ ] Do not publish the intended classification on any topic consumed by Role 2's agent.
- [ ] Return to a valid normal state after the agreed dwell/reset transition.

### 4. Implement `coordinated_intrusion`

- [ ] Produce abnormal outbound scan/network evidence from `power_meter_01`.
- [ ] Preserve the absence of a valid matching RFID event during the signed correlation interval; do not fake an explicit “missing scan” message.
- [ ] Publish an unauthorized unlock transition from `smart_lock_01` within the agreed window.
- [ ] Use fresh timestamps/event IDs for each event while retaining the scenario correlation ID in test diagnostics.
- [ ] Keep all required evidence observable long enough for Role 2's rolling correlation window.
- [ ] Exclude CCTV from the core scenario.

### 5. Add operator and backend trigger paths

- [ ] Make the operator CLI publish the exact same MQTT trigger payload used by Role 2.
- [ ] Confirm Role 2's `POST /api/sim/trigger` maps frontend names to the MQTT trigger without translation drift.
- [ ] Define the API response rule: accepted trigger versus completed scenario must remain distinguishable.
- [ ] Surface controller failures to Role 2 through the signed status channel.

### 6. Verify repeatability and isolation

- [ ] Run each scenario repeatedly from a clean state and after a reset.
- [ ] Verify one scenario does not leave state that changes the classification of the next scenario.
- [ ] Verify the normal device publishers do not erase attack evidence before the agreed dwell period.
- [ ] Confirm ground-truth topics are inaccessible to the backend detector identity.
- [ ] Confirm the attacker/controller account cannot publish high-risk device controls.

## Acceptance criteria

- [ ] All three exact public names are accepted; any other name is rejected safely.
- [ ] `spoof_sensor` contains no prompt injection and produces a physics anomaly.
- [ ] `prompt_injection` contains a valid outer envelope and adversarial untrusted text.
- [ ] `coordinated_intrusion` contains power/network evidence, no matching RFID event, and an unauthorized lock transition inside the agreed window.
- [ ] Every accepted trigger yields traceable lifecycle status with the original request ID.
- [ ] Repeated or duplicate triggers follow the signed idempotency policy.
- [ ] Role 2 can activate all scenarios through `/api/sim/trigger` without importing Role 1 code or launching a subprocess.
- [ ] Detection remains Role 2's responsibility; no consumed telemetry reveals the expected verdict.

## Dependencies and hand-offs

- **Requires:** Phase 1 trigger/schema decisions and Phase 2 broker/device stability.
- **Input from Role 2:** API request validation, MQTT trigger publisher, and correlation timing confirmation.
- **Input from Role 3:** exact attack strings already declared in `frontend/src/api/client.ts`.
- **Output to Phase 4:** stateful attack controller capable of redirecting subsequent simulated traffic after containment.
- **Output to Role 2:** scenario fixtures, expected evidence (not expected detection internals), and lifecycle status contract.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Normal telemetry immediately overwrites attack evidence | Use the signed state/dwell model instead of one-off publications | Disable the failing scenario and restore the last known normal state |
| Trigger acknowledgement is confused with scenario completion | Use distinct lifecycle states | Revert consumers to accepted-only handling until completion semantics are fixed |
| Ground truth biases agent detection | Protect it with a separate ACL and consumer audit | Disable ground-truth publication entirely |
| Scenario overlap creates nondeterministic evidence | Serialize or reject overlap per contract | Reset the lab and rerun one scenario at a time |
| Attack code becomes coupled to FastAPI | Keep MQTT as the only trigger boundary | Remove the coupling and return to the last schema-valid controller build |

## Completion gate

Phase 3 is complete only when every scenario passes its evidence tests, Role 2 can trigger it over MQTT via the API, lifecycle status is traceable, and repeated runs reset cleanly.
