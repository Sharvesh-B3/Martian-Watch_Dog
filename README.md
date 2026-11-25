# Aegis Watchdog

A fully synthetic, isolated campus-IoT security demo that correlates cross-device attacks, blocks prompt injection, requires Human-in-the-Loop approval for containment, and explicitly routes a post-containment probe to a Decoy Twin.

## Running services

| Service | Endpoint |
|---|---|
| React command center | <http://127.0.0.1:5173> |
| FastAPI backend | <http://127.0.0.1:8000> |
| Backend health | <http://127.0.0.1:8000/health> |
| Docker MQTT lab | `127.0.0.1:1884` (container MQTT remains 1883) |

Host port 1884 avoids the machine's existing native Windows Mosquitto service on port 1883.

## Architecture

```text
React → FastAPI → MQTT trigger/control
                   ↓
            Attack controller
                   ↓
  Smart lock / RFID / Air / Power / Decoy Twin
                   ↓
        MQTT telemetry → FastAPI correlation
                   ↓
       Incident → HITL approval → quarantine + Decoy capture
```

All devices, badges, attacks, measurements, and Decoy captures are synthetic. Decoy routing is an explicit lab simulation—not transparent network redirection.

## Start from a clean machine

Docker Engine and Compose run inside WSL 2 Ubuntu in this environment.

```powershell
# Keep WSL alive for the local Docker daemon and start Docker Engine.
Start-Process -FilePath wsl.exe -ArgumentList @('-d','Ubuntu','--','sleep','infinity') -WindowStyle Hidden
wsl -d Ubuntu -- systemctl start docker

# Generate all eight ignored MQTT credentials.
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/ADMIN/Documents/Martian-Watch_Dog && python3 sim/setup_credentials.py'

# Build and start the complete lab/backend.
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/ADMIN/Documents/Martian-Watch_Dog && docker compose --env-file sim/.env up --build --detach --wait'

# Install and launch the frontend in live mode.
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

`frontend/.env.local` selects live REST/WebSocket mode and is intentionally ignored. Use `frontend/.env.example` as the committed template.

## Verification

```powershell
# Contracts and fast tests
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv\Scripts\python.exe sim\contracts\validate_examples.py
.venv\Scripts\python.exe -m unittest discover -s sim\tests\unit

# Normal telemetry/auth/allowed-subscription checks
.venv\Scripts\python.exe -m sim.verify_lab

# Complete API → MQTT → HITL → Decoy → audit → reset run
.venv\Scripts\python.exe -m sim.verify_e2e

# Frontend
cd frontend
npm run build
npm run typecheck
```

The isolated write/denied-read ACL mode is only safe before attack/control consumers are running. It was executed and passed during Phase A; do not rerun it on the integrated Phase B/C topology.

## Demonstration flow

1. Open <http://127.0.0.1:5173>.
2. Trigger **Sensor Spoofing** and observe a physics anomaly incident.
3. Trigger **Prompt Injection** after the previous scenario completes and observe the guardrail incident.
4. Trigger **Coordinated Intrusion** and observe lock + missing RFID + power-scan correlation.
5. Approve the pending action.
6. Observe lock quarantine, Decoy activation, capture count, and immutable SQLite audit entries.

The controller runs one bounded scenario at a time. The frontend/API may submit another request only after the previous lifecycle reaches `completed`.

## Reset and shutdown

```powershell
# Reset device/controller state through the API.
Invoke-RestMethod -Method Post -ContentType application/json -Body '{}' http://127.0.0.1:8000/api/sim/reset

# Stop containers but retain the SQLite audit volume.
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/ADMIN/Documents/Martian-Watch_Dog && docker compose --env-file sim/.env down'
```

After stopping the lab, `wsl --shutdown` may be used if no other WSL work is running. On the next launch, start the keepalive and Docker service again.

Credential rotation requires the lab to be stopped:

```powershell
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/ADMIN/Documents/Martian-Watch_Dog && python3 sim/setup_credentials.py --rotate'
```

## Security boundaries

- Anonymous MQTT access is denied.
- Every device has a distinct account and client ID.
- Backend cannot subscribe to private injection, raw Decoy input, or observer ground truth.
- Only backend credentials can publish triggers and high-risk controls.
- Device/controller containers use an internal Docker network and cannot reach external IPs.
- Broker and backend use dedicated loopback ingress only.
- MQTT credentials and generated password data are ignored by Git.
- TLS is deferred for this isolated local MVP and must be added before any non-local deployment.

## Detailed documentation

- `sim/README.md` — Role 1 operation and troubleshooting
- `sim/contracts/README.md` — message semantics and integration contract
- `sim/contracts/mqtt_topics.md` — topics and ACL ownership
- `sim/contracts/signoff.md` — remaining human sign-off
- `sim/docs/phase1.md` and `sim/docs/phase2.md` — detailed implementation evidence
