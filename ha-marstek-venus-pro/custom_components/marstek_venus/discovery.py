from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredDevice:
    host: str
    port: int
    src: str | None = None
    wifi_mac: str | None = None
    ssid: str | None = None
    rssi: int | None = None
    sta_ip: str | None = None


def _looks_like_venus(src: str | None) -> bool:
    return bool(src) and src.lower().startswith("venuse") or bool(src) and src.lower().startswith("venusc")


async def udp_broadcast_discover(port: int, timeout: float = 2.0) -> list[DiscoveredDevice]:
    """Broadcast Marstek.GetDevice (params ble_mac='0') and collect replies."""
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", 0))

        req = {"id": 1, "method": "Marstek.GetDevice", "params": {"ble_mac": "0"}}
        data = json.dumps(req).encode("utf-8")

        await loop.sock_sendto(sock, data, ("255.255.255.255", port))

        devices: dict[str, DiscoveredDevice] = {}
        end = loop.time() + timeout

        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                break
            try:
                payload, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=remaining)
            except asyncio.TimeoutError:
                break

            host = addr[0]
            try:
                resp = json.loads(payload.decode("utf-8", errors="replace"))
            except Exception:
                continue

            src = resp.get("src")
            if not _looks_like_venus(src):
                continue

            result = resp.get("result") or {}
            devices[f"{host}:{port}"] = DiscoveredDevice(
                host=host,
                port=port,
                src=src,
                wifi_mac=result.get("wifi_mac"),
                ssid=result.get("ssid"),
                rssi=result.get("rssi"),
                sta_ip=result.get("sta_ip") or result.get("ip"),
            )

        return sorted(devices.values(), key=lambda d: d.host)
    finally:
        sock.close()


async def udp_subnet_probe(
    cidr: str,
    port: int,
    timeout_per_host: float = 0.35,
    concurrency: int = 120,
) -> list[DiscoveredDevice]:
    """Fallback scan: probe each IP using Wifi.GetStatus."""
    net = ipaddress.ip_network(cidr, strict=False)
    sem = asyncio.Semaphore(concurrency)

    async def probe_ip(ip: str) -> DiscoveredDevice | None:
        async with sem:
            loop = asyncio.get_running_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setblocking(False)
                sock.bind(("0.0.0.0", 0))
                req = {"id": 1, "method": "Wifi.GetStatus", "params": {"id": 0}}
                data = json.dumps(req).encode("utf-8")
                await loop.sock_sendto(sock, data, (ip, port))
                try:
                    payload = await asyncio.wait_for(loop.sock_recv(sock, 65535), timeout=timeout_per_host)
                except asyncio.TimeoutError:
                    return None

                resp = json.loads(payload.decode("utf-8", errors="replace"))
                src = resp.get("src")
                if not _looks_like_venus(src):
                    return None
                result = resp.get("result") or {}
                return DiscoveredDevice(
                    host=ip,
                    port=port,
                    src=src,
                    wifi_mac=result.get("wifi_mac"),
                    ssid=result.get("ssid"),
                    rssi=result.get("rssi"),
                    sta_ip=result.get("sta_ip"),
                )
            except Exception:
                return None
            finally:
                sock.close()

    found = [d for d in await asyncio.gather(*[probe_ip(str(ip)) for ip in net.hosts()]) if d is not None]
    uniq = {(d.host, d.port): d for d in found}
    return sorted(uniq.values(), key=lambda d: d.host)
