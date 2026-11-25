# MQTT Topics, Delivery Policy, and ACL Matrix

**Root namespace:** `campus/lab1`  
**Default delivery:** QoS 1  
**Retained messages:** Disabled on every topic, including presence  
**Transport:** Plain MQTT inside the isolated local lab; TLS is out of scope for MVP  
**Authentication:** Required; anonymous access is denied

## Fixed principals

Passwords are generated locally and never committed. These usernames are fixed contract identifiers:

- `device_smart_lock_01`
- `device_rfid_scanner_01`
- `device_air_quality_01`
- `device_power_meter_01`
- `device_decoy_twin_01`
- `attack_controller`
- `backend`
- `observer`

Credential creation will use a local setup script wrapping `mosquitto_passwd`. It writes the broker database to `sim/broker/generated/passwd` and client variables to `sim/.env`. Both paths are explicitly ignored by Git; only non-secret variable names may appear in a future example file.

## Credential lifecycle

- Role 1 owns generation, local storage, emergency rotation, and revocation for all MQTT accounts.
- Every password is derived from at least 32 bytes produced by a cryptographically secure random generator and encoded in an environment-safe form.
- The setup script must not print passwords to normal logs or command history beyond what is required to write `sim/.env` and the Mosquitto password database.
- Rotation is deliberately all-or-nothing for the MVP. Stop the lab, generate all eight new account passwords and a replacement password database, atomically replace both local outputs, restart all services, and rerun positive/negative ACL smoke tests.
- Partial output or a failed generation run must not replace the last complete working credential set.
- A suspected leak triggers immediate full rotation. Previously generated files are overwritten locally and never added to Git.
- The backend password is handed to Role 2 only through the local ignored `sim/.env`/Compose workflow; Role 3 receives no MQTT credential.

## Topic catalog

| Topic | Schema | Authorized publisher | Authorized subscribers | Purpose |
|---|---|---|---|---|
| `campus/lab1/telemetry/{device_id}` | `telemetry.schema.json` | Matching device account only | `backend`, `observer` | Public device telemetry |
| `campus/lab1/presence/{device_id}` | `presence.schema.json` | Matching device account only | `backend`, `observer` | Online fact and offline Last Will |
| `campus/lab1/control/{device_id}` | `control.schema.json` | `backend` | Matching device account, `observer` | Approved per-device action |
| `campus/lab1/control_ack/{device_id}` | `control_ack.schema.json` | Matching device account only | `backend`, `observer` | Per-device command outcome |
| `campus/lab1/sim/attack/trigger` | `attack_trigger.schema.json` | `backend` | `attack_controller`, `observer` | Start one canonical scenario |
| `campus/lab1/sim/attack/status` | `attack_status.schema.json` | `attack_controller` | `backend`, `observer` | Trigger and reset lifecycle |
| `campus/lab1/sim/inject/{device_id}` | `injection.schema.json` | `attack_controller` | Matching device account, `observer` | Private scenario instruction; forbidden to backend |
| `campus/lab1/sim/reset` | `control.schema.json` | `backend` | All five device accounts, `attack_controller`, `observer` | Idempotent whole-lab reset |
| `campus/lab1/decoy/input/{target_device_id}` | `decoy_input.schema.json` | `attack_controller` | `device_decoy_twin_01`, `observer` | Private explicitly redirected hostile input; forbidden to backend |
| `campus/lab1/decoy/events` | `decoy_event.schema.json` | `device_decoy_twin_01` | `backend`, `attack_controller`, `observer` | Safe Decoy activation/capture/restore facts |
| `campus/lab1/test/ground_truth` | `ground_truth.schema.json` | `attack_controller` | `observer` only | Test expected evidence; forbidden to backend and Role 3 |

`{device_id}` and `{target_device_id}` are one of the five canonical IDs. Injection targets are limited by schema to `smart_lock_01`, `air_quality_01`, and `power_meter_01` for version 1.0 scenarios.

## Per-principal ACL requirements

### Device accounts

Every device account may:

- publish only its exact telemetry, presence, and acknowledgement topic;
- subscribe only to its exact control topic and `campus/lab1/sim/reset`;
- connect with only its unique MQTT client ID policy defined in Phase 2.

Scenario-target devices additionally subscribe to only their own injection topic:

- `device_smart_lock_01` → `campus/lab1/sim/inject/smart_lock_01`;
- `device_air_quality_01` → `campus/lab1/sim/inject/air_quality_01`;
- `device_power_meter_01` → `campus/lab1/sim/inject/power_meter_01`.

`device_decoy_twin_01` additionally:

- subscribes to `campus/lab1/decoy/input/+`;
- publishes `campus/lab1/decoy/events`.

No device account may publish controls, scenario triggers/status, injections, Decoy input, or ground truth.

### Attack controller

`attack_controller` may:

- subscribe to `campus/lab1/sim/attack/trigger`;
- subscribe to `campus/lab1/sim/reset`;
- subscribe to `campus/lab1/decoy/events` to observe activation and establish explicit simulated routing;
- publish `campus/lab1/sim/attack/status`;
- publish only the three allowed `campus/lab1/sim/inject/{device_id}` targets;
- publish `campus/lab1/decoy/input/{target_device_id}`;
- publish `campus/lab1/test/ground_truth`.

It must not publish controls, control acknowledgements, public device telemetry/presence, or Decoy events.

### Backend

`backend` may:

- subscribe to `campus/lab1/telemetry/+`;
- subscribe to `campus/lab1/presence/+`;
- subscribe to `campus/lab1/control_ack/+`;
- subscribe to `campus/lab1/sim/attack/status`;
- subscribe to `campus/lab1/decoy/events`;
- publish `campus/lab1/sim/attack/trigger`;
- publish `campus/lab1/control/+`;
- publish `campus/lab1/sim/reset`.

It must not subscribe to injection, Decoy input, or ground-truth topics and must not publish telemetry, presence, acknowledgements, scenario status, Decoy input/events, or ground truth.

### Observer

`observer` has read-only access to `campus/lab1/#` for local diagnostics and contract testing. It has no publish permission. Observer verdicts must never feed Role 2 detection or Role 3 data.

## Message and replay rules

- Publishers set QoS 1 and `retain=false` explicitly.
- Consumers deduplicate by `event_id`, `request_id`, or `command_id` as appropriate.
- Event and request replay cache: 10 minutes.
- Command replay cache: 24 hours.
- Offline Last Will payloads use `presence.schema.json`, QoS 1, and `retain=false`. Their `session_started_at` is fixed when the session begins; Role 2 records trusted receive time as `observed_at`.
- A timestamp more than 5 seconds in the future is invalid.
- Telemetry older than 60 seconds is stale and cannot update current state.
- Triggers and controls received after `expires_at` are rejected.
- MQTT redelivery does not authorize repeated state changes.

## Reset behavior

The backend publishes one `control.schema.json` message to `campus/lab1/sim/reset` with:

- `target_id=lab1`;
- `action=RESET`;
- a unique `command_id` and `correlation_id`;
- `incident_id=null` and `approval_id=null` unless a backend policy supplies references;
- a 30-second expiry.

Each device publishes accepted/applied or failure acknowledgements on its own control acknowledgement topic using the same `command_id`. The controller clears active/busy/routing state and publishes attack status with `attack_type=reset`.

## Denial tests required before Phase 2 completion

- Anonymous connect is denied.
- Every device is denied from every other device's topics.
- The controller is denied from controls and public telemetry.
- The backend is denied from injections, Decoy input, and ground truth.
- The observer is denied all publication.
- A mismatched client/account combination follows the Phase 2 client-ID policy and cannot silently replace a valid device session.
