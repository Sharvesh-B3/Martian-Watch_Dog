# Current Proof-of-Concept Inventory and Contract Gaps

**Inventory date:** 2026-11-25  
**Purpose:** Record reusable assets and required replacements before Phase 2. Nothing listed here is considered contract-complete merely because it exists.

## Repository state

| Area | Current asset | Current behavior | Contract gap |
|---|---|---|---|
| Broker | `docker-compose.yml`, `sim/broker/mosquitto.conf` | Starts one Mosquitto 2 container on `127.0.0.1:1883` | Anonymous access is enabled; no explicit internal network, health check, ACL, generated credentials, or device services |
| Devices | `sim/devices/sim_devices.py` | One process/client publishes five logical device payloads every 2 seconds | IDs/types differ from contract; CCTV replaces Decoy Twin; no strict envelope/schema; no separate services/accounts/client IDs |
| Controls | `sim/devices/sim_devices.py` | Subscribes to `campus/lab1/control/+` and mutates an in-memory state | No command IDs, expiry, approval references, acknowledgements, idempotency, backend-only ACL, or full reset |
| Attacks | `sim/attacks/red_team.py` | Interactive controller publishes three kinds of malicious telemetry | Public names/evidence do not align 1:1; import has side effects; no MQTT trigger/status contract; coordinated attack omits power evidence |
| Observer | `sim/monitor.py` | Read-only-looking process subscribes to `campus/lab1/#` and prints threshold matches | Uses anonymous access; mixes diagnostics with detector-like labels; lacks structured IDs/schema checks/redaction |
| Dependencies | Local `.venv` only | `paho-mqtt` is used by source | No committed Role 1 dependency manifest or reproducible image yet |
| Environment | Hard-coded localhost and port | All scripts assume `127.0.0.1:1883` | No `.env.example`, credential inputs, validation, or container service hostname |
| Backend | No `backend/` directory | No Role 2 implementation exists | Contract sign-off and end-to-end integration remain blocked |
| Frontend | `frontend/src/types/watchdog.ts`, `frontend/src/api/client.ts` | Defines canonical five-device UI and three attack names in mock/live adapter | Current simulator IDs/scenarios do not match it; mock audit text still names `campus/wing-a/air_quality_01` instead of the signed `campus/lab1/telemetry/air_quality_01` topic |

## Current device mapping

| Current ID | Current role | Canonical replacement | Disposition |
|---|---|---|---|
| `door_lock_01` | Door lock | `smart_lock_01` | Migrate reusable lock behavior; do not retain old ID |
| `rfid_01` | RFID scanner | `rfid_scanner_01` | Migrate reusable idle behavior; add canonical metrics |
| `aq_sensor_01` | Air sensor | `air_quality_01` | Migrate random generation; add PM2.5 and untrusted metadata |
| `meter_01` | Smart meter | `power_meter_01` | Migrate load/network generation; align normal profile |
| `cctv_01` | CCTV | `decoy_twin_01` | Do not map CCTV behavior; implement a real Decoy Twin |

## Current topic mapping

| Current topic | Current producer/consumer | Target semantic replacement |
|---|---|---|
| `campus/lab1/door_lock` | Aggregate device and attacker | `campus/lab1/telemetry/smart_lock_01` |
| `campus/lab1/rfid_scanner` | Aggregate device | `campus/lab1/telemetry/rfid_scanner_01` |
| `campus/lab1/air_quality` | Aggregate device and attacker | `campus/lab1/telemetry/air_quality_01` |
| `campus/lab1/smart_meter` | Aggregate device and attacker | `campus/lab1/telemetry/power_meter_01` |
| `campus/lab1/cctv_cam` | Aggregate device and attacker | Removed from core topology |
| `campus/lab1/control/{current_id}` | Any anonymous publisher → aggregate device | Authenticated `campus/lab1/control/{canonical_device_id}` plus acknowledgement |

## Current payload-field inventory

| Current logical device/message | Current fields | Version 1.0 disposition |
|---|---|---|
| Door lock normal | `device_id`, `status`, `last_rfid`, `timestamp`, injected `state` | Rename ID; replace free-form `status`/`state` with strict top-level status and smart-lock metrics `locked`, `door_closed`, `failed_attempts`, `last_badge_id` |
| Door lock attack | Normal fields with `status=UNLOCKED`, `last_rfid=UNAUTHORIZED_BYPASS` | Emit `locked=false`, `door_closed=false`, `failed_attempts=1`, `last_badge_id=null`, top-level `warning`, and scenario `correlation_id` |
| RFID normal | `device_id`, `event`, `badge_id`, `timestamp`, injected `state` | Rename ID; retain normalized `event`/`badge_id`; add required boolean `authorized`; move runtime state to strict top-level status |
| Air normal | `device_id`, `co2_ppm`, `temp_c`, `status`, `timestamp`, injected `state` | Rename ID; add `pm25`; move measurements under `metrics`; replace text status with strict top-level status and `metadata.note` |
| Air poisoned | Normal fields with extreme values and injection inside `status` | Split into independent PM2.5 spoof and normal-metric prompt injection; hostile text exists only in untrusted `metadata.note` |
| Meter normal | `device_id`, `power_kw`, `network_conns`, `timestamp`, injected `state` | Rename ID; map to `load_kw`, `outbound_conns`; add `voltage`; use strict top-level status |
| Meter port scan | Normal fields plus `anomaly_flag` and high `network_conns` | Remove answer-revealing `anomaly_flag` from public telemetry; express evidence through high `outbound_conns` and correlation only |
| CCTV normal/attack | `device_id`, `heartbeat`, `fps`, `timestamp`, injected `state` | Remove from core topology; no version 1.0 telemetry mapping |
| Quarantined aggregate output | `device_id`, `state`, `timestamp` only | Continue publishing the complete device-specific metrics envelope with top-level `quarantined`; do not switch to a reduced shape |
| Current control input | JSON object containing only `action` | Replace with `control.schema.json`, including IDs, target, references, issue/expiry times, actor, and acknowledgements |

All version 1.0 telemetry additionally requires `schema_version`, UUIDv4 `event_id`, nullable `correlation_id`, matching `device_type`, `zone=lab-wing-a`, RFC 3339 UTC `timestamp`, strict `metrics`, and strict `metadata`.

## Current control-action inventory

| Current action | Current effect | Version 1.0 disposition |
|---|---|---|
| `QUARANTINED` | Sets literal aggregate state | Remove as a command; `quarantined` is an observed status, not an action |
| `QUARANTINE` | Maps to aggregate `QUARANTINED` | Retain as strict `QUARANTINE` with approval references and acknowledgement |
| `DECOY` | Sets the addressed device state to `DECOY` | Replace with `ACTIVATE_DECOY` targeted only at `decoy_twin_01` |
| `RESTORE` | Maps aggregate state to `NORMAL` | Retain as strict `RESTORE` with command identity/expiry/acknowledgement |
| `NORMAL` | Directly sets aggregate state | Remove as a command; normal is an observed post-restore/reset state |
| No current equivalent | None | Add strict whole-lab `RESET` on `campus/lab1/sim/reset` |

## Current attack mapping

### Coordinated intrusion

Current behavior publishes a CCTV offline event followed by a forced door unlock. The signed contract instead requires power-meter port-scan evidence, no authorized RFID scan in the prior 5 seconds, and a smart-lock unlock approximately 1 second after the scan. CCTV is removed.

### Prompt injection

Current behavior combines implausible CO2/temperature values with prompt injection in an unconstrained `status` string. The signed contract keeps metrics normal and places the hostile string only in untrusted `metadata.note` so the guardrail can be evaluated independently.

### Lateral movement / sensor spoofing

Current behavior exposes lateral movement as a standalone menu item. The public contract has no standalone lateral-movement attack: port-scan evidence belongs to `coordinated_intrusion`. The required `spoof_sensor` scenario is a PM2.5 spike with no hostile text.

## Reusable proof-of-concept elements

- Loopback-only broker port binding is a useful isolation layer.
- Mosquitto 2 is the agreed broker family.
- Two-second telemetry cadence is retained.
- UTC timestamp generation is retained but moves into the strict envelope.
- QoS 1 is retained.
- MQTT callback API v2 usage is reusable.
- Basic smart-lock, RFID, air, and power data-generation ideas are reusable after canonical renaming and schema alignment.
- The interactive menu can inform `trigger_cli.py`, but the final CLI publishes the MQTT trigger contract instead of executing attack logic itself.
- `monitor.py` can become a read-only observer after authentication, schema validation, neutral wording, and output redaction.

## Frontend follow-up outside Role 1

Role 3's IDs, device types, statuses, normal air/power metrics, and three API attack names align with contract version 1.0. Its mock-only audit strings at `frontend/src/api/client.ts` still mention `campus/wing-a/air_quality_01`. Role 3 should update those display strings when reconciling live-mode wording; Role 1 must not change the signed MQTT namespace to match stale mock prose.

## Behavior that must not be carried forward unchanged

- Anonymous broker access.
- One MQTT client representing all devices.
- Hard-coded connection settings.
- CCTV as one of the five core devices.
- Free-form top-level device `status` strings.
- One-off malicious publications that are immediately overwritten by normal state.
- Direct unapproved control publication from the attacker tool.
- Import-time MQTT connections and interactive infinite loops in reusable attack modules.
- Controls without IDs, expiry, approval references, acknowledgements, or replay protection.
- Diagnostic monitor rules being presented as Role 2 AI detection.

## Migration safety rule

Keep `sim/devices/sim_devices.py`, `sim/attacks/red_team.py`, and the current monitor available during migration. Retire or relocate them only after their Phase 2–5 replacements pass the relevant acceptance gates; do not delete working proof-of-concept behavior merely to match the target tree.
