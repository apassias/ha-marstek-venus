from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .api import MarstekUdpClient
from .const import (
    CONF_CIDR,
    CONF_DEVICES,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_MODE,
    CONF_WIFI_MAC,
    DEFAULT_PORT,
    DOMAIN,
)


from .discovery import udp_broadcast_discover, udp_subnet_probe


class MarstekVenusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered = []
        self._scan_mode = "broadcast"
        self._scan_port = DEFAULT_PORT
        self._scan_cidr = "192.168.1.0/24"

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._scan_mode = user_input[CONF_SCAN_MODE]
            self._scan_port = int(user_input[CONF_PORT])
            self._scan_cidr = user_input.get(CONF_CIDR, self._scan_cidr)
            return await self.async_step_scan()

        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_MODE, default="broadcast"): vol.In(["broadcast", "subnet"]),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_CIDR, default="192.168.1.0/24"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_scan(self, user_input=None):
        return self.async_show_progress(step_id="scan", progress_action="scan")

    async def async_step_scan_progress(self, user_input=None):
        if self._scan_mode == "broadcast":
            self._discovered = await udp_broadcast_discover(port=self._scan_port, timeout=2.0)
        else:
            self._discovered = await udp_subnet_probe(cidr=self._scan_cidr, port=self._scan_port)

        return await self.async_step_pick()

    async def async_step_pick(self, user_input=None):
        errors = {}

        if user_input is not None:
            selected = user_input.get("devices", [])
            manual_host = user_input.get("manual_host")

            devices = []
            by_key = {f"{d.host}:{d.port}": d for d in self._discovered}

            for key in selected:
                d = by_key.get(key)
                if not d:
                    continue
                name = d.src or d.host
                devices.append({CONF_HOST: d.host, CONF_PORT: d.port, CONF_NAME: name, CONF_WIFI_MAC: d.wifi_mac})

            if manual_host:
                try:
                    client = MarstekUdpClient(host=manual_host, port=self._scan_port, timeout=3.0)
                    await client.async_connect()
                    wifi = await client.call("Wifi.GetStatus", {"id": 0}, retries=1)
                    bat = await client.call("Bat.GetStatus", {"id": 0}, retries=1)
                    await client.async_close()

                    name = bat.get("src") or manual_host
                    wifi_mac = (wifi.get("result") or {}).get("wifi_mac")
                    devices.append({CONF_HOST: manual_host, CONF_PORT: self._scan_port, CONF_NAME: name, CONF_WIFI_MAC: wifi_mac})
                except Exception:
                    errors["base"] = "cannot_connect"

            if not devices and not errors:
                errors["base"] = "no_selection"

            if not errors:
                await self.async_set_unique_id("marstek_venus_multi")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Marstek Venus (Local UDP)",
                    data={},
                    options={CONF_DEVICES: devices},
                )

        opts = {}
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
            opts[key] = label

        schema = vol.Schema(
            {
                vol.Optional("devices"): cv.multi_select(opts),
                vol.Optional("manual_host"): str,
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema, errors=errors)


async def async_get_options_flow(config_entry):
    from .options_flow import OptionsFlowHandler
    return OptionsFlowHandler(config_entry)
