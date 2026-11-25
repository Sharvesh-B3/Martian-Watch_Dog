"""FastAPI application for the Aegis Watchdog backend."""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.agent import Agent
from backend.app.api.routes_agent import router as agent_router
from backend.app.api.routes_approvals import router as approvals_router
from backend.app.api.routes_incidents import router as incidents_router
from backend.app.api.routes_stream import router as stream_router
from backend.app.audit_db import AuditDB
from backend.app.config import get_settings
from backend.app.correlation_window import CorrelationWindow
from backend.app.hitl_engine import HitlEngine
from backend.app.llm_client import LLMUnavailable, build_llm_client
from backend.app.mqtt_client import MqttBridge
from backend.app.pipeline import run_pipeline
from backend.app.stream_hub import StreamHub

logger = logging.getLogger(__name__)

settings = get_settings()
hub = StreamHub()
window = CorrelationWindow(settings.WINDOW_SECONDS)
bridge = MqttBridge(settings, hub, window)
db = AuditDB(settings.DB_PATH)
agent = Agent(db, bridge, hub, build_llm_client(settings))
hitl = HitlEngine(db, bridge, hub)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MQTT telemetry ingestion and bind the WebSocket event loop."""
    app.state.settings = settings
    app.state.hub = hub
    app.state.window = window
    app.state.bridge = bridge
    app.state.db = db
    app.state.agent = agent
    app.state.hitl = hitl
    loop = asyncio.get_running_loop()
    pipeline_requested = asyncio.Event()

    def schedule_pipeline() -> None:
        loop.call_soon_threadsafe(pipeline_requested.set)

    async def pipeline_worker() -> None:
        while True:
            await pipeline_requested.wait()
            # Collect a short burst of cross-device MQTT frames before
            # evaluating, preventing a coordinated scenario from first being
            # emitted as an isolated port scan.
            await asyncio.sleep(0.15)
            pipeline_requested.clear()
            try:
                await asyncio.to_thread(run_pipeline, app)
            except LLMUnavailable as exc:
                logger.error("MQTT-triggered reasoning unavailable: %s", exc)
            except Exception:
                logger.exception("MQTT-triggered pipeline failed")

    hub.bind_loop(loop)
    bridge.set_pipeline_callback(schedule_pipeline)
    worker = asyncio.create_task(
        pipeline_worker(), name="watchdog-telemetry-pipeline"
    )
    bridge_started = False
    try:
        bridge.start()
        bridge_started = True
        yield
    finally:
        bridge.set_pipeline_callback(None)
        if bridge_started:
            bridge.stop()
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        hub.bind_loop(None)
        db.close()


app = FastAPI(
    title="Aegis Watchdog Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)
app.include_router(approvals_router)
app.include_router(stream_router)
app.include_router(agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
