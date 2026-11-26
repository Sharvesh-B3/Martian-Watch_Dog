# Trinetra — Local IoT Security MVP

Trinetra is a fully local, operator-supervised security console for a simulated
campus IoT lab. It demonstrates the complete path from device telemetry to a
real, reversible network containment action:

```text
Simulator → MQTT → Guardrail → Correlation → Local LLM → HITL
→ Loopback Gateway Reroute → Operator Console → SQLite Audit
```

The MVP is intentionally lab-only. No real facility network, production device,
firewall rule, or cloud AI service is involved.

---

## 1. What this MVP proves

- **Multi-process lab:** independent simulator processes publish MQTT telemetry
  for smart lock, RFID scanner, air-quality sensor, power meter, CCTV camera and
  a Decoy Twin.
- **Deterministic detection:** a 60-second correlation window escalates a lone
  port scan into a critical coordinated intrusion when paired with an
  unauthorized door unlock and no RFID badge.
- **Prompt-injection guardrail:** instruction-override phrases are detected and
  redacted before the telemetry reaches the model.
- **Local reasoning:** Ollama `qwen2.5:3b` explains incidents in plain English;
  it does not decide risk or execute actions.
- **Human-in-the-loop control:** high-risk containment stays pending until a
  human operator approves it.
- **Real reroute proof:** the attacker endpoint is switched from the real broker
  to a decoy broker through a loopback TCP gateway, with byte counts and session
  evidence.
- **Reversible reset:** `Reset lab` restores devices, attack state, gateway route
  and counters, and writes an audit entry.
- **Auditable workflow:** incidents, approvals and audit entries are persisted in
  SQLite and streamed live to the console.

---

## 2. Architecture

```text
                         ┌──────────────────────┐
                         │ Simulated IoT devices│
                         └──────────┬───────────┘
                                    │ MQTT :1883
                                    ▼
                         ┌──────────────────────┐
                         │ Mosquitto real broker│
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ MqttBridge + guardrail│
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ 60s CorrelationWindow│
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Local Ollama Agent   │
                         │ qwen2.5:3b           │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ HITL engine          │
                         └───────┬──────┬───────┘
                                 │      │
                    MQTT control │      │ gateway control
                                 ▼      ▼
                       ┌────────────┐ ┌──────────────────┐
                       │ Quarantine │ │ Containment proxy│
                       │ Decoy Twin │ │ 127.0.0.1:1884   │
                       └─────┬──────┘ └────────┬─────────┘
                             │                 ▼
                             │        ┌──────────────────┐
                             │        │ Decoy broker :1885│
                             │        └────────┬─────────┘
                             ▼                 ▼
                         ┌───────────────────────────────┐
                         │ StreamHub / WebSocket /api/stream
                         └───────────────┬───────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │ Trinetra React operator console│
                         └───────────────┬───────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │ SQLite: incidents, approvals,  │
                         │ audit_log                      │
                         └───────────────────────────────┘
```

---

## 3. Lab ports and isolation

| Endpoint | Purpose |
|---|---|
| `127.0.0.1:1883` | Real Mosquitto broker |
| `127.0.0.1:1885` | Decoy Mosquitto broker |
| `127.0.0.1:1884` | Attacker-facing containment TCP gateway |
| `127.0.0.1:9000` | Gateway control/status API |
| `127.0.0.1:8000` | FastAPI backend and WebSocket |
| `127.0.0.1:5173` | Vite frontend |

Telemetry prefix: `campus/lab1/#`

Control prefix: `campus/lab1/control/+`

Gateway status is independently visible:

```bash
curl http://127.0.0.1:9000/status
```

No host firewall, `iptables`, DNAT or production network configuration is used.

---

## 4. Repository layout

```text
sim/                  Multi-process simulator, attacks and containment gateway
  run_lab.py          One-command lab launcher
  attacks/            Scenario publisher, controller and synthetic attacker
  devices/            Smart lock, RFID, air quality, meter, CCTV, Decoy Twin
  common/             MQTT device base class, settings and protocol helpers

backend/              FastAPI backend
  app/main.py         Lifespan wiring and router registration
  app/mqtt_client.py  MQTT ingest, device state and control publishing
  app/guardrail.py    Prompt-injection regex sanitizer
  app/correlation_window.py  Deterministic 60-second detection rules
  app/agent.py        Local LLM reasoning and incident creation
  app/hitl_engine.py  Approval, quarantine, decoy and reroute enforcement
  app/containment_gateway.py  Gateway client with confirmation checks
  app/audit_db.py     SQLite persistence
  app/api/            REST and WebSocket routes

frontend/             React + TypeScript operator console
  src/pages/          Command center
  src/components/     Device rail, approval panel, proof card, menus
  src/hooks/          Live state and action orchestration
  src/api/            REST/WebSocket client seam

backend/tests/        Backend and API tests
sim/tests/            Simulator and gateway tests
```

---

## 5. Prerequisites

- Python 3.11+
- Node.js 20+
- Docker with Compose plugin
- Ollama running locally with the model pulled:

```bash
ollama pull qwen2.5:3b
```

Do not start a second Ollama server if one is already running.

---

## 6. Configuration

### Backend

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp backend/.env.example .env
```

The final MVP configuration uses local reasoning:

```dotenv
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=campus/lab1

LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen2.5:3b
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2

GATEWAY_CONTROL_URL=http://127.0.0.1:9000
GATEWAY_TIMEOUT_SECONDS=5

DB_PATH=backend/data/watchdog.db
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
WINDOW_SECONDS=60
```

`.env` is ignored by Git and must not be committed. The backend fails fast if
the selected provider is not configured. If local reasoning is unavailable at
runtime, the API returns `503` and writes an `LLM_UNAVAILABLE` audit entry; no
explanation is fabricated.

### Frontend

Create `frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000/api
VITE_WS_URL=ws://127.0.0.1:8000/api/stream
VITE_USE_MOCK_DATA=false
```

Install dependencies:

```bash
cd frontend
npm install
```

---

## 7. Running the MVP

Use three or four terminals from the repository root.

### Terminal 1 — simulator, brokers, attacker and gateway

```bash
source .venv/bin/activate
python -m sim.run_lab --seed 42 --no-noise --monitor
```

Useful options:

- `--noise 0.25` adds seeded metric drift.
- `--keep-broker` leaves Mosquitto running after exit.
- `--no-broker` connects to already-running brokers.
- Ctrl+C stops all child processes and brokers started by the launcher.

### Terminal 2 — backend

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000
```

### Terminal 3 — frontend

```bash
cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

### Terminal 4 — optional red-team console

```bash
source .venv/bin/activate
python -m sim.attacks.red_team
```

Options:

```text
1  Coordinated intrusion
2  Sensor spoofing
3  Prompt injection
4  Manual device control
r  Reset all scenarios and devices
q  Quit
```

---

## 8. Recommended judge demo

### Step 1 — baseline

Show:

- Live backend and Agent active in the header.
- Five devices normal.
- Permanent right approval rail in standby or showing the last decision.

### Step 2 — optional bypass demonstration

Set Agent to **Bypassed**, then trigger **coordinated intrusion**.

Expected:

- `Unmitigated ...` incident.
- `UNMITIGATED_BREACH` audit entry.
- No approval and no containment.

Set Agent back to **Active** before continuing.

> Approvals are not retroactive. Do not trigger the coordinated scenario while
> bypassed if you expect a pending approval panel.

### Step 3 — sensor spoofing

Trigger **sensor spoofing**.

Expected:

- Detected as low risk.
- Safe auto-action flags applied.
- Device becomes `warning`.
- No quarantine.

### Step 4 — prompt injection

Trigger **prompt injection**.

Expected:

- Injection excerpt visible as operator evidence.
- Phrase redacted before the LLM prompt.
- Incident explains that telemetry was treated as untrusted data.

### Step 5 — coordinated intrusion

Trigger **coordinated intrusion**.

Expected:

- 60-second correlation finds door unlock + outbound scan + no RFID badge.
- Severity `critical`, risk `high`, `auto_execute=false`.
- Right panel shows `Human approval required`.

### Step 6 — approve containment

Click **Approve containment**.

Expected:

- Smart lock becomes `quarantined`.
- Decoy Twin becomes active.
- Gateway switches from `real` to `decoy`.
- Attacker session is disconnected.
- `decoy_bytes` increases and attacker probes are captured.
- Proof card and audit entries appear.

Approval is fail-closed: if the gateway does not confirm the route switch, the
API returns `502`, the approval remains pending, and `NETWORK_REROUTE_FAILED`
is audited.

### Step 7 — reset

Open **Start simulation → Reset lab**.

Expected:

- Devices return to normal baseline.
- Held attack scenarios are cleared.
- Gateway returns to `real` and counters zero.
- `LAB_RESET` audit entry is written.
- The right panel remains visible with the last decision.

---

## 9. Backend pipeline details

### Ingest and sanitize

`MqttBridge` subscribes to `campus/lab1/#`, maps simulator IDs to canonical IDs,
sanitizes every string value and adds the frame to the correlation window.

### Guardrail

`backend/app/guardrail.py` uses compiled, case-insensitive regular expressions
to detect instruction-override patterns such as:

- `ignore all previous instructions`
- `disregard prior instructions`
- `system:` / `assistant:` role markers
- `override all rules`
- `new instructions:`

Matches are replaced with `[REDACTED]`. `wrap_untrusted()` then frames the
sanitized signal inside `<untrusted_telemetry>` tags and explicitly instructs
the model not to follow instructions found in telemetry.

### Correlation

`CorrelationWindow` keeps a 60-second rolling buffer and emits deterministic
`Signal` objects:

| Rule | Risk | Action |
|---|---|---|
| Prompt injection | low | auto-filter |
| Implausible air-quality reading | low | auto-filter |
| Isolated outbound scan | low | auto-filter |
| Unlock + scan + no badge | high | HITL approval |

Event fingerprints deduplicate MQTT echoes while allowing a later scenario with
a new `scenario_id` to produce a fresh incident.

### Agent

The local Ollama model returns validated JSON with sense, think, act, explain,
severity, category, risk level and auto-execute. The backend uses the model's
explanation and proposed action text only. Severity, category, risk and
auto-execute remain authoritative from the deterministic signal.

### HITL

`HitlEngine` auto-executes only safe low-risk flags. High-risk signals create a
pending approval. Actual containment commands are fixed:

```text
QUARANTINE → smart_lock_01
DECOY      → decoy_twin_01
```

They are not chosen dynamically by the model.

### Gateway

The containment gateway is a loopback TCP proxy:

```text
attacker endpoint → real broker 127.0.0.1:1883
                  → decoy broker 127.0.0.1:1885
```

Control API:

```text
GET  /status
POST /route/real
POST /route/decoy
POST /sessions/disconnect
```

---

## 10. HTTP and WebSocket API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Backend health |
| `GET` | `/api/incidents` | Persisted incidents |
| `GET` | `/api/approvals` | Approval requests |
| `GET` | `/api/audit-log` | Audit entries |
| `POST` | `/api/sim/trigger` | Trigger a lab scenario |
| `POST` | `/api/sim/reset` | Full lab reset |
| `POST` | `/api/approvals/{id}/decide` | Approve or reject |
| `POST` | `/api/agent/mode` | Activate or bypass Agent |
| `WS` | `/api/stream` | Live events |

Trigger body:

```json
{ "attack_type": "spoof_sensor" }
```

Valid values:

```text
spoof_sensor
coordinated_intrusion
prompt_injection
```

Decision body:

```json
{ "decision": "approved" }
```

WebSocket events:

```text
device_update
new_incident
new_approval
audit_entry
```

---

## 11. Activity logs and persistence

Trinetra stores all durable state in one SQLite database.

Configured default:

```text
backend/data/watchdog.db
```

Tables:

```text
incidents
approvals
audit_log
```

The Activity drawer combines incidents from `/api/incidents` with audit entries
from `/api/audit-log`. Live rows arrive over `/api/stream`.

Example audit actions:

```text
HITL_APPROVAL_REQUESTED
APPROVAL_APPROVED
APPROVAL_REJECTED
DECOY_ACTIVATED
NETWORK_REROUTE_APPLIED
NETWORK_REROUTE_FAILED
UNMITIGATED_BREACH
LAB_RESET
LLM_UNAVAILABLE
```

A backend process may override the default with `DB_PATH=/some/path.db`.

---

## 12. Verification

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider backend/tests sim/tests
```

Expected:

```text
89 passed
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

Infrastructure and diff checks:

```bash
docker compose config
git diff --check
```

---

## 13. MVP boundaries

- The guardrail is deterministic regex-based coverage for known override
  patterns, not a claim of blocking every possible prompt injection.
- The LLM explains; it does not authorize or execute containment.
- The reroute is real only inside the loopback lab.
- The simulator is synthetic and seeded for repeatable judging.
- No secrets belong in Git. `.env` and `frontend/.env.local` stay ignored.

---

## 14. One-line judge explanation

> Trinetra is a local IoT security MVP where deterministic correlation detects
> cross-device attacks, a local Ollama model explains them in plain English, a
> human approval gate controls containment, and a loopback gateway proves the
> attacker was really rerouted to a decoy — with every step audited and
> reversible.
