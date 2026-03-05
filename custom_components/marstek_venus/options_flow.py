from __future__ import annotations

import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .api import MarstekUdpClient
from .const import (
    CONF_CIDR,
    CONF_DEVICES,
    CONF_ENERGY_UNITS_PER_WH,
    CONF_HOST,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SCAN_MODE,
    CONF_WIFI_MAC,
    DEFAULT_ENERGY_UNITS_PER_WH,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
)
from .discovery import udp_broadcast_discover, udp_subnet_probe


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._discovered = []
        self._scan_mode = "broadcast"
        self._scan_port = DEFAULT_PORT
        self._scan_cidr = "192.168.1.0/24"

        self._scan_task: asyncio.Task | None = None

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self._scan_mode = user_input[CONF_SCAN_MODE]
            self._scan_port = int(user_input[CONF_PORT])
            self._scan_cidr = user_input.get(CONF_CIDR, self._scan_cidr)
            return await self.async_step_scan()

        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_MODE, default="broadcast"): vol.In(["broadcast", "subnet"]),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_CIDR, default=self._scan_cidr): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_scan(self, user_input=None):
        """
        Home Assistant 2024.8+ requires async_show_progress to be called with a progress_task.
        """
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(self._async_do_scan())

        if not self._scan_task.done():
            return self.async_show_progress(
                progress_action="scan",
                progress_task=self._scan_task,
            )

        return self.async_show_progress_done(next_step_id="edit")

    async def _async_do_scan(self):
        if self._scan_mode == "broadcast":
            self._discovered = await udp_broadcast_discover(port=self._scan_port, timeout=2.0)
        else:
            self._discovered = await udp_subnet_probe(cidr=self._scan_cidr, port=self._scan_port)

    async def async_step_edit(self, user_input=None):
        errors = {}
        existing = self._entry.options.get(CONF_DEVICES, [])
        poll_interval = int(self._entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        energy_units_per_wh = float(self._entry.options.get(CONF_ENERGY_UNITS_PER_WH, DEFAULT_ENERGY_UNITS_PER_WH))

        if user_input is not None:
            keep = set(user_input.get("keep_existing", []))
            add = set(user_input.get("add_devices", []))
            manual_host = user_input.get("manual_host")

            poll_interval = int(user_input.get(CONF_POLL_INTERVAL, poll_interval))
            energy_units_per_wh = float(user_input.get(CONF_ENERGY_UNITS_PER_WH, energy_units_per_wh))

            new_devices = [d for d in existing if f"{d[CONF_HOST]}:{d[CONF_PORT]}" in keep]

            by_key = {f"{d.host}:{d.port}": d for d in self._discovered}
            for key in add:
                d = by_key.get(key)
                if not d:
                    continue
                name = d.src or d.host
                new_devices.append(
                    {
                        CONF_HOST: d.host,
                        CONF_PORT: d.port,
                        CONF_NAME: name,
                        CONF_WIFI_MAC: d.wifi_mac,
                    }
                )

            if manual_host:
                try:
                    client = MarstekUdpClient(host=manual_host, port=self._scan_port, timeout=3.0)
                    await client.async_connect()
                    wifi = await client.call("Wifi.GetStatus", {"id": 0}, retries=1)
                    bat = await client.call("Bat.GetStatus", {"id": 0}, retries=1)
                    await client.async_close()
                    name = bat.get("src") or manual_host
                    wifi_mac = (wifi.get("result") or {}).get("wifi_mac")
                    new_devices.append(
                        {
                            CONF_HOST: manual_host,
                            CONF_PORT: self._scan_port,
                            CONF_NAME: name,
                            CONF_WIFI_MAC: wifi_mac,
                        }
                    )
                except Exception:
                    errors["base"] = "cannot_connect"

            # de-dup
            dedup = {}
            for d in new_devices:
                dedup[f"{d[CONF_HOST]}:{d[CONF_PORT]}"] = d
            new_devices = list(dedup.values())

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_DEVICES: new_devices,
                        CONF_POLL_INTERVAL: poll_interval,
                        CONF_ENERGY_UNITS_PER_WH: energy_units_per_wh,
                    },
                )

        existing_opts = {
            f"{d[CONF_HOST]}:{d[CONF_PORT]}": f"{d.get(CONF_NAME) or d[CONF_HOST]} ({d[CONF_HOST]}:{d[CONF_PORT]})"
            for d in existing
        }

        discovered_opts = {}
        for d in self._discovered:
            key = f"{d.host}:{d.port}"
            extras = []
            if d.src:
                extras.append(d.src)
            if d.ssid:
                extras.append(f"ssid={d.ssid}")
            if d.rssi is not None:
                extras.append(f"rssi={d.rssi}")
            if d.wifi_mac:
                extras.append(f"mac={d.wifi_mac}")
            label = key + (" (" + ", ".join(extras) + ")" if extras else "")
            discovered_opts[key] = label

        schema = vol.Schema(
            {
                vol.Optional("keep_existing"): cv.multi_select(existing_opts),
                vol.Optional("add_devices"): cv.multi_select(discovered_opts),
                vol.Optional("manual_host"): str,
                vol.Optional(CONF_POLL_INTERVAL, default=poll_interval): vol.All(int, vol.Range(min=10, max=3600)),
                vol.Optional(CONF_ENERGY_UNITS_PER_WH, default=energy_units_per_wh): vol.All(
                    float, vol.Range(min=0.1, max=10000.0)
                ),
            }
        )
        return self.async_show_form(step_id="edit", data_schema=schema, errors=errors)