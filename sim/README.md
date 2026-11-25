# Role 1 Lab Operations

**Status:** Compressed Phases A–C implemented and verified against contract version 1.0.  
**Runtime:** Docker Engine 29.1.3 and Compose 2.40.3 in WSL 2 Ubuntu; all integrated services are healthy.

## Phase 2 scope

This phase provides:

- authenticated Mosquitto configuration and least-privilege ACLs;
- one Compose service, process, account, and fixed MQTT client ID per canonical device;
- strict normal telemetry every 2 seconds;
- online/offline presence with a Last Will;
- deterministic normal physics by default;
- a standby Decoy Twin;
- local credential generation and all-account rotation;
- container health definitions.

The integrated lab also includes the MQTT attack controller, all three scenarios, validated controls/acknowledgements, quarantine, Decoy activation/capture, full reset, and the FastAPI/HITL backend.

The legacy proof-of-concept files `devices/sim_devices.py`, `attacks/red_team.py`, and `monitor.py` are retained for migration evidence but are not Compose services. Their anonymous connections are expected to fail against the hardened broker. Use the five canonical modules and the authenticated verifier instead.

## Fixed service identities

| Service | MQTT client ID | MQTT account | Default seed |
|---|---|---|---:|
| `smart_lock_01` | `watchdog-smart-lock-01` | `device_smart_lock_01` | 101 |
| `rfid_scanner_01` | `watchdog-rfid-scanner-01` | `device_rfid_scanner_01` | 102 |
| `air_quality_01` | `watchdog-air-quality-01` | `device_air_quality_01` | 103 |
| `power_meter_01` | `watchdog-power-meter-01` | `device_power_meter_01` | 104 |
| `decoy_twin_01` | `watchdog-decoy-twin-01` | `device_decoy_twin_01` | 105 |

## Prerequisites

- Python 3.13 for local validation.
- WSL 2 Ubuntu with Docker Engine and Compose v2 (`docker` is available inside WSL, not the current Windows PATH).
- The lab stopped before rotating an existing credential set.

The shared simulator image is based on `python:3.13.7-slim-bookworm`. Mosquitto uses `eclipse-mosquitto:2` (resolved to Mosquitto 2.1.4 during verification).

Registry lookup on 2026-11-25 confirmed both tags exist:

- `python:3.13.7-slim-bookworm` multi-platform manifest: `sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d`.
- `eclipse-mosquitto:2` multi-platform manifest observed at: `sha256:fa12172a051310efe5bcb7a6a11b77bd5faacb82cbacd7742aa758bf024fd8e4`.

Both images were pulled and executed successfully. The Mosquitto major tag can still move and should be digest-pinned before a non-demo deployment.

## Generate credentials

From the repository root:

```powershell
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/ADMIN/Documents/Martian-Watch_Dog && python3 sim/setup_credentials.py'
```

The script:

1. generates eight independent passwords from at least 32 random bytes each;
2. writes client variables to ignored `sim/.env`;
3. uses `mosquitto_passwd -U` in an official one-off Mosquitto container, with the image's compatible default SHA-512 PBKDF2 policy, to hash an ignored staged password file;
4. atomically installs `sim/broker/generated/passwd` and `sim/.env`;
5. prints paths and account count, never passwords.

If credentials already exist, the script refuses to overwrite them. To rotate every account after stopping the lab:

```powershell
python sim/setup_credentials.py --rotate
```

Partial/per-account rotation is intentionally unsupported in the MVP.

## Validate and start the lab

Every Compose command must explicitly load the selected secret file so interpolation can pass only each service's own credential:

```powershell
docker compose --env-file sim/.env config
docker compose --env-file sim/.env up --build --detach
docker compose --env-file sim/.env ps
```

Expected services:

- `mosquitto`
- `smart_lock_01`
- `rfid_scanner_01`
- `air_quality_01`
- `power_meter_01`
- `decoy_twin_01`

Mosquitto is published only at `127.0.0.1:1884`; MQTT remains port `1883` inside Compose. Host port 1884 deliberately avoids this machine's auto-start native Mosquitto service on 1883. All six services join `watchdog-lab`, which is declared `internal: true`. Only the broker also joins `watchdog-host-access`, a dedicated ingress bridge required because this Docker engine does not publish host ports from an internal-only network. Device services remain internal-only and have no external route.

At startup, the broker entrypoint copies the read-only host ACL/password/config inputs into a private runtime directory, assigns them to the `mosquitto` user, and applies mode `0700`. This avoids current/future Mosquitto rejection of permissive bind-mount ownership and modes.

## Observe contract-valid telemetry

The broker container receives only observer credentials for its authenticated health check. The same read-only identity can be used interactively without copying its password into a command:

```powershell
docker compose --env-file sim/.env exec mosquitto sh -c 'mosquitto_sub -h 127.0.0.1 -p 1883 -u "$MQTT_OBSERVER_USERNAME" -P "$MQTT_OBSERVER_PASSWORD" -t "campus/lab1/telemetry/+" -q 1 -v'
```

Stop the subscription with Ctrl+C. Normal output should contain all five canonical IDs and strict version 1.0 envelopes. `rfid_scanner_01` remains idle in Phase 2, and `decoy_twin_01` remains `decoy`/`standby` with zero captures.

## Run the safe live verifier

With all six services healthy, run from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv\Scripts\python.exe -m sim.verify_lab
```

The verifier waits up to 20 seconds for at least two samples from every device. It checks:

- anonymous authentication is denied;
- observer authentication succeeds;
- all five topics, IDs, envelopes, event IDs, non-retained flags, normal states, metric bounds, and approximately two-second cadence;
- allowed subscriptions for all five devices, attack controller, backend, and observer.

The default verifier is deliberately read-only. It does not publish operational controls, triggers, injections, Decoy input, malformed payloads, or ground truth. Mosquitto can accept a denied subscription at SUBACK time and enforce it during delivery, so negative read checks run with the explicit Phase 2 write-marker mode below.

While the Compose project still contains only the six Phase 2 services, run the isolated write-ACL markers as well:

```powershell
.venv\Scripts\python.exe -m sim.verify_lab --include-write-acl
```

Do not use `--include-write-acl` after Phase 3/4 consumers are added: its permitted probes intentionally target representative operational channels to prove broker write authorization.

## Deterministic and random modes

Compose defaults to fixed per-device seeds. For a nondeterministic local run, set one or more host variables to the literal `random` before `docker compose up`. Example in PowerShell:

```powershell
$env:AIR_QUALITY_SIM_SEED = 'random'
$env:POWER_METER_SIM_SEED = 'random'
docker compose --env-file sim/.env up --build --detach
```

Do not use nondeterministic mode for contract or demo regression tests.

## Logs, restart, and shutdown

```powershell
docker compose --env-file sim/.env logs --follow
docker compose --env-file sim/.env restart power_meter_01
docker compose --env-file sim/.env down
```

Devices publish an explicit graceful offline presence event during orderly shutdown. Mosquitto publishes their configured offline Last Will after an ungraceful disconnect.

## Non-Docker verification

These checks can run before Docker is installed:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv\Scripts\python.exe -m pip install --requirement sim\requirements-dev.txt
.venv\Scripts\python.exe sim\contracts\validate_examples.py
.venv\Scripts\python.exe -m unittest discover -s sim\tests\unit -v
```

Current automated baseline: 10 schemas and 41 contract fixtures pass; 36 simulator/configuration tests pass.

## Docker-dependent checks still required

- Resolve/pull both image tags and record their digests.
- Execute credential generation and confirm the password database is readable by the broker container.
- Parse the final Compose model with `docker compose config`.
- Bring all six services to healthy state.
- Observe all five live telemetry streams and presence events.
- Run `python -m sim.verify_lab` for safe live telemetry/auth/subscription checks.
- Test remaining operational write ACLs in an isolated integration run that cannot activate later phases.
- Restart the broker and each device independently.
- Confirm loopback-only host exposure and no runtime Internet access from internal services.
- Confirm no secret or generated password database is tracked.

Phase 2 cannot be declared complete until those checks pass on a Docker-capable machine.
