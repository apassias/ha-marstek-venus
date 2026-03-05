from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MarstekUdpClient


class MarstekCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: MarstekUdpClient, name: str, poll_interval_s: int) -> None:
        super().__init__(
            hass,
            name=f"Marstek Venus {name}",
            update_interval=timedelta(seconds=poll_interval_s),
        )
        self._client = client

    @property
    def client(self) -> MarstekUdpClient:
        return self._client

    async def _safe_call(self, method: str, params: dict[str, Any], retries: int = 1) -> dict[str, Any] | None:
        """
        Best-effort call.
        Returns result dict or None on any failure (timeout, parse error, etc.).
        """
        try:
            resp = await self._client.call(method, params, retries=retries)
            return resp.get("result") or {}
        except Exception:
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Refresh strategy:
        - Bat/Mode/Wifi are preferred (should be stable)
        - EM can timeout, so we keep the previous EM values if it fails
        - If everything fails, raise UpdateFailed
        """
        prev = self.data or {}

        bat = await self._safe_call("Bat.GetStatus", {"id": 0}, retries=1)
        mode = await self._safe_call("ES.GetMode", {"id": 0}, retries=1)
        wifi = await self._safe_call("Wifi.GetStatus", {"id": 0}, retries=1)

        # EM is known to timeout intermittently -> keep last good value
        em = await self._safe_call("EM.GetStatus", {"id": 0}, retries=1)
        if em is None:
            em = prev.get("em", {})

        if bat is None and mode is None and wifi is None and not prev:
            raise UpdateFailed("Device not responding")

        return {
            "src": prev.get("src"),
            "bat": bat if bat is not None else prev.get("bat", {}),
            "em": em,
            "mode": mode if mode is not None else prev.get("mode", {}),
            "wifi": wifi if wifi is not None else prev.get("wifi", {}),
        }

    async def async_set_mode_config(self, config: dict[str, Any]) -> None:
        # ES.SetMode expects params: {"id":0, "config": {...}}
        await self._client.call("ES.SetMode", {"id": 0, "config": config}, retries=1)
        await self.async_request_refresh()