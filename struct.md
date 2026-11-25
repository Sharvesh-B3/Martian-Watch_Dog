life-support-watchdog/
├── docker-compose.yml                  # Eclipse Mosquitto MQTT broker + isolated lab network
├── .env.example                        # MQTT_HOST, MQTT_PORT, LLM_API_KEY
├── README.md                           # Lab isolation notes, setup & declared tools
│
├── sim/                                # [Role 1] Multi-process IoT lab & Red Team
│   ├── run_lab.py                      # One command: broker + nodes + attack controller
│   ├── monitor.py                      # Human-readable MQTT security timeline
│   ├── broker/
│   │   └── mosquitto.conf
│   ├── common/
│   │   ├── mqtt_device.py              # Shared MQTT lifecycle, LWT, controls & metadata
│   │   ├── protocol.py                 # Stable topics, IDs, run/scenario helpers
│   │   └── settings.py                 # Seed, noise, broker and interval settings
│   ├── devices/
│   │   ├── smart_lock.py
│   │   ├── rfid_scanner.py
│   │   ├── air_quality.py
│   │   ├── power_meter.py
│   │   ├── cctv_camera.py              # Internal correlation evidence
│   │   └── decoy_twin.py               # Active attacker capture and timeline
│   ├── attacks/
│   │   ├── controller.py               # Holds scenarios and emits attacker probes
│   │   ├── scenarios.py                # Shared CLI/API attack definitions
│   │   ├── spoof_sensor.py
│   │   ├── coordinated_intrusion.py
│   │   ├── prompt_injection.py
│   │   └── red_team.py                 # Import-safe interactive control panel
│   └── tests/                           # Device, scenario, control and decoy tests
│
├── backend/                            # [Role 2 - YOU] FastAPI Agent & Guardrails
│   ├── pyproject.toml / requirements.txt
│   └── app/
│       ├── main.py                     # FastAPI app, CORS, lifespan, WebSocket/SSE router
│       ├── config.py                   # Environment config via Pydantic settings
│       ├── schemas.py                  # Shared data contracts (Telemetry, Incident, Approval)
│       ├── mqtt_client.py              # Subscribes to telemetry; publishes approved commands
│       ├── correlation_window.py       # Rolling 60s sliding window per zone/device
│       ├── guardrail.py                # Prompt-injection sanitizer & untrusted-data framing
│       ├── agent.py                    # Anomaly pre-filter + LLM reasoning (Sense -> Think -> Act)
│       ├── hitl_engine.py              # Human-in-the-Loop queue & decision enforcement
│       ├── audit_db.py                 # SQLite store for incidents, approvals & audit logs
│       └── api/
│           ├── routes_incidents.py     # GET /api/incidents, GET /api/audit-log, POST /api/sim/trigger
│           ├── routes_approvals.py   # GET /api/approvals, POST /api/approvals/{id}/decide
│           └── routes_stream.py      # Real-time WebSocket or SSE push to React
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
        │   ├── WingFloorplan.tsx       # Live zone/device cards (Normal / Alert / Quarantined)
        │   ├── IncidentFeed.tsx        # Plain-English AI reasoning & prompt-injection flags
        │   ├── ApprovalDrawer.tsx      # Human-in-the-Loop Approve / Reject controls
        │   └── AuditLogPanel.tsx       # Immutable action & operator decision log
        └── pages/
            └── CommandCenter.tsx
