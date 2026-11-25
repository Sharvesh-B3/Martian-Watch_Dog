# Phase 5 — Hardening, Automated Verification, and Observability

**Status:** Planned — starts after the complete Phase 4 state machine works.  
**Scope:** Automated tests, ACL/security checks, failure recovery, network isolation evidence, diagnostics, and regression protection.

## Goal

Turn the working lab into a repeatable and defensible system. Verify positive behavior, expected denials, malformed input handling, restart recovery, timing boundaries, and isolation without relying on manual observation alone.

## Deliverables

- Unit, contract, integration, security, and end-to-end Role 1 tests under `sim/tests/`.
- A read-only observer/monitor that displays facts but does not perform or influence Role 2 detection.
- Correlation-friendly structured logs with secret and hostile-content redaction.
- Reproducible network-isolation and ACL test evidence.
- A failure/recovery matrix and resolved critical defects.

## Execution checklist

### 1. Add contract and unit tests

- [ ] Validate every valid fixture against its schema.
- [ ] Confirm every invalid fixture fails for the expected reason.
- [ ] Test device physics/range generation with deterministic seeds.
- [ ] Test state transitions for normal, attacked, quarantined, decoy-active, restored, and reset states.
- [ ] Test trigger and command idempotency without requiring the live broker where practical.
- [ ] Test stale, duplicate, out-of-order, future-dated, and malformed inputs.

### 2. Add broker integration tests

- [ ] Verify all five devices connect and publish to only authorized topics.
- [ ] Verify each authorized account operation from the ACL matrix.
- [ ] Verify anonymous access and every prohibited publish/subscribe operation fail.
- [ ] Verify backend-only control ownership and observer read-only access.
- [ ] Verify QoS and retained-message behavior matches the Phase 1 topic map.
- [ ] Verify unique client IDs prevent unintended session replacement.

### 3. Add scenario and containment tests

- [ ] Assert the exact evidence emitted by each of the three scenarios.
- [ ] Assert timing stays inside the signed backend correlation window.
- [ ] Assert no high-risk containment occurs before an approved backend control.
- [ ] Assert quarantine, activation, redirection, capture counting, restore, and reset outcomes.
- [ ] Assert duplicate triggers/commands follow idempotency rules.
- [ ] Assert sequential scenarios cannot contaminate each other's starting state.

### 4. Test failure and recovery paths

- [ ] Restart Mosquitto during normal telemetry and verify bounded client recovery.
- [ ] Restart each device independently and verify truthful online/offline state.
- [ ] Restart the attack controller during an active scenario and verify the signed recovery policy.
- [ ] Interrupt containment between quarantine and decoy activation and verify partial-failure reporting.
- [ ] Test unavailable/expired credentials and actionable startup failures.
- [ ] Test a full clean restart after an unclean shutdown.

### 5. Prove lab isolation and secret hygiene

- [ ] Verify host exposure matches the signed network contract and is not bound broadly by accident.
- [ ] Verify internal simulator services cannot reach external networks unless explicitly approved.
- [ ] Verify only required ports are published.
- [ ] Verify generated credentials, password databases, environment overrides, and logs containing secrets are untracked.
- [ ] Record the exact evidence needed for organiser lab inspection.

### 6. Establish safe observability

- [ ] Keep `sim/monitor.py` or its replacement read-only under the observer account.
- [ ] Display topic, device ID, event ID, correlation ID, safe state summary, and validation outcome.
- [ ] Do not label monitor rules as the AI detector or feed monitor verdicts into Role 2.
- [ ] Redact credentials and bound hostile free-text output.
- [ ] Make logs sufficient to trace trigger → telemetry → control → acknowledgement → decoy capture.

### 7. Add regression gates

- [ ] Define the required automated suite before merging Role 1 changes.
- [ ] Fail the suite on schema drift, topic drift, ACL widening, canonical-name changes, or dirty reset state.
- [ ] Document how test fixtures and schema versions evolve together.
- [ ] Classify failures as release-blocking or explicitly deferred with an owner.

## Acceptance criteria

- [ ] All required tests pass from a clean checkout with newly generated local credentials.
- [ ] Positive and negative ACL tests cover every account class and sensitive topic.
- [ ] Broker/device/controller restarts recover within signed bounds or report explicit failure.
- [ ] No scenario leaves state that changes a later test's result.
- [ ] Isolation checks demonstrate no undocumented external access or exposed listener.
- [ ] Observer output is useful for debugging but cannot influence backend detection.
- [ ] Logs trace the entire lifecycle without exposing secrets or treating hostile text as trusted.
- [ ] No unresolved critical defect proceeds to Phase 6.

## Dependencies and hand-offs

- **Requires:** the complete Phase 1–4 contracts and implementation.
- **Input from Role 2:** correlation boundary tests, backend MQTT permissions, and acknowledgement expectations.
- **Output to Role 2:** regression fixtures and a stable integration test environment.
- **Output to Role 3:** deterministic scenarios and reset behavior for browser/demo validation.
- **Output to Phase 6:** test reports, isolation evidence, known non-critical limitations, and a stable release candidate.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Tests validate implementation quirks instead of signed behavior | Derive assertions from Phase 1 contracts and acceptance criteria | Replace brittle tests while keeping the signed contract unchanged |
| Recovery tests leave the lab dirty | Give every test explicit setup/teardown and baseline assertions | Tear down the test environment and recreate credentials/state from scratch |
| ACL hardening breaks integration | Run positive and negative permission tests together | Restore the last reviewed ACL matrix; never fall back silently to anonymous access |
| Logs expose secrets or injection text | Redact and bound all untrusted fields | Disable unsafe fields until sanitization tests pass |
| Flaky timing hides real defects | Use deterministic timing controls and tolerances agreed with Role 2 | Quarantine flaky tests and block release until their behavior is understood |

## Completion gate

Phase 5 is complete only when the full required suite, security denials, restart recovery, clean reset, isolation checks, and observability review pass with no critical open defect.
