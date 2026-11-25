# Aegis Watchdog — 24-Hour Hackathon & Qualification Plan

**Track:** Track 3 — Life-Support Watchdog (IoT Security)  
**Concept:** A physics-aware, cross-device **IoT Immune System** for campus infrastructure that detects multi-sensor intrusions, neutralizes prompt-injection payloads, and enforces Human-in-the-Loop (HITL) containment with active **Decoy Twin** deception.

---

## 1. What Makes Us Stand Out (Judge Differentiators)

1. **Cross-Device Correlation (Not Single-Sensor Thresholds):**
   Correlates telemetry across a 60-second rolling window for an entire simulated **Campus Lab Wing** (`smart_lock_01`, `rfid_scanner_01`, `air_quality_01`, `power_meter_01`, and `decoy_twin_01`). Detects coordinated physical + cyber breaches (e.g., door unlocking without a matching RFID scan right after outbound port scanning).
2. **Active Deception ("Decoy Twin" Containment):**
   Instead of merely raising an alert, approved containment locks down the compromised device and explicitly redirects subsequent **simulated attacker traffic** to a synthetic **Decoy Twin** honeypot node. This is an observable lab simulation, not a claim of transparent broker- or network-level routing.
3. **Live Prompt-Injection Defense (Rule 8 Showcase):**
   Sanitizes untrusted sensor payloads before LLM reasoning and demonstrates live interception of adversarial prompt injections hidden inside telemetry metadata (`"IGNORE PREVIOUS INSTRUCTIONS..."`).
4. **Human-in-the-Loop + Immutable Audit Trail (Rule 7 Compliance):**
   Low-risk mitigations (topic rate-limiting) run automatically; high-risk physical/network quarantine requires 1-click operator approval with full cryptographic/timestamped logging.

---

## 2. Team Role Split & Deliverables

### Role 1 — IoT Lab & Red Team Lead (`sim/`) **[YOU]**
* **Deliverables:**
  * Isolated Docker Compose setup with **Eclipse Mosquitto**, an explicit internal lab network, authenticated accounts, topic ACLs, health checks, and no undocumented external runtime dependency.
  * 5 separate simulated Python IoT services (`smart_lock_01`, `rfid_scanner_01`, `air_quality_01`, `power_meter_01`, and `decoy_twin_01`) publishing contract-valid synthetic telemetry through unique MQTT clients.
  * An MQTT-triggered Red Team controller implementing exactly `spoof_sensor`, `coordinated_intrusion`, and `prompt_injection`, with lifecycle status, deterministic reset, and an operator CLI that uses the same trigger contract.
  * Authenticated command handling for quarantine, restore, Decoy Twin activation, acknowledgements, and explicit **simulated** redirection of subsequent attacker traffic to the decoy.
  * Versioned message contracts, fixtures, automated tests, isolation evidence, and a repeatable Role 1 operations runbook.
* **Locked Decisions:** Five-device topology only; one Compose service per device; MQTT trigger boundary with Role 2; explicit simulated Decoy Twin routing; authenticated ACLs; all phase gates require fresh verification.
* **Detailed Execution:** `sim/docs/phase1.md` through `sim/docs/phase6.md` are the authoritative gated Role 1 roadmap.
* **Key Check:** Verify lab isolation, ACL denials, 100% synthetic data, truthful simulated-routing claims, and clean repeatability for organiser inspection.

### Role 2 — AI Agent & Guardrails Architect (`backend/`)
* **Deliverables:**
  * FastAPI backend (`app/main.py`) ingesting MQTT streams into a 60s sliding correlation window (`correlation_window.py`).
  * **Prompt-Injection Guardrail** (`guardrail.py`) stripping/flagging adversarial instructions in untrusted sensor fields.
  * Anomaly pre-filter + structured LLM reasoning (`agent.py`) outputting **Sense → Think → Act → Explain** JSON matching `schemas.py`.
  * HITL approval queue (`hitl_engine.py`), SQLite audit log (`audit_db.py`), and live WebSocket stream (`routes_stream.py`).

### Role 3 — Command Dashboard & Pitch Lead (`frontend/` + PPT)
* **Deliverables:**
  * Dark-mode React + TypeScript + Tailwind SOC Command Center (`CommandCenter.tsx`) with live Lab Wing topology, AI Explanation & Guardrail feed, HITL Approve/Reject drawer, and immutable audit log.
  * Built-in **Agent Active vs. Bypassed** toggle and **1-Click Red Team Demo Bar** for seamless live pitching.
  * 7-slide **Qualification PPT**, architecture diagrams, declared tools list, and 3-minute live demo script.

---

## 3. Phase-by-Phase Execution Roadmap

### Phase 0: Qualification Round (Pre-Hackathon / Immediate)
* [x] Run the OpenCode prompt to generate and build `./frontend/` (`npm run build` clean).
* [ ] Capture 3 high-contrast screenshots from `CommandCenter.tsx` (Normal State, Prompt Injection Blocked, and HITL Containment Approved) for prototype proof.
* [ ] Assemble the **7-Slide Qualification Deck**:
  1. **Title & Hook:** *Aegis Watchdog — Autonomous IoT Immune System for Campus Safety*
  2. **The Problem:** Why isolated threshold alerts miss coordinated campus attacks
  3. **Architecture (Sense → Think → Act → Explain):** End-to-end MQTT → Guardrail → LLM → HITL flow
  4. **3 Core Differentiators:** Cross-device correlation, Decoy Twin deception, Live Prompt-Injection defense
  5. **Demo Scenario (Without Agent vs. With Agent):** Visual walkthrough + UI prototype screenshots
  6. **Safety, Isolation & Compliance:** Isolated Docker lab, fake data, HITL gate, audit log, declared tools
  7. **24-Hour Execution & Team Split:** Role ownership and milestone timeline

### Phase 1: Foundation & Contract Sync (Hours 0–4)
* [ ] Confirm 1:1 schema alignment between `frontend/src/types/watchdog.ts` and `backend/app/schemas.py`.
* [ ] Complete the Role 1 contract gate in `sim/docs/phase1.md`, including MQTT topics, schemas, timing, controls, and the ACL matrix agreed with Role 2.
* [x] Bring up `docker-compose.yml` (authenticated Mosquitto + 5 separate simulated device services) and verify contract-valid live telemetry publishing.
* [x] Verify FastAPI WebSocket stream (`/api/stream`) emits `device_update`, `new_incident`, `new_approval`, and `audit_entry` events.

### Phase 2: Core Intelligence & Attack Wiring (Hours 4–12)
* [x] Connect Role 2's `POST /api/sim/trigger` endpoint to Role 1's MQTT attack-controller trigger and lifecycle-status contracts.
* [x] Test prompt-injection sanitization against poisoned `air_quality_01` payloads.
* [x] Test multi-device correlation rule (`smart_lock_01` unlock without `rfid_scanner_01` badge + `power_meter_01` port scan).
* [x] Verify `spoof_sensor` remains independently classifiable and does not contain prompt-injection instructions.

### Phase 3: End-to-End Integration (Hours 12–18)
* [x] Flip live mode with `VITE_USE_MOCK_DATA=false` in `frontend/.env.local`.
* [x] Verify 1-click **Approve Containment** path causes Role 2 to publish authenticated MQTT controls, receives truthful acknowledgements, updates `smart_lock_01` to `quarantined`, and activates `decoy_twin_01`.
* [x] Verify subsequent simulated attacker traffic is explicitly redirected to the Decoy Twin and increments actual capture counters without unlocking the quarantined lock.
* [x] Verify all actions persist in the SQLite audit store and render through the audit API/WebSocket contract.

### Phase 4: Hardening, Fallback & Pitch Rehearsal (Hours 18–24)
* [x] Complete organiser lab-isolation and MQTT security checks (`README.md`, Docker network inspection, credential hygiene, and positive/negative ACL tests).
* [ ] Record a 60-second backup video of a clean end-to-end run (in case venue Wi-Fi interrupts live LLM API calls).
* [ ] Rehearse the 3-minute live demo script:
  1. Show **Agent Bypassed** → trigger Coordinated Breach → show unmitigated compromise.
  2. Flip **Agent Active** → trigger Prompt Injection → highlight Guardrail block.
  3. Trigger Coordinated Breach → explain cross-device AI reasoning → click **Approve Containment** → show Decoy Twin activation & Audit Log.

---

## 4. Compressed Three-Phase MVP Execution

1. **[x] Phase A — Working IoT Lab:** contract baseline, authenticated Mosquitto, five device services, deterministic telemetry, health checks, credentials/ACLs, host endpoint, restart recovery, and isolation. Detailed evidence remains in `sim/docs/phase1.md` and `sim/docs/phase2.md`.
2. **[x] Phase B — Attacks and Containment:** MQTT controller, all three canonical attacks, persistent warning states, full reset, command acknowledgements, quarantine, Decoy activation, explicit routed probe, and capture counters.
3. **[x] Phase C — Integration and Demo:** FastAPI MQTT ingestion/correlation, prompt guardrail, incidents, HITL approvals, SQLite audit, REST/WebSocket, live frontend mode, focused E2E verifier, restart tests, and operating runbook.

**Deferred extras:** TLS, CCTV, transparent broker-level rerouting, exhaustive load testing, advanced CI, and optional metrics. Authentication, strict schemas, HITL, audit persistence, reset, and explicit simulated Decoy routing remain required and are implemented.

**Human-only open item:** named Role 1/Role 2 contract sign-off in `sim/contracts/signoff.md`; technical API/MQTT compatibility is demonstrated by the running backend and E2E tests.
