# Role 2 API ↔ MQTT Handoff

**Contract version:** 1.0  
**Status:** Ready for review; Role 2 owner and approval remain pending  
**Authority:** This document derives from `README.md`, `mqtt_topics.md`, and the versioned schemas. It does not introduce new fields or topics.

## Boundary rule

Role 2 is the only bridge between MQTT and Role 3. The frontend never connects to Mosquitto, receives an MQTT password, consumes private injection/ground-truth data, or decides whether a control is authorized.

## Startup and ingestion

1. Role 2 authenticates with the `backend` MQTT principal.
2. It subscribes at QoS 1, non-retained, to:
   - `campus/lab1/telemetry/+`;
   - `campus/lab1/presence/+`;
   - `campus/lab1/control_ack/+`;
   - `campus/lab1/sim/attack/status`;
   - `campus/lab1/decoy/events`.
3. It validates each payload against the matching version 1.0 schema before using it.
4. It deduplicates ordinary events for 10 minutes.
5. It rejects event timestamps over 5 seconds in the future and drops or explicitly flags telemetry over 60 seconds old.
6. Presence `session_started_at` is not disconnect time. Role 2 records trusted local receive time as `observed_at` for online/offline state.
7. Valid telemetry maps to backend `DeviceNode` state and then to Role 3 `device_update` events.

Role 2 must not subscribe to:

- `campus/lab1/sim/inject/+`;
- `campus/lab1/decoy/input/+`;
- `campus/lab1/test/ground_truth`.

The broker ACL must deny those subscriptions even if backend code requests them.

## `POST /api/sim/trigger`

### API input

Role 3 already sends JSON with one `attack_type` value:

- `spoof_sensor`
- `coordinated_intrusion`
- `prompt_injection`

### Backend action

After API validation, Role 2:

1. creates a UUIDv4 `request_id`;
2. sets RFC 3339 UTC `requested_at` and a future `expires_at`;
3. sets `requested_by=backend`;
4. validates the resulting object against `attack_trigger.schema.json`;
5. publishes it to `campus/lab1/sim/attack/trigger` with QoS 1 and `retain=false`;
6. records the request ID with the API/audit request.

The API may preserve the current frontend-compatible response fields `{ ok, triggered }`. If Role 2 exposes `request_id`, that is an additive REST decision requiring frontend type review; MQTT correlation does not depend on the browser receiving it.

Successful MQTT publication means only that the request was sent. It does not mean the scenario completed.

### Lifecycle handling

Role 2 consumes `attack_status.schema.json` from `campus/lab1/sim/attack/status` and distinguishes:

- `accepted` — valid and admitted by the controller;
- `started` — scenario execution began;
- `completed` — the bounded evidence burst was emitted;
- `rejected` — invalid/expired request or policy denial;
- `duplicate` — request ID seen in the last 10 minutes; no replay;
- `busy` — another scenario is active; no queueing;
- `failed` — execution did not complete.

Role 2 must not report a successful trigger as a successful detected/contained incident. Detection comes independently from public telemetry.

## Detection evidence

### `spoof_sensor`

- Public evidence: `air_quality_01` warning telemetry with PM2.5 = 490 and normal CO2/temperature.
- `metadata.note` is null.
- Expected category: Role 2-owned `sensor_spoofing` decision.

### `prompt_injection`

- Public evidence: `air_quality_01` warning telemetry with normal physical metrics.
- Untrusted `metadata.note` contains the hostile instruction fixture.
- Role 2 sanitizes/frames the field before reasoning and owns the incident/audit result.

### `coordinated_intrusion`

- Public evidence begins with abnormal `power_meter_01.outbound_conns`.
- No authorized `rfid_scanner_01` badge scan exists in the 5 seconds before unlock.
- `smart_lock_01` then reports unlocked/door open with the same scenario correlation ID.
- Role 2 evaluates this evidence inside its wider 60-second rolling window.

Role 2 must not use private injection or observer ground truth to satisfy these rules.

## HITL approval → controls

When `POST /api/approvals/{id}/decide` records an approved high-risk action, Role 2 looks up the incident, approval, target, and scenario correlation. It then publishes schema-valid controls with a 30-second expiry.

### Quarantine

- Topic: `campus/lab1/control/smart_lock_01`.
- Action: `QUARANTINE`.
- Required: UUIDv4 command/correlation IDs, non-null incident/approval IDs, issue/expiry times, `actor=backend`.

### Decoy activation

- Topic: `campus/lab1/control/decoy_twin_01`.
- Action: `ACTIVATE_DECOY`.
- Uses the same incident, approval, and scenario correlation.

Publishing a command does not prove it was applied. Role 2 consumes each device's `control_ack` messages:

- `accepted` is intermediate;
- `applied` is a completed local state transition;
- `rejected`, `failed`, or `duplicate` must be represented truthfully in API/audit state.

Role 2 retains command IDs for 24-hour replay protection and persists the human decision separately from device execution facts.

## Decoy event handling

After valid activation, Role 2 may observe:

1. a Decoy `activated` event;
2. a controller-generated post-containment probe sent privately to the Decoy Twin;
3. a public safe Decoy `capture` event with incremented counters and a payload hash.

Role 2 never receives raw Decoy input. It may claim capture only after a schema-valid `capture` event, not from activation alone. All user-facing language must say explicit **simulated routing**, not transparent broker/network rerouting.

## Full reset

To reset the lab, Role 2 publishes `control.schema.json` to `campus/lab1/sim/reset` with:

- `action=RESET`;
- `target_id=lab1`;
- a fresh `command_id` and `correlation_id`;
- a 30-second expiry;
- `actor=backend`.

The controller uses the reset `command_id` as the reset lifecycle `request_id` and reports `attack_type=reset`. Role 2 waits for:

- one acknowledgement from each of the five canonical devices; and
- controller `completed` reset status.

Only then may the backend report a clean baseline. A partial timeout is a failed/partial reset, not success.

## Backend-to-frontend mapping

| MQTT field/fact | Role 2 responsibility | Role 3 output |
|---|---|---|
| Canonical device ID/type | Preserve exactly | `DeviceNode.id` / `type` |
| Machine zone `lab-wing-a` | Map explicitly | Display label such as `Lab Wing A` |
| Telemetry status/metrics/time | Validate and normalize | `device_update` |
| Detected evidence | Correlate and explain | `new_incident` |
| Required high-risk action | Create HITL request | `new_approval` |
| Operator decision | Persist before control | `audit_entry` and approval update |
| Control acknowledgement | Persist actual execution result | `device_update` / `audit_entry` |
| Safe Decoy event | Persist activation/capture fact | `device_update` / `audit_entry` |

## Required Role 2 review outcome

The Role 2 owner must either:

1. implement fixture-based compatibility tests and approve version 1.0 in `signoff.md`; or
2. record a concrete change request against a topic, schema field, timing rule, ACL permission, or mapping.

Silence, successful MQTT connection, or partial backend implementation is not sign-off.
