# Aegis Watchdog — Backend Plan (Role 2)

Scope: `backend/` only, plus the minimal frontend seam changes and README notes listed in Phase 7. `plan.md`, `struct.md`, `sim/` and the rest of `frontend/` are references and stay unchanged.

Decisions already agreed:

- Code lives in `backend/app/` exactly as described in `struct.md`.
- FastAPI + `paho-mqtt` + SQLite (stdlib `sqlite3`) + Pydantic; no extra infrastructure services.
- `backend/app/schemas.py` is 1:1 with `frontend/src/types/watchdog.ts`.
- Live Agent Active/Bypassed toggle: add `POST /api/agent/mode`; `frontend/src/api/client.ts:setAgentMode()` posts to it.
- LLM is required: direct Gemini API via `httpx` (structured JSON with a response schema) now, with a switchable OpenAI-compatible local endpoint for later (`LLM_PROVIDER=gemini|local`, default `GEMINI_MODEL=gemini-3.5-flash-lite`; `gemini-2.5-flash` is no longer available to new users). The model remains configurable with `GEMINI_MODEL`. Missing config fails fast at startup; failed reasoning returns `503` + a `SYSTEM` audit entry. No fabricated offline explanation. Transient `429`/`5xx` and network errors get up to 3 attempts with exponential backoff (`0.5s`, `1s`); auth/parse errors fail immediately. The former OpenAI-compatible router provider was removed.
- HITL: low-risk actions auto-execute; high-risk quarantine/decoy requires approval and publishes MQTT control commands.
- Role 1 device IDs/topics differ from the frontend contract; the backend absorbs this with a canonical ID map. `cctv_01` stays internal as correlation evidence.
- Focused `pytest` suite for guardrail, correlation, HITL and schema parity.
- `struct.md` is followed strictly; justified extras are `backend/app/llm_client.py`, `backend/app/api/routes_agent.py`, `backend/tests/`.

---

## Phase 0 — Scaffold and configuration

**Goal:** importable package, validated environment, FastAPI app boots with `/health`.

- [x] Add `backend/requirements.txt`: `fastapi`, `uvicorn[standard]`, `paho-mqtt`, `pydantic-settings`, `python-dotenv`, `httpx`, `pytest`.
- [x] Add `backend/.env.example` with `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC_PREFIX=campus/lab1`, `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `DB_PATH`, `CORS_ORIGINS`, `WINDOW_SECONDS=60`.
- [x] Add `backend/__init__.py`, `backend/app/__init__.py` and `backend/app/config.py` using `pydantic-settings`; require `GEMINI_API_KEY` when provider is `gemini`, require `LOCAL_LLM_BASE_URL` when provider is `local`.
- [x] Add `backend/app/main.py`: FastAPI app, CORS from `CORS_ORIGINS`, lifespan stub, `GET /health`.
- [x] Verify: `pip install -r backend/requirements.txt`, `uvicorn backend.app.main:app`, `curl localhost:8000/health` → `200 {"status":"ok"}`; missing key fails fast with a validation error.

## Phase 1 — Contract sync and persistence

**Goal:** schemas match the frontend exactly; SQLite round-trips incidents, approvals and audit entries.

- [x] Add `backend/app/schemas.py` with enums `DeviceStatus`, `AttackCategory`, `ApprovalStatus`, `DeviceType`, `Actor` and models `DeviceNode`, `Incident`, `ApprovalRequest`, `AuditEntry`, plus `StreamEvent` union and request models (`TriggerRequest`, `DecisionRequest`, `AgentModeRequest`). Use the exact field names and literal values from `frontend/src/types/watchdog.ts`.
- [x] Add `backend/tests/test_schema_parity.py` asserting enum/field snapshots match `watchdog.ts` (read the TS file when present).
- [x] Add `backend/app/audit_db.py`: initialise tables for incidents, approvals and append-only audit log; helpers for insert/list/update; UTC ISO timestamps; stable IDs; `threading.RLock` for the shared connection.
- [x] Verify: `pytest -q backend/tests/test_schema_parity.py` → 8 passed; manual insert/list/update round-trip confirmed prefixed IDs, `Z` timestamps and JSON field handling.

## Phase 2 — Guardrail and 60-second correlation

**Goal:** untrusted telemetry is sanitized before reasoning; multi-device attack rules fire inside a 60s window.

- [x] Add `backend/app/guardrail.py`: detect and strip instruction overrides (`IGNORE ALL PREVIOUS INSTRUCTIONS`, `ignore previous instructions`, role/system impersonation); return `(clean_payload, detected, sanitized_excerpt)`; add `wrap_untrusted()` that delimits telemetry as untrusted data for the LLM prompt.
- [x] Add `backend/app/correlation_window.py`: timestamp-pruned deque per zone/device; emit signals for coordinated intrusion (door `UNLOCKED`/`UNAUTHORIZED_BYPASS` with no RFID badge plus meter `network_conns > 50` / port-scan flag within 60s), sensor spoofing (CO2 > 1000 or temp outside 10-35 C) and injected payload markers; dedupe within the window; consumed signals clear the window so repeated simulated attacks stay independent.
- [x] Add `backend/tests/test_guardrail.py` and `backend/tests/test_correlation_window.py`.
- [x] Verify: `python -m pytest -q backend/tests` → 19 passed.

## Phase 3 — MQTT bridge and device state

**Goal:** live sim telemetry drives canonical `device_update` events; backend can publish control commands back to the sim.

- [x] Add `backend/app/mqtt_client.py` and `backend/app/stream_hub.py`: `paho` client with `loop_start()`, subscribe `campus/lab1/#` (ignore `control/#`), JSON parse + guardrail sanitize + feed correlation window. WebSocket route deferred to Phase 6 per decision.
- [x] Canonical ID map: `smart_lock_01 ↔ door_lock_01`, `rfid_scanner_01 ↔ rfid_01`, `air_quality_01 ↔ aq_sensor_01`, `power_meter_01 ↔ meter_01`, `decoy_twin_01` virtual only; `cctv_01` internal evidence.
- [x] Maintain device registry mirroring frontend `INITIAL_DEVICES` (`normal`/`warning`/`quarantined`/`decoy`, metrics, `last_updated`) and broadcast `device_update` on every telemetry message.
- [x] Add `publish_control(canonical_id, action)` → `campus/lab1/control/{sim_id}` with `{"action": "QUARANTINE|DECOY|RESTORE|NORMAL"}`.
- [x] Wire async connect/disconnect into `main.py` lifespan; backend starts even when the broker is unavailable and paho retries in the background.
- [x] Verify: `python -m pytest -q backend/tests` → 24 passed, including ID mapping, metric mapping, status authority, control publishing and injection sanitization. Live broker+sim check deferred to Phase 8 (Docker/Mosquitto unavailable locally).

## Phase 4 — LLM reasoning adapter

**Goal:** structured Sense → Think → Act → Explain JSON from the direct Gemini API, with a local-provider switch and explicit failure behaviour.

- [x] Add `backend/app/llm_client.py`: provider adapter. Gemini via `httpx` POST to `{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent` with `x-goog-api-key`, `systemInstruction`, `contents`, and JSON `responseMimeType`/`responseSchema`; local via `{LOCAL_LLM_BASE_URL}/chat/completions`; timeout; bounded retry for transient `429`/`500`/`502`/`503`/`504` and transport errors (3 attempts, exponential backoff); raise `LLMUnavailable` on final failure.
- [x] Add `backend/app/agent.py`: deterministic prefilter decides whether to call the LLM; send sanitized telemetry + correlation signals framed as untrusted data; validate returned JSON keys `sense`, `think`, `act`, `explain`, `severity`, `category`, `risk_level`, `auto_execute`; map to `Incident`.
- [x] Bypassed mode path: explicit `UNMITIGATED_BREACH` audit + warning device updates, no AI explanation generated.
- [x] Failure path: startup validates required env; runtime failure raises `LLMUnavailable` (API `503` + `SYSTEM` audit `LLM_UNAVAILABLE` wired in Phase 6); no incident is invented.
- [x] Verify: mocked Gemini and local unit tests pass; `python -m pytest -q backend/tests` → **58 passed**. Live Gemini smoke passed with `gemini-3.5-flash-lite` and returned valid structured JSON; `gemini-2.5-flash` returned `404` as it is no longer available to new users.

## Phase 5 — HITL enforcement and audit

**Goal:** low-risk auto actions, high-risk pending approvals, approval publishes containment.

- [x] Add `backend/app/hitl_engine.py`: `handle_signals()` consumes `AgentResult`, auto-executes low-risk actions (warning + rate_limited/drop_sample flags + `AUTO_ACTION_EXECUTED` audit) and queues high-risk containment as pending `ApprovalRequest` targeting the first correlated device with `HITL_APPROVAL_REQUESTED` audit.
- [x] `decide(approval_id, decision)`: on approve publish `QUARANTINE` then `DECOY` to the target sim device, mark target quarantined, activate `decoy_twin_01` with `active_traps=1`/`captured_payloads=0`, update approval/incident, write `APPROVAL_APPROVED` + `DECOY_ACTIVATED` audits; on reject only update records and write `APPROVAL_REJECTED`.
- [x] Broadcast `new_approval`, `new_incident`, `device_update` and `audit_entry` for every state transition.
- [x] Add `backend/tests/test_hitl_engine.py` with a fake MQTT publisher.
- [x] Verify: `python -m pytest -q backend/tests` → green with fake publisher; live sim console check deferred to Phase 8 (broker unavailable locally).

## Phase 6 — REST and WebSocket API

**Goal:** serve the exact frontend integration contract.

- [x] Add `backend/app/api/routes_incidents.py`: `GET /api/incidents`, `GET /api/audit-log`, `POST /api/sim/trigger` with body `{"attack_type": "spoof_sensor|coordinated_intrusion|prompt_injection"}`. Trigger publishes MQTT payloads mirroring `sim/attacks/red_team.py` and feeds them in-process through `backend/app/pipeline.py`.
- [x] Add `backend/app/api/routes_approvals.py`: `GET /api/approvals`, `POST /api/approvals/{id}/decide` body `{"decision": "approved|rejected"}` returning `{ok, id, status}`; unknown → 404, already decided → 409.
- [x] Add `backend/app/api/routes_stream.py`: `WS /api/stream` with `StreamHub` subscription, current `device_update` replay, and live `device_update`/`new_incident`/`new_approval`/`audit_entry` events.
- [x] Add `backend/app/api/routes_agent.py`: `POST /api/agent/mode` body `{"enabled": bool}` returning `{ok, enabled}`; repeated mode is a no-op, changes audit `AGENT_ACTIVATED`/`AGENT_BYPASSED`.
- [x] Include all routers in `main.py`; CORS allows the frontend dev origin. LLM failure during trigger returns 503 with `SYSTEM` audit `LLM_UNAVAILABLE` and no invented incident.
- [x] Verify: `python -m pytest -q backend/tests` → green with TestClient for REST/WS; live broker/sim check deferred to Phase 8 (broker unavailable locally).

## Phase 7 — Frontend seam and documentation

**Goal:** live mode matches mock mode for the agent toggle; setup is documented.

- [x] In `frontend/src/api/client.ts`, make `setAgentMode(enabled)` POST `{ enabled }` to `/api/agent/mode`; kept the exported name and `(enabled: boolean) => void` signature as the single seam. Mock mode still updates local state/audit; live mode logs POST failures without reverting the local toggle.
- [x] In `frontend/src/pages/CommandCenter.tsx`, change `toggleAgent` to `void setAgentMode(next)`.
- [x] Add a concise backend setup + environment + lab-isolation section to `README.md`, including the REST/WS contract, live frontend env values, and the 3-step demo.
- [x] Verify: `npm run typecheck` and `npm run build`; live-mode toggle is audited by `POST /api/agent/mode`.

## Phase 8 — End-to-end verification and handoff

**Goal:** the 3-minute qualification demo works against live services.

- [ ] Full stack up: Mosquitto, sim devices, backend, frontend with `VITE_USE_MOCK_DATA=false` — deferred locally: Docker/Mosquitto are not installed. See handoff below.
- [x] `python -m pytest -q backend/tests` → **58 passed**.
- [x] Trigger all three attacks via `POST /api/sim/trigger`; WS client receives all four event types; approval decision activates quarantine/decoy in backend state.
- [ ] Confirm sim console prints `QUARANTINE`/`DECOY` — requires the live broker/sim; deferred to handoff.
- [x] Persistence verified by reopening the same SQLite DB in a fresh FastAPI app instance; live server restart deferred.
- [ ] Rehearse demo: Bypassed → Coordinated Breach; Active → Prompt Injection; Coordinated Breach → Approve → Decoy Twin + Audit Log — manual handoff.
- [x] Failure path: simulated `LLMUnavailable` returns `503` + `SYSTEM` audit `LLM_UNAVAILABLE`, with no incident/approval created.

### Handoff: remaining manual live-demo steps

1. On a machine with Docker: `docker compose up -d mosquitto`.
2. Start sim devices: `python sim/devices/sim_devices.py`.
3. Start the backend from the repo root with `GEMINI_API_KEY` set in the environment (or root `.env`): `uvicorn backend.app.main:app --reload --port 8000`.
4. Start the frontend with `VITE_USE_MOCK_DATA=false` and `VITE_API_BASE_URL` / `VITE_WS_URL` pointing at the backend.
5. In the dashboard: Bypassed → Coordinated Intrusion (expect `UNMITIGATED_BREACH`); Active → Prompt Injection (expect guardrail + auto action); Coordinated Intrusion → Approve (expect sim console `QUARANTINE` then `DECOY`, Decoy Twin active, audit entries).
6. Restart the backend and confirm incidents/approvals/audit are unchanged.

---

## Integration contract (for Role 3)

- `GET /api/incidents` → `Incident[]`
- `GET /api/approvals` → `ApprovalRequest[]`
- `GET /api/audit-log` → `AuditEntry[]`
- `POST /api/sim/trigger` body `{ "attack_type": "spoof_sensor" | "coordinated_intrusion" | "prompt_injection" }` → `{ ok, triggered }`
- `POST /api/approvals/{id}/decide` body `{ "decision": "approved" | "rejected" }` → `{ ok, id, status }`
- `POST /api/agent/mode` body `{ "enabled": boolean }` → `{ ok, enabled }`
- WebSocket `/api/stream` events: `device_update`, `new_incident`, `new_approval`, `audit_entry`

All payload shapes are defined in `backend/app/schemas.py` and must remain 1:1 with `frontend/src/types/watchdog.ts`.
