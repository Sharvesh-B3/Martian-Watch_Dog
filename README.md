# Martian-Watch_Dog

Role 2 backend: a FastAPI Watchdog Agent that correlates lab telemetry, guards untrusted data, reasons through an LLM, gates containment behind human approval, and streams state to the React SOC dashboard.

## 1. Lab isolation

All MQTT traffic stays in an isolated local lab:

- Mosquitto is bound to `127.0.0.1:1883` only (`docker-compose.yml`).
- Telemetry topic prefix: `campus/lab1/#`.
- Control topics: `campus/lab1/control/+`.
- Attacker endpoint: `127.0.0.1:1884` (containment gateway).
- Decoy broker: `127.0.0.1:1885`.
- Gateway control/status: `127.0.0.1:9000`.
- No real facility network or production device is involved.
- Sim device IDs are translated to canonical frontend IDs by `backend/app/mqtt_client.py`.

## 2. Backend setup

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
```

Create a root-level `.env` (do not commit it) using `backend/.env.example` as the template. Required values:

- `MQTT_HOST=127.0.0.1`, `MQTT_PORT=1883`, `MQTT_TOPIC_PREFIX=campus/lab1`
- `LLM_PROVIDER=gemini` with `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-3.5-flash-lite`
- `DB_PATH=backend/data/watchdog.db`
- `CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]`
- `WINDOW_SECONDS=60`

The default provider is the direct Gemini API with structured JSON output. `LLM_PROVIDER=local` switches to an OpenAI-compatible local endpoint via `LOCAL_LLM_BASE_URL`. Missing provider settings fail startup fast; a runtime LLM failure returns `503` and writes a `SYSTEM` audit entry `LLM_UNAVAILABLE` — no fabricated explanation is created.

The API connects to Mosquitto during startup, so start it after the Role 1 lab
launcher described below.

## 3. Simulator and frontend

Start the broker and the six-device simulator (five dashboard nodes plus the
internal CCTV correlation signal) with one command:

```bash
source .venv/bin/activate
python -m sim.run_lab --seed 42 --no-noise --monitor
```

The launcher starts real and decoy Mosquitto brokers, the L4 containment
gateway, a synthetic network attacker, six independent device processes and the
persistent Red Team controller. Ctrl+C stops every child and the brokers it
started. Add `--noise 0.25` for seeded metric drift or `--keep-broker` to leave
Mosquitto running after the lab exits.

In a second terminal, start the API from the repository root:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000
```

In a third terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

For live backend data, create `frontend/.env.local` with:

```bash
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/api/stream
VITE_USE_MOCK_DATA=false
```

Dashboard attack buttons call `POST /api/sim/trigger`. Raw MQTT attacks enter
the same correlation → Agent → HITL pipeline:

```bash
python -m sim.attacks.red_team
```

Option 1 emits CCTV loss, an unauthorized door unlock and port-scan evidence as
one coordinated intrusion. Approved containment quarantines `door_lock_01` and
activates the separate `decoy_twin_01` simulator. The containment gateway then
disconnects the attacker TCP session and changes the same gateway endpoint from
the real broker to the decoy broker. Attack evidence remains active until the
Red Team menu publishes reset (`r`) or a device receives RESTORE. While active,
the Decoy Twin captures the actually rerouted MQTT probes and streams gateway
bytes, reconnect count, capture count and safe payload hashes to the dashboard.

Gateway status is independently visible at:

```bash
curl http://127.0.0.1:9000/status
```

Before approval `route_target` is `real`. After approval it is `decoy`, the
attacker reconnect count increases and `decoy_bytes` begins increasing. Restore
the real route with:

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"incident_id":"RESTORE"}' \
  http://127.0.0.1:9000/route/real
```

For a full demo reset, open **Start simulation → Reset lab**. That restores all
device states and baseline metrics, clears held attack scenarios, resets the
gateway counters, and returns the network route to the real broker. It is also
available as `POST /api/sim/reset`.

## 4. Integration contract

- `GET /health`
- `GET /api/incidents` → `Incident[]`
- `GET /api/approvals` → `ApprovalRequest[]`
- `GET /api/audit-log` → `AuditEntry[]`
- `POST /api/sim/trigger` body: `{"attack_type": "spoof_sensor|coordinated_intrusion|prompt_injection"}`
- `POST /api/sim/reset` → `{ ok, reset }` restores devices, attacks and gateway route
- `POST /api/approvals/{id}/decide` body: `{"decision": "approved|rejected"}`
- `POST /api/agent/mode` body: `{"enabled": true|false}`
- `WS /api/stream` → `device_update`, `new_incident`, `new_approval`, `audit_entry`

## 5. Quick demo

1. Toggle Agent **BYPASSED**, trigger Coordinated Intrusion → unmitigated incident plus `UNMITIGATED_BREACH` audit.
2. Toggle Agent **ACTIVE**, trigger Prompt Injection → guardrail flags the payload, low-risk auto action emits a warning and audit.
3. Trigger Coordinated Intrusion, approve the pending request → the attacker terminal changes from `REAL_LAB` to `DECOY_LAB`, the lock is quarantined, gateway `decoy_bytes` increases, Decoy Twin captures traffic, and the frontend shows **Network reroute applied**.

Distinct breaches inside the same 60-second correlation window are emitted as
separate incidents; duplicate MQTT echoes of one attack remain deduplicated.

## 6. Verification

```bash
python -m pytest -q backend/tests sim/tests
cd frontend && npm run typecheck && npm run build
```
