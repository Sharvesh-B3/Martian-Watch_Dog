# Target Repository Structure

This is the agreed target structure. Existing proof-of-concept aggregators may remain during migration, but they are retired only after their replacement phase gates pass.

```text
life-support-watchdog/
├── docker-compose.yml                  # Broker, 5 devices, attack controller and FastAPI backend
├── .dockerignore                       # Keeps secrets, caches, tests and large local output out of images
├── .env.example                        # Non-secret MQTT, timing, simulator, backend & frontend settings
├── .gitignore                          # Excludes local secrets, generated password DBs and runtime data
├── README.md                           # Setup, credentials, isolation, operation, reset & declared tools
├── plan.md                             # Overall hackathon roadmap + Role 1 phase index
├── struct.md                           # This target structure
│
├── sim/                                # [Role 1 - YOU] Isolated IoT lab, attacks & actuators
│   ├── Dockerfile                      # Shared image used by Role 1 Python services
│   ├── README.md                       # Role 1 setup, operation, verification & current limits
│   ├── .env.example                    # Non-secret Role 1 account names and optional seed settings
│   ├── setup_credentials.py            # Atomic 8-account generation via official Docker tool
│   ├── verify_lab.py                    # Safe live telemetry/auth/subscription verification
│   ├── requirements.txt                # Pinned simulator MQTT/schema runtime dependencies
│   ├── requirements-dev.txt            # Local-only validation dependency pins
│   ├── docs/
│   │   ├── phase1.md                   # Contract freeze and integration agreement
│   │   ├── phase2.md                   # Isolated MQTT lab and five-device topology
│   │   ├── phase3.md                   # Attack scenarios and MQTT trigger controller
│   │   ├── phase4.md                   # HITL containment and Decoy Twin routing
│   │   ├── phase5.md                   # Hardening, automated verification and observability
│   │   └── phase6.md                   # End-to-end integration, runbook and handoff
│   ├── contracts/
│   │   ├── README.md                   # Contract decisions, semantics, ownership & sign-off
│   │   ├── signoff.md                  # Explicit Role 1/Role 2 review and approval gate
│   │   ├── role2_handoff.md            # Derived API/HITL-to-MQTT integration flow
│   │   ├── poc_inventory.md            # Current proof-of-concept mapping and migration gaps
│   │   ├── mqtt_topics.md              # Topic owners, QoS, retain policy and ACL matrix
│   │   ├── telemetry.schema.json       # Strict versioned telemetry envelope + device metrics
│   │   ├── presence.schema.json        # Online fact and offline Last Will
│   │   ├── attack_trigger.schema.json  # Three public attack trigger values
│   │   ├── attack_status.schema.json   # Attack and reset lifecycle
│   │   ├── injection.schema.json       # Private controller-to-device scenario evidence
│   │   ├── control.schema.json         # Backend quarantine/decoy/restore/reset commands
│   │   ├── control_ack.schema.json     # Per-device command outcomes
│   │   ├── decoy_input.schema.json     # Private explicitly routed hostile content
│   │   ├── decoy_event.schema.json     # Safe Decoy activation/capture/restore facts
│   │   ├── ground_truth.schema.json    # Observer-only expected evidence
│   │   ├── validate_examples.py        # Draft 2020-12 schema and fixture gate
│   │   └── examples/                   # Valid and intentionally invalid contract fixtures
│   ├── broker/
│   │   ├── mosquitto.conf              # Authenticated broker configuration
│   │   ├── acl                          # Tracked least-privilege topic rules
│   │   ├── entrypoint.sh                # Copies secrets to private mosquitto-owned runtime files
│   │   └── generated/                   # Ignored; local passwd database from setup script
│   ├── .env                             # Ignored; generated local MQTT client passwords
│   ├── common/
│   │   ├── config.py                   # Environment validation; no embedded credentials
│   │   ├── healthcheck.py              # Device publish/connect freshness health gate
│   │   ├── mqtt.py                     # MQTT 3.1.1 auth, retry, presence and graceful shutdown
│   │   ├── messages.py                 # Schema validation, IDs and timestamps
│   │   └── state.py                    # Thread-safe device model separated from transport
│   ├── devices/                        # Separate Compose service and MQTT client per device
│   │   ├── smart_lock.py               # smart_lock_01
│   │   ├── rfid_scanner.py             # rfid_scanner_01
│   │   ├── air_quality.py              # air_quality_01
│   │   ├── power_meter.py              # power_meter_01
│   │   └── decoy_twin.py               # decoy_twin_01; standby/active/capture behavior
│   ├── attacks/
│   │   ├── controller.py               # Consumes signed MQTT scenario triggers
│   │   ├── trigger_cli.py              # Publishes the same trigger contract for operators
│   │   └── red_team.py                 # Retained legacy proof-of-concept menu
│   ├── monitor.py                      # Read-only observer; never the Role 2 detector
│   └── tests/
│       ├── unit/                       # Physics, schemas, state transitions and idempotency
│       ├── integration/                # Broker, devices, scenarios, controls and reset
│       ├── security/                   # ACL denial, credentials and network-isolation checks
│       └── fixtures/                   # Stable deterministic test data
│
├── backend/                            # [Role 2 compressed MVP] FastAPI + MQTT + HITL
│   ├── Dockerfile                      # Non-root Python 3.13 backend image
│   ├── requirements.txt                # FastAPI, Uvicorn, Paho and schema dependencies
│   └── app/
│       ├── __init__.py
│       └── main.py                     # MQTT ingest/correlation/guardrail, REST, WS, HITL & SQLite audit
│
└── frontend/                           # [Role 3] React + Vite SOC Dashboard
    ├── package.json
    ├── index.html
    └── src/
        ├── App.tsx
        ├── types/
        │   └── watchdog.ts             # TypeScript interfaces matching backend/app/schemas.py
        ├── api/
        │   └── client.ts               # REST helpers + live WebSocket/SSE subscription
        ├── components/
        │   ├── WingFloorplan.tsx       # Live zone/device cards
        │   ├── IncidentFeed.tsx        # AI explanation & prompt-injection flags
        │   ├── ApprovalDrawer.tsx      # Human-in-the-Loop Approve / Reject controls
        │   └── AuditLogPanel.tsx       # Immutable action & operator decision log
        └── pages/
            └── CommandCenter.tsx
```

## Locked Role 1 architecture

- The core simulator has exactly five devices; CCTV is not part of the target topology.
- Each device runs as a separate Compose service with a unique MQTT client identity.
- Role 2's API publishes scenario requests to the MQTT attack controller; it does not import Role 1 code or launch it as a subprocess.
- Decoy traffic routing is an explicit simulation and must be labelled accordingly.
- Mosquitto rejects anonymous access and enforces account/topic ACLs.
- Exact topic strings, QoS, retain behavior, timing values, and message fields are frozen collaboratively in Phase 1 rather than inferred from this tree.
