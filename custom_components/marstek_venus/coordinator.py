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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Known-good methods on VenusE 3.0 from user tests:
            bat = await self._client.call("Bat.GetStatus", {"id": 0}, retries=1)
            em = await self._client.call("EM.GetStatus", {"id": 0}, retries=1)
            mode = await self._client.call("ES.GetMode", {"id": 0}, retries=1)
            wifi = await self._client.call("Wifi.GetStatus", {"id": 0}, retries=1)

            return {
                "src": bat.get("src") or em.get("src") or mode.get("src") or wifi.get("src"),
                "bat": bat.get("result") or {},
                "em": em.get("result") or {},
                "mode": mode.get("result") or {},
                "wifi": wifi.get("result") or {},
            }
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_mode_config(self, config: dict[str, Any]) -> None:
        # Marstek ES.SetMode expects params: {"id":0, "config": {...}}
        await self._client.call("ES.SetMode", {"id": 0, "config": config}, retries=1)
        await self.async_request_refresh()
