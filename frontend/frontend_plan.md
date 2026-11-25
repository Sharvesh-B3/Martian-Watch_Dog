# Aegis Watchdog — Frontend Plan (Role 3)

Scope: `frontend/` only. `plan.md`, `struct.md`, pitch slides and the 3-minute deck are out of scope.

Decisions already agreed:

- React + Vite + TypeScript, Tailwind v4 via `@tailwindcss/vite`.
- Backend endpoints come from `VITE_API_BASE_URL` / `VITE_WS_URL` with `localhost:8000` defaults.
- Agent Active/Bypassed toggle is a single adapter function; it is local-only in mock mode.
- Mock mode is a full local demo state machine behind the same API the live mode uses.
- `struct.md` is followed strictly; only the extra build/entry files `vite.config.ts`, `tsconfig.json`, `src/main.tsx`, `src/index.css` are added.

---

## Phase 0 — Make the current prototype buildable

**Goal:** `npm run build` and `npm run typecheck` pass.

- [x] Add `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, `tailwindcss`, `@tailwindcss/vite` and scripts to `package.json`.
- [x] Add `index.html`, `vite.config.ts`, `tsconfig.json`, `src/main.tsx`, `src/index.css` (`@import "tailwindcss"`).
- [x] Add `src/App.tsx` rendering `CommandCenter`.
- [x] Verify: `npm install && npm run build && npm run typecheck`.

## Phase 1 — Align the tree with `struct.md`

**Goal:** Documented files exist, behavior unchanged.

- [x] Move `src/page/CommandCenter.tsx` to `src/pages/CommandCenter.tsx`.
- [x] Extract `src/components/WingFloorplan.tsx` (live topology cards).
- [x] Extract `src/components/IncidentFeed.tsx` (AI explanation + guardrail flags).
- [x] Extract `src/components/ApprovalDrawer.tsx` (HITL approve/reject).
- [x] Extract `src/components/AuditLogPanel.tsx` (immutable action log).
- [x] Props typed from `src/types/watchdog.ts`; `CommandCenter` owns all state.
- [x] Verify: build still passes; layout looks identical to the starting prototype.

## Phase 2 — Integration seams + full mock state machine

**Goal:** Flipping one flag switches mock to live without touching components.

- [x] In `src/api/client.ts`: env-based API/WS config; typed `StreamEvent` union; WebSocket reconnect with backoff.
- [x] In `src/api/client.ts`: mock event bus so mock and live both deliver `device_update`, `new_incident`, `new_approval`, `audit_entry`.
- [x] In `src/api/client.ts`: `setAgentMode(enabled)` adapter (local mock state now; one place to wire a backend call later).
- [x] Implement all three attacks in mock mode:
  - `coordinated_intrusion` → correlated incident + pending HITL approval when agent active; unmitigated compromise when bypassed.
  - `prompt_injection` → guardrail block, sanitized payload excerpt, auto rate-limit audit entries.
  - `spoof_sensor` → filtered anomaly and audit trail.
- [x] Implement approval decisions in mock mode: approve quarantines the target, activates `decoy_twin_01`, and writes audit entries; reject writes the rejection audit.
- [x] Keep live REST calls for `/api/incidents`, `/api/approvals`, `/api/audit-log`, `/api/sim/trigger`, `/api/approvals/{id}/decide`; devices seed from `INITIAL_DEVICES` and update via `device_update` (no undocumented endpoint assumed).
- [x] `CommandCenter` consumes only the client interface; dedupe stream updates by id.
- [x] Verify: all three attacks and approve/reject work in mock mode (logic wired through the mock event bus).

## Phase 3 — Verification and handoff

**Goal:** Clean build and a repeatable demo.

- [x] `npm run build`, `npm run typecheck`, `npm run dev` clean.
- [ ] Demo walkthrough (manual browser check): Agent Bypassed → Coordinated Breach; Agent Active → Prompt Injection; Coordinated Breach → Approve Containment → Decoy Twin + Audit Log.
- [x] Document in this file the exact one-step change needed when `backend/` is ready (flip `VITE_USE_MOCK_DATA=false`, optionally set API/WS URLs).

---

## Integration contract (for Role 2)

- `GET /api/incidents` → `Incident[]`
- `GET /api/approvals` → `ApprovalRequest[]`
- `GET /api/audit-log` → `AuditEntry[]`
- `POST /api/sim/trigger` body `{ attack_type }`
- `POST /api/approvals/{id}/decide` body `{ decision }`
- WebSocket `/api/stream` events: `device_update`, `new_incident`, `new_approval`, `audit_entry`

Frontend types live in `src/types/watchdog.ts`; reconcile 1:1 with `backend/app/schemas.py` when that file exists.
