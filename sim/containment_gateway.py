"""Loopback-only L4 MQTT gateway with a small internal control API."""

import asyncio
from dataclasses import dataclass
import json
import os
import signal
from typing import Any

import paho.mqtt.client as mqtt

from sim.common.protocol import utc_now


@dataclass
class Session:
    client_writer: asyncio.StreamWriter
    upstream_writer: asyncio.StreamWriter
    target: str


class ContainmentGateway:
    def __init__(self) -> None:
        self.listen_host = os.getenv("GATEWAY_LISTEN_HOST", "127.0.0.1")
        self.listen_port = int(os.getenv("GATEWAY_LISTEN_PORT", "1884"))
        self.control_host = os.getenv("GATEWAY_CONTROL_HOST", "127.0.0.1")
        self.control_port = int(os.getenv("GATEWAY_CONTROL_PORT", "9000"))
        self.real_target = (
            os.getenv("GATEWAY_REAL_HOST", "127.0.0.1"),
            int(os.getenv("GATEWAY_REAL_PORT", "1883")),
        )
        self.decoy_target = (
            os.getenv("GATEWAY_DECOY_HOST", "127.0.0.1"),
            int(os.getenv("GATEWAY_DECOY_PORT", "1885")),
        )
        self.topic_prefix = os.getenv("SIM_TOPIC_PREFIX", "campus/lab1").rstrip("/")
        self.route = "real"
        self.sessions: dict[str, Session] = {}
        self.connection_count = 0
        self.reconnects = 0
        self.switch_count = 0
        self.real_bytes = 0
        self.decoy_bytes = 0
        self.last_switch_at: str | None = None
        self.incident_id: str | None = None
        self.last_error: str | None = None
        self._stop = asyncio.Event()
        self._mqtt = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="containment-gateway-status",
        )

    def target(self) -> tuple[str, int]:
        return self.decoy_target if self.route == "decoy" else self.real_target

    def snapshot(self) -> dict[str, Any]:
        host, port = self.target()
        return {
            "route_target": self.route,
            "upstream": f"{host}:{port}",
            "active_sessions": len(self.sessions),
            "connection_count": self.connection_count,
            "attacker_reconnects": self.reconnects,
            "switch_count": self.switch_count,
            "real_bytes": self.real_bytes,
            "decoy_bytes": self.decoy_bytes,
            "last_switch_at": self.last_switch_at or "NONE",
            "incident_id": self.incident_id or "NONE",
            "last_error": self.last_error or "NONE",
            "timestamp": utc_now(),
        }

    async def switch(self, target: str, incident_id: str | None = None) -> dict[str, Any]:
        if target not in {"real", "decoy"}:
            raise ValueError(f"unsupported route: {target}")
        changed = self.route != target
        self.route = target
        self.incident_id = incident_id
        self.last_switch_at = utc_now()
        self.last_error = None
        if changed:
            self.switch_count += 1
        disconnected = len(self.sessions)
        await self.disconnect_sessions()
        if incident_id == "RESET":
            self.connection_count = 0
            self.reconnects = 0
            self.switch_count = 0
            self.real_bytes = 0
            self.decoy_bytes = 0
        self.publish_status()
        print(
            f"[containment-gateway] route={target} disconnected={disconnected} "
            f"incident={incident_id or 'none'}",
            flush=True,
        )
        return {**self.snapshot(), "disconnected_sessions": disconnected}

    async def disconnect_sessions(self) -> None:
        sessions = list(self.sessions.values())
        self.sessions.clear()
        for session in sessions:
            session.client_writer.close()
            session.upstream_writer.close()
        for session in sessions:
            try:
                await session.client_writer.wait_closed()
            except Exception:
                pass
            try:
                await session.upstream_writer.wait_closed()
            except Exception:
                pass

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connection_count += 1
        if self.connection_count > 1:
            self.reconnects += 1
        session_id = f"session-{self.connection_count:04d}"
        target_name = self.route
        host, port = self.target()
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(host, port)
        except Exception as exc:
            self.last_error = str(exc)
            self.publish_status()
            writer.close()
            await writer.wait_closed()
            return

        self.sessions[session_id] = Session(writer, upstream_writer, target_name)
        self.publish_status()
        print(
            f"[containment-gateway] {session_id} -> {target_name} ({host}:{port})",
            flush=True,
        )

        async def pump(
            source: asyncio.StreamReader,
            destination: asyncio.StreamWriter,
        ) -> None:
            while data := await source.read(65536):
                destination.write(data)
                await destination.drain()
                if target_name == "decoy":
                    self.decoy_bytes += len(data)
                else:
                    self.real_bytes += len(data)

        tasks = [
            asyncio.create_task(pump(reader, upstream_writer)),
            asyncio.create_task(pump(upstream_reader, writer)),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            writer.close()
            upstream_writer.close()
            self.sessions.pop(session_id, None)
            self.publish_status()

    async def handle_http(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = 200
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            lines = header.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
            headers = {
                key.lower(): value.strip()
                for line in lines[1:]
                if ":" in line
                for key, value in [line.split(":", 1)]
            }
            length = int(headers.get("content-length", "0"))
            body = await reader.readexactly(length) if length else b""
            payload = json.loads(body or b"{}")

            if method == "GET" and path == "/status":
                result = self.snapshot()
            elif method == "POST" and path in {"/route/real", "/route/decoy"}:
                result = await self.switch(
                    path.rsplit("/", 1)[-1],
                    str(payload.get("incident_id") or "") or None,
                )
            elif method == "POST" and path == "/sessions/disconnect":
                disconnected = len(self.sessions)
                await self.disconnect_sessions()
                result = {**self.snapshot(), "disconnected_sessions": disconnected}
            else:
                status = 404
                result = {"detail": "not found"}
        except Exception as exc:
            status = 500
            result = {"detail": str(exc)}

        encoded = json.dumps(result).encode()
        reason = "OK" if status == 200 else "Error"
        writer.write(
            (
                f"HTTP/1.1 {status} {reason}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(encoded)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            + encoded
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    def publish_status(self) -> None:
        self._mqtt.publish(
            f"{self.topic_prefix}/gateway/status",
            json.dumps(self.snapshot()),
            qos=1,
            retain=True,
        )

    async def publish_status_loop(self) -> None:
        while not self._stop.is_set():
            self.publish_status()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1)
            except TimeoutError:
                pass

    async def run(self) -> None:
        self._mqtt.connect(self.real_target[0], self.real_target[1], 30)
        self._mqtt.loop_start()
        self._mqtt.publish(
            f"{self.topic_prefix}/environment",
            json.dumps({"environment": "REAL_LAB", "timestamp": utc_now()}),
            qos=1,
            retain=True,
        )
        tcp_server = await asyncio.start_server(
            self.handle_client, self.listen_host, self.listen_port
        )
        http_server = await asyncio.start_server(
            self.handle_http, self.control_host, self.control_port
        )
        print(
            f"[containment-gateway] tcp={self.listen_host}:{self.listen_port} "
            f"control={self.control_host}:{self.control_port}",
            flush=True,
        )
        status_task = asyncio.create_task(self.publish_status_loop())
        await self._stop.wait()
        tcp_server.close()
        http_server.close()
        await tcp_server.wait_closed()
        await http_server.wait_closed()
        status_task.cancel()
        await self.disconnect_sessions()
        self._mqtt.disconnect()
        self._mqtt.loop_stop()

    def stop(self) -> None:
        self._stop.set()


async def async_main() -> None:
    gateway = ContainmentGateway()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, gateway.stop)
    await gateway.run()


if __name__ == "__main__":
    asyncio.run(async_main())
