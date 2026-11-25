# Phase 2 — Isolated MQTT Lab and Five-Device Topology

**Status:** Complete — implementation, Docker/live verification, restart recovery, ACLs, host access, and network isolation passed.
**Scope:** Broker, Docker Compose topology, credentials/ACLs, shared simulator runtime, and normal telemetry.

## Provisional authorization and current blocker

- The Role 1 owner authorized implementation against contract version 1.0 while Phase 1 awaits Role 2 assignment/sign-off.
- This exception permits Role 1 code and local tests only; it does not close Phase 1 or prove Role 2 integration.
- Docker Engine 29.1.3 and Compose 2.40.3 are installed in WSL 2 and the lab is running.
- Image builds, credential hashing/rotation, broker startup, live MQTT, ACL denials, container health, restart recovery, host access, and network isolation are verified.
- No Phase 3 attack behavior or Phase 4 control behavior is included in this phase.

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

- [x] Configure Mosquitto to reject anonymous clients.
- [x] Load the tracked ACL policy and an untracked generated password file.
- [x] Bind any host-published listener only as permitted by the Phase 1 isolation contract.
- [x] Add a broker health check that proves authenticated MQTT readiness rather than only process existence.
- [x] Configure useful local logs without exposing passwords or tokens.
- [x] Verify clean shutdown and restart behavior.

### 2. Build the isolated Compose network

- [x] Define an explicit internal lab network instead of relying on the default Compose network.
- [x] Attach only approved lab services to that network.
- [x] Confirm how a host-run or later containerized backend reaches the broker without opening unintended external access.
- [x] Add service health dependencies so devices do not race broker startup.
- [x] Verify that no simulator service requires Internet access at runtime.

### 3. Establish safe configuration and credentials

- [x] Add `sim/.env.example` entries for non-secret broker and simulator settings.
- [x] Document local generation of simulator, attacker/controller, backend, and observer credentials.
- [x] Ensure real environment files and generated password data are ignored by Git.
- [x] Validate the Phase 1 ACL matrix with positive and negative connection tests.
- [x] Fail clearly when required configuration or credentials are missing.

### 4. Create the shared simulator runtime

- [x] Centralize environment parsing, MQTT connection setup, schema validation, timestamp/event ID creation, structured logging, and retry/backoff.
- [x] Keep device-specific physics and state transitions outside the MQTT transport layer.
- [x] Give every service a unique MQTT client ID and last-will/offline signal as agreed in Phase 1.
- [x] Support graceful termination without leaving misleading retained state.
- [x] Add deterministic random seeding for repeatable tests while retaining a configurable realistic mode.

### 5. Implement the five normal device services

- [x] Implement `smart_lock_01` normal locked/closed behavior and valid access-related metrics.
- [x] Implement the approved idle-only Phase 2 baseline for `rfid_scanner_01`; valid scans remain explicit future behavior so attack correlation is deterministic.
- [x] Implement `air_quality_01` slowly changing physically plausible air metrics and an explicitly untrusted metadata field.
- [x] Implement `power_meter_01` physically plausible load/network metrics suitable for later anomaly injection.
- [x] Implement `decoy_twin_01` in standby with zero active traps/captures until an approved Phase 4 command.
- [x] Validate every outbound message against the Phase 1 schema before publication in development/test mode.

### 6. Verify normal operation

- [x] Start from a clean environment using only repository documentation and generated local secrets.
- [x] Observe all five canonical device IDs on only their authorized topics.
- [x] Confirm timestamps, event IDs, schema versions, status values, and metric types.
- [x] Confirm telemetry cadence and physical ranges match the signed contract.
- [x] Restart the broker and individual devices and verify bounded reconnection with no duplicate-client conflict.
- [x] Confirm the Decoy Twin remains inactive during normal operation.

## Acceptance criteria

- [x] All six required services become healthy without manual race-condition workarounds.
- [x] Each device is configured as a distinct service, process, MQTT client ID, account, and canonical device ID.
- [x] All observed normal telemetry passes the Phase 1 schemas and agreed physical bounds.
- [x] Unauthorized anonymous connections fail.
- [x] Each account can perform only the topic operations granted by the ACL matrix.
- [x] A clean broker/device restart recovers automatically within the agreed bound.
- [x] The lab has no undocumented external-network dependency.
- [x] No plaintext production-like password or generated password database is tracked.

## Dependencies and hand-offs

- **Requires:** contract version 1.0 artifacts; formal Role 2 signature is still pending under the explicitly authorized provisional exception.
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

## Current non-Docker verification evidence

- 10 Draft 2020-12 schemas and 41 valid/invalid fixtures pass.
- 36 simulator/structure/security-policy/state-transition tests pass.
- All Python sources parse with Python 3.13.7; the legacy BOM in `sim/monitor.py` is handled without modifying that proof-of-concept file.
- `docker-compose.yml` parses with pinned local PyYAML 6.0.4 and declares exactly the broker plus five device services on an internal network.
- Compose structure tests confirm loopback-only port declaration, fixed unique client IDs, broker health dependency, and per-service credential selection.
- Credential tests confirm eight unique environment-safe tokens, paired atomic installation, and use of `mosquitto_passwd -U` without passwords in process arguments.
- `sim/verify_lab.py` is prepared to collect two live samples per device, validate cadence/physics/contracts, prove anonymous denial, and test allowed/denied subscription ACLs without publishing operational messages.
- Git ignore checks cover `sim/.env` and `sim/broker/generated/passwd`.
- Official Mosquitto documentation confirms exit code 27 represents a clean `mosquitto_sub -W` timeout used by the authenticated health check.
- Docker Hub registry lookup confirms both selected image tags currently exist; observed manifest digests are recorded in `sim/README.md`, but local pull/platform execution remains unverified.

## Completed Docker/live verification

- WSL Docker Engine 29.1.3 and Compose 2.40.3 installed and running.
- Selected Python/Mosquitto images pulled; simulator and backend images built successfully.
- Eight credentials generated and successfully rotated without plaintext disclosure.
- All services reached healthy state; MQTT uses container port 1883 and host `127.0.0.1:1884`.
- Full read/write ACL verifier passed, including denied-read delivery filtering.
- Independent power-meter and broker restarts recovered automatically.
- All five devices plus the attack controller were unable to reach external IPs.
- Backend reached MQTT through the internal network and exposed HTTP only on `127.0.0.1:8000`.
