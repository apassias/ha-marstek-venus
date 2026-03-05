from __future__ import annotations

import asyncio
import json
import socket
from typing import Any


class MarstekUdpClient:
    """Async UDP JSON-RPC client."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._loop = asyncio.get_running_loop()
        self._sock: socket.socket | None = None
        self._id = 0  # must be int
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def async_connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        self._sock = sock

    async def async_close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    async def call(self, method: str, params: dict[str, Any], *, retries: int = 1) -> dict[str, Any]:
        """Call a method. Retries on timeout."""
        last_err: Exception | None = None
        for _ in range(retries + 1):
            try:
                return await self._call_once(method, params)
            except TimeoutError as e:
                last_err = e
                await asyncio.sleep(0.05)
            except Exception as e:
                # Do not retry unknown errors by default
                raise
        assert last_err is not None
        raise last_err

    async def _call_once(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._sock is None:
            await self.async_connect()

        async with self._lock:
            self._id += 1
            req_id = self._id

            payload = {"id": req_id, "method": method, "params": params}
            data = json.dumps(payload).encode("utf-8")
            await self._loop.sock_sendto(self._sock, data, (self._host, self._port))

            deadline = self._loop.time() + self._timeout
            while True:
                remaining = deadline - self._loop.time()
                if remaining <= 0:
                    raise TimeoutError(f"Timeout waiting response for {method} on {self._host}:{self._port}")

                resp_bytes = await asyncio.wait_for(self._loop.sock_recv(self._sock, 65535), timeout=remaining)
                resp = json.loads(resp_bytes.decode("utf-8", errors="replace"))

                if resp.get("id") != req_id:
                    continue

                err = resp.get("error")
                if err:
                    raise RuntimeError(f"Marstek API error: {err}")
                return resp
