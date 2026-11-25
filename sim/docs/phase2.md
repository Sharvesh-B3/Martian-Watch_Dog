# Phase 2 — Isolated MQTT Lab and Five-Device Topology

**Status:** Planned — starts only after the Phase 1 contract gate.  
**Scope:** Broker, Docker Compose topology, credentials/ACLs, shared simulator runtime, and normal telemetry.

## Goal

Build a reproducible isolated lab in which Mosquitto and each of the five canonical devices run as separate healthy Compose services, authenticate with least-privilege credentials, and publish contract-valid normal telemetry.

## Required topology

- Mosquitto broker service.
- `smart_lock_01` service.
- `rfid_scanner_01` service.
- `air_quality_01` service.
- `power_meter_01` service.
- `decoy_twin_01` service, initially in the contract-defined standby state.

The attack controller and observer are added to the Compose workflow in later phases. CCTV is not part of the core topology.

## Deliverables

- Updated `docker-compose.yml` with an explicit internal lab network and one service per device.
- `sim/Dockerfile` and a pinned Role 1 dependency manifest.
- Environment-driven shared MQTT configuration and reconnect behavior.
- Hardened `sim/broker/mosquitto.conf`, tracked ACL rules, and a documented process for generating untracked credentials.
- Separate device entry points under `sim/devices/`, backed by reusable code under `sim/common/`.
- Contract-valid normal telemetry from all five canonical device IDs.

## Execution checklist

### 1. Build the broker service

- [ ] Configure Mosquitto to reject anonymous clients.
- [ ] Load the tracked ACL policy and an untracked generated password file.
- [ ] Bind any host-published listener only as permitted by the Phase 1 isolation contract.
- [ ] Add a broker health check that proves authenticated MQTT readiness rather than only process existence.
- [ ] Configure useful local logs without exposing passwords or tokens.
- [ ] Verify clean shutdown and restart behavior.

### 2. Build the isolated Compose network

- [ ] Define an explicit internal lab network instead of relying on the default Compose network.
- [ ] Attach only approved lab services to that network.
- [ ] Confirm how a host-run or later containerized backend reaches the broker without opening unintended external access.
- [ ] Add service health dependencies so devices do not race broker startup.
- [ ] Verify that no simulator service requires Internet access at runtime.

### 3. Establish safe configuration and credentials

- [ ] Add `.env.example` entries for non-secret broker and simulator settings.
- [ ] Document local generation of simulator, attacker/controller, backend, and observer credentials.
- [ ] Ensure real environment files and generated password data are ignored by Git.
- [ ] Validate the Phase 1 ACL matrix with positive and negative connection tests.
- [ ] Fail clearly when required configuration or credentials are missing.

### 4. Create the shared simulator runtime

- [ ] Centralize environment parsing, MQTT connection setup, schema validation, timestamp/event ID creation, structured logging, and retry/backoff.
- [ ] Keep device-specific physics and state transitions outside the MQTT transport layer.
- [ ] Give every service a unique MQTT client ID and last-will/offline signal as agreed in Phase 1.
- [ ] Support graceful termination without leaving misleading retained state.
- [ ] Add deterministic random seeding for repeatable tests while retaining a configurable realistic mode.

### 5. Implement the five normal device services

- [ ] Implement `smart_lock_01` normal locked/closed behavior and valid access-related metrics.
- [ ] Implement `rfid_scanner_01` idle and valid-badge behavior without manufacturing a badge event for every lock message.
- [ ] Implement `air_quality_01` slowly changing physically plausible air metrics and an explicitly untrusted metadata field.
- [ ] Implement `power_meter_01` physically plausible load/network metrics suitable for later anomaly injection.
- [ ] Implement `decoy_twin_01` in standby with zero active traps/captures until an approved Phase 4 command.
- [ ] Validate every outbound message against the Phase 1 schema before publication in development/test mode.

### 6. Verify normal operation

- [ ] Start from a clean environment using only repository documentation and generated local secrets.
- [ ] Observe all five canonical device IDs on only their authorized topics.
- [ ] Confirm timestamps, event IDs, schema versions, status values, and metric types.
- [ ] Confirm telemetry cadence and physical ranges match the signed contract.
- [ ] Restart the broker and individual devices and verify bounded reconnection with no duplicate-client conflict.
- [ ] Confirm the Decoy Twin remains inactive during normal operation.

## Acceptance criteria

- [ ] All six required services become healthy without manual race-condition workarounds.
- [ ] Each device uses a distinct service, process, MQTT client ID, and canonical device ID.
- [ ] All observed normal telemetry passes the Phase 1 schemas and agreed physical bounds.
- [ ] Unauthorized anonymous connections fail.
- [ ] Each account can perform only the topic operations granted by the ACL matrix.
- [ ] A clean broker/device restart recovers automatically within the agreed bound.
- [ ] The lab has no undocumented external-network dependency.
- [ ] No plaintext production-like password or generated password database is tracked.

## Dependencies and hand-offs

- **Requires:** completed and signed Phase 1 contracts.
- **Input from Role 2:** backend connectivity mode and backend MQTT identity requirements.
- **Output to Phase 3:** stable broker, normal telemetry producers, schema validator, and attacker/controller account.
- **Output to Role 2:** broker connection guide, CA/auth details if applicable, topic map, and validated normal fixtures.

## Risks and rollback

| Risk | Mitigation | Safe rollback |
|---|---|---|
| Internal networking blocks the agreed backend path | Test the agreed host/container path before hardening is signed off | Return to the last working restricted network configuration; do not enable broad exposure |
| Device services duplicate shared logic | Build a shared runtime with thin device entry points | Keep the current aggregate simulator available until all five replacements pass smoke tests |
| ACLs prevent legitimate telemetry | Validate each permission from the matrix independently | Restore the last reviewed ACL file, not `allow_anonymous true` |
| Random values cause flaky tests | Use a contract-defined deterministic seed in tests | Switch tests to fixed fixtures while correcting the physics model |
| Secrets are accidentally staged | Ignore generated files and add a secret check | Revoke/regenerate exposed local credentials before continuing |

## Completion gate

Phase 2 is complete only when the isolated authenticated lab starts cleanly, all five services publish valid normal telemetry, ACL tests pass, and Role 2 can connect through the agreed path.
