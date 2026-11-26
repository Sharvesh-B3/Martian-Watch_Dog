# Aegis Watchdog — 24-Hour Hackathon & Qualification Plan

**Track:** Track 3 — Life-Support Watchdog (IoT Security)  
**Concept:** A physics-aware, cross-device **IoT Immune System** for campus infrastructure that detects multi-sensor intrusions, neutralizes prompt-injection payloads, and enforces Human-in-the-Loop (HITL) containment with active **Decoy Twin** deception.

---

## 1. What Makes Us Stand Out (Judge Differentiators)

1. **Cross-Device Correlation (Not Single-Sensor Thresholds):**
   Correlates telemetry across a 60-second rolling window for an entire simulated **Campus Lab Wing** (`smart_lock_01`, `rfid_scanner_01`, `air_quality_01`, `power_meter_01`, and `decoy_twin_01`). Detects coordinated physical + cyber breaches (e.g., door unlocking without a matching RFID scan right after outbound port scanning).
2. **Active Deception ("Decoy Twin" Containment):**
   Instead of merely raising an alert, approved containment locks down physical access, disconnects the attacker TCP session and switches the same MQTT gateway endpoint from the real broker to an isolated **Decoy Twin** broker with independently measured route and byte counters.
3. **Live Prompt-Injection Defense (Rule 8 Showcase):**
   Sanitizes untrusted sensor payloads before LLM reasoning and demonstrates live interception of adversarial prompt injections hidden inside telemetry metadata (`"IGNORE PREVIOUS INSTRUCTIONS..."`).
4. **Human-in-the-Loop + Immutable Audit Trail (Rule 7 Compliance):**
   Low-risk mitigations (topic rate-limiting) run automatically; high-risk physical/network quarantine requires 1-click operator approval with full cryptographic/timestamped logging.

---

## 2. Team Role Split & Deliverables

### Role 1 — IoT Lab & Red Team Lead (`sim/`)
* **Deliverables:**
  * Isolated Docker Compose setup with **Eclipse Mosquitto** MQTT broker (`sim/broker/mosquitto.conf`) and zero external network bridges.
  * 5 dashboard Python IoT nodes (`smart_lock.py`, `rfid_scanner.py`, `air_quality.py`, `power_meter.py`, `decoy_twin.py`) plus an internal CCTV evidence node, each running independently and publishing realistic synthetic telemetry.
  * 3 automated Red Team attack scripts (`spoof_sensor.py`, `coordinated_intrusion.py`, `prompt_injection.py`) triggerable via CLI or API.
* **Key Check:** Verify lab isolation and 100% synthetic data for organiser lab inspection.

### Role 2 — AI Agent & Guardrails Architect (`backend/`)
* **Deliverables:**
  * FastAPI backend (`app/main.py`) ingesting MQTT streams into a 60s sliding correlation window (`correlation_window.py`).
  * **Prompt-Injection Guardrail** (`guardrail.py`) stripping/flagging adversarial instructions in untrusted sensor fields.
  * Anomaly pre-filter + structured LLM reasoning (`agent.py`) outputting **Sense → Think → Act → Explain** JSON matching `schemas.py`.
  * HITL approval queue (`hitl_engine.py`), SQLite audit log (`audit_db.py`), and live WebSocket stream (`routes_stream.py`).

### Role 3 — Command Dashboard & Pitch Lead (`frontend/` + PPT) **[YOU]**
* **Deliverables:**
  * Dark-mode React + TypeScript + Tailwind SOC Command Center (`CommandCenter.tsx`) with live Lab Wing topology, AI Explanation & Guardrail feed, HITL Approve/Reject drawer, and immutable audit log.
  * Built-in **Agent Active vs. Bypassed** toggle and **1-Click Red Team Demo Bar** for seamless live pitching.
  * 7-slide **Qualification PPT**, architecture diagrams, declared tools list, and 3-minute live demo script.

---

## 3. Phase-by-Phase Execution Roadmap

### Phase 0: Qualification Round (Pre-Hackathon / Immediate)
* [ ] Run the OpenCode prompt to generate and build `./frontend/` (`npm run build` clean).
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
* [ ] Bring up `docker-compose.yml` (Mosquitto broker + 5 simulated devices) and verify live telemetry publishing.
* [ ] Verify FastAPI WebSocket stream (`/api/stream`) emits `device_update`, `new_incident`, `new_approval`, and `audit_entry` events.

### Phase 2: Core Intelligence & Attack Wiring (Hours 4–12)
* [ ] Connect Role 1's 3 attack scripts to Role 2's `POST /api/sim/trigger` endpoint.
* [ ] Test prompt-injection sanitization against poisoned `air_quality_01` payloads.
* [ ] Test multi-device correlation rule (`smart_lock_01` unlock without `rfid_scanner_01` badge + `power_meter_01` port scan).

### Phase 3: End-to-End Integration (Hours 12–18)
* [ ] Flip `USE_MOCK_DATA = false` in `frontend/src/api/client.ts`.
* [ ] Verify 1-click **Approve Containment** in `ApprovalDrawer.tsx` updates `smart_lock_01` to `quarantined` and activates `decoy_twin_01` via MQTT command publish.
* [ ] Verify all actions persist in `audit_db.py` and render in `AuditLogPanel.tsx`.

### Phase 4: Hardening, Fallback & Pitch Rehearsal (Hours 18–24)
* [ ] Complete organiser lab-isolation check (`README.md` + Docker network inspection).
* [ ] Record a 60-second backup video of a clean end-to-end run (in case venue Wi-Fi interrupts live LLM API calls).
* [ ] Rehearse the 3-minute live demo script:
  1. Show **Agent Bypassed** → trigger Coordinated Breach → show unmitigated compromise.
  2. Flip **Agent Active** → trigger Prompt Injection → highlight Guardrail block.
  3. Trigger Coordinated Breach → explain cross-device AI reasoning → click **Approve Containment** → show Decoy Twin activation & Audit Log.
