# Aegis Watchdog — Role 1 Simulation Redesign Plan

Scope: `sim/` plus the minimum backend integration needed to preserve the
existing REST/WebSocket/frontend contract.

Agreed decisions:

- One command starts Mosquitto and independent simulator processes.
- Six nodes run independently: lock, RFID, air quality, power meter, CCTV and
  Decoy Twin.
- Telemetry is deterministic by default, with optional seeded noise.
- Attack evidence remains active until containment, restore or reset.
- Decoy Twin visibly captures synthetic attacker activity.
- Approved containment performs a real loopback L4 route switch from the real
  MQTT broker to a separate decoy broker and exposes independent byte/session
  counters.
- Existing `campus/lab1` topics and Role 1 device IDs remain compatible.
- Frontend REST payloads, canonical IDs and WebSocket event types do not change.

---

## Target architecture

```text
python -m sim.run_lab
        |
        +-- starts Mosquitto
        +-- smart_lock process
        +-- rfid_scanner process
        +-- air_quality process
        +-- power_meter process
        +-- cctv_camera process
        +-- decoy_twin process
        +-- attack_controller process
        +-- optional prefixed monitor
```

```text
Dashboard/API --> Red Team trigger --> Attack Controller
                                         |
                                         +--> device attack commands
                                                   |
Devices --> realistic MQTT telemetry --> Backend correlation/Gemini/HITL
                                                   |
Backend --> approved controls --> physical lock + separate Decoy Twin
```

## Target structure

```text
sim/
|-- __init__.py
|-- run_lab.py
|-- monitor.py
|-- common/
|   |-- __init__.py
|   |-- mqtt_device.py
|   |-- protocol.py
|   `-- settings.py
|-- devices/
|   |-- __init__.py
|   |-- smart_lock.py
|   |-- rfid_scanner.py
|   |-- air_quality.py
|   |-- power_meter.py
|   |-- cctv_camera.py
|   `-- decoy_twin.py
|-- attacks/
|   |-- __init__.py
|   |-- controller.py
|   |-- scenarios.py
|   |-- spoof_sensor.py
|   |-- coordinated_intrusion.py
|   |-- prompt_injection.py
|   `-- red_team.py
`-- tests/
    |-- test_devices.py
    |-- test_scenarios.py
    |-- test_controls.py
    `-- test_decoy.py
```

The existing `sim/devices/sim_devices.py` and `sim/attacks/red_team.py` remain
as compatibility wrappers until all runbooks use the new launcher/modules.

---

## Phase 0 — Contract and security checkpoint

**Goal:** improve Role 1 without breaking the integrated backend/frontend.

- [x] Preserve existing telemetry topics and sim IDs.
- [x] Preserve canonical mapping in `backend/app/mqtt_client.py`.
- [x] Preserve REST request shapes and four WebSocket event types.
- [x] Keep `.env` and `frontend/.env.local` local-only.
- [x] Do not require frontend component changes.

## Phase 1 — Shared MQTT device runtime

**Goal:** every node gets reliable lifecycle, telemetry and control behavior.

- [x] Add `BaseMqttDevice` with reconnect/backoff, QoS 1, unique client ID,
  graceful shutdown, retained presence/LWT and prefixed logs.
- [x] Add UTC timestamp, monotonic `sequence`, `run_id`, optional
  `scenario_id`, and state to every telemetry frame.
- [x] Add seeded random generator and configurable noise.
- [x] Subscribe each device to `campus/lab1/control/{device_id}` and
  `campus/lab1/sim/attack/{device_id}`.
- [x] Keep metrics present while a node is quarantined rather than replacing
  telemetry with a minimal state-only payload.

## Phase 2 — Device-specific state machines

**Goal:** synthetic telemetry behaves like distinct real devices.

- [x] Smart lock: authorized unlock/relock, rejected scans, tamper, forced
  unlock, quarantine and restore.
- [x] RFID: idle, deterministic accepted/rejected scans, badge and scan-rate
  metrics.
- [x] Air quality: smooth CO2/temperature/PM2.5 drift, spoof state and prompt
  injection state.
- [x] Power meter: smooth load/voltage/network baseline and persistent port-scan
  state.
- [x] CCTV: independent heartbeat/FPS and persistent tamper/offline state.
- [x] Decoy Twin: dormant/active state, attacker subscription, capture counter
  and sanitized capture timeline.

## Phase 3 — Deterministic Red Team scenarios

**Goal:** CLI and API-triggered attacks use the same scenario definitions.

- [x] Sensor spoofing changes only physical readings.
- [x] Prompt injection uses realistic readings plus malicious untrusted
  metadata.
- [x] Coordinated intrusion emits CCTV loss, unauthorized door unlock, missing
  RFID authorization and meter port scan under one `scenario_id`.
- [x] Attack modules are import-safe and expose callable functions plus CLI
  entry points.
- [x] Attack controller holds scenarios until a newer same-type scenario or
  explicit `RESTORE`/`RESET`; containment keeps attacker probes flowing into
  the Decoy Twin.
- [x] Add a high-level MQTT trigger topic for backend and CLI parity.

## Phase 4 — Visible Decoy Twin containment

**Goal:** approved deception is observable, not just a state label.

- [x] `QUARANTINE` targets `door_lock_01`; `DECOY` targets
  `decoy_twin_01`.
- [x] Active attacks publish synthetic probes to an attacker session topic.
- [x] Active Decoy Twin captures those probes, increments
  `captured_payloads`, and records source/session/command plus a safe hash.
- [x] Publish Decoy Twin metrics through the existing `device_update` contract.
- [x] Restore/reset returns the twin to dormant state.

## Phase 5 — One-command launcher

**Goal:** a presenter starts and stops the whole lab reliably.

- [x] `python -m sim.run_lab --seed 42` validates Docker, starts Mosquitto,
  waits for broker readiness and launches all child processes.
- [x] Add `--noise`, `--no-noise`, `--keep-broker`, `--log-level`; the Red Team
  panel provides a deterministic global reset command.
- [x] Prefix child logs with component names.
- [x] Detect failed child processes.
- [x] Ctrl+C/SIGTERM terminates children and stops the broker started by the launcher.

## Phase 6 — Backend synchronization

**Goal:** richer Role 1 messages remain safe and produce one incident per
scenario.

- [x] Ignore simulator command, presence and attacker-control topics as raw
  telemetry.
- [x] Accept optional run/scenario/sequence metadata.
- [x] Deduplicate held telemetry by scenario evidence while allowing a new
  attack within the 60-second window.
- [x] Keep raw MQTT and `/api/sim/trigger` behavior equivalent.
- [x] Keep frontend schemas and event envelopes unchanged.

## Phase 7 — Verification and demo acceptance

**Goal:** deterministic, repeatable, judge-ready operation.

- [x] Unit tests cover device transitions and seeded telemetry.
- [x] Scenario tests cover ordering, IDs and attack separation.
- [x] Control tests cover quarantine, restore and reset.
- [x] Decoy tests confirm visible capture and counter increments.
- [x] One command starts every node and broker.
- [x] One active scenario produces one backend incident despite repeated held
  telemetry.
- [x] CLI and API attacks produce equivalent incidents.
- [x] Approval leaves the lock quarantined and activates the separate Decoy
  Twin.
- [x] Decoy captures at least three synthetic probes during the demo.
- [x] The same attacker endpoint reports `REAL_LAB` before approval and
  `DECOY_LAB` after a forced TCP reconnect.
- [x] Gateway `real_bytes` stops and `decoy_bytes` increases after approval.
- [x] Restore switches the gateway back to the real broker.
- [x] Ctrl+C leaves no simulator process or broker started by the launcher.

---

## Compatibility contract

Existing telemetry topics remain:

```text
campus/lab1/door_lock
campus/lab1/rfid_scanner
campus/lab1/air_quality
campus/lab1/smart_meter
campus/lab1/cctv_cam
campus/lab1/decoy_twin
campus/lab1/control/{device_id}
```

New internal simulator topics are namespaced below `campus/lab1/sim/`,
`campus/lab1/presence/`, `campus/lab1/redteam/` and
`campus/lab1/attacker/`. The backend must ignore internal command topics while
continuing to process normal telemetry.

Frontend-facing contracts remain unchanged:

```text
device_update
new_incident
new_approval
audit_entry
```
