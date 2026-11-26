"""Real-time WebSocket event route."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.schemas import DeviceUpdateEvent

router = APIRouter(prefix="/api", tags=["stream"])


@router.websocket("/stream")
async def stream_events(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = websocket.app.state.hub
    queue = hub.subscribe()
    try:
        for device in websocket.app.state.bridge.device_snapshot():
            await websocket.send_json(
                DeviceUpdateEvent(device=device).model_dump(mode="json")
            )
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(queue)
