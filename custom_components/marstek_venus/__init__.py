from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .api import MarstekUdpClient
from .coordinator import MarstekCoordinator
from .const import (
    ATTR_CD_TIME,
    ATTR_DEVICE_ID,
    ATTR_MODE,
    ATTR_POWER,
    ATTR_SLOTS,
    CONF_DEVICES,
    CONF_ENERGY_UNITS_PER_WH,
    CONF_HOST,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    DATA_CLIENTS,
    DATA_COORDINATORS,
    DEFAULT_ENERGY_UNITS_PER_WH,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_SET_MANUAL,
    SERVICE_SET_MODE,
    SERVICE_SET_PASSIVE,
)


def _device_id(dev: dict) -> str:
    return f"{dev[CONF_HOST]}:{dev[CONF_PORT]}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {DATA_CLIENTS: {}, DATA_COORDINATORS: {}})

    devices = entry.options.get(CONF_DEVICES, [])
    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    await _setup_devices(hass, entry, devices, poll_interval)
    _register_services(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _setup_devices(hass: HomeAssistant, entry: ConfigEntry, devices: list[dict], poll_interval: int) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    clients: dict[str, MarstekUdpClient] = store[DATA_CLIENTS]
    coordinators: dict[str, MarstekCoordinator] = store[DATA_COORDINATORS]

    # add new
    for dev in devices:
        did = _device_id(dev)
        if did in coordinators:
            continue

        host = dev[CONF_HOST]
        port = int(dev[CONF_PORT])
        name = dev.get(CONF_NAME) or host

        client = MarstekUdpClient(host=host, port=port, timeout=5.0)
        await client.async_connect()

        coord = MarstekCoordinator(hass=hass, client=client, name=name, poll_interval_s=poll_interval)
        await coord.async_config_entry_first_refresh()

        clients[did] = client
        coordinators[did] = coord

        # device registry
        device_reg = dr.async_get(hass)
        device_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, did)},
            name=f"Marstek {name}",
            manufacturer="Marstek",
            model="Venus",
        )

    # remove deleted
    keep_ids = {_device_id(d) for d in devices}
    for did in list(coordinators.keys()):
        if did not in keep_ids:
            coordinators.pop(did)
            client = clients.pop(did, None)
            if client:
                await client.async_close()


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    key = f"{DOMAIN}_{entry.entry_id}_services"
    if hass.data[DOMAIN].get(key):
        return
    hass.data[DOMAIN][key] = True

    async def _coord(device_id: str) -> MarstekCoordinator:
        return hass.data[DOMAIN][entry.entry_id][DATA_COORDINATORS][device_id]

    async def handle_set_mode(call: ServiceCall) -> None:
        device_id = call.data[ATTR_DEVICE_ID]
        mode = call.data[ATTR_MODE]
        coord = await _coord(device_id)
        await coord.async_set_mode_config({"mode": mode})

    async def handle_set_passive(call: ServiceCall) -> None:
        device_id = call.data[ATTR_DEVICE_ID]
        power = int(call.data[ATTR_POWER])
        cd_time = int(call.data.get(ATTR_CD_TIME, 0))
        coord = await _coord(device_id)
        await coord.async_set_mode_config({"mode": "Passive", "passive_cfg": {"power": power, "cd_time": cd_time}})

    async def handle_set_manual(call: ServiceCall) -> None:
        device_id = call.data[ATTR_DEVICE_ID]
        slots = call.data[ATTR_SLOTS]
        coord = await _coord(device_id)
        await coord.async_set_mode_config({"mode": "Manual", "manual_cfg": slots})

    hass.services.async_register(DOMAIN, SERVICE_SET_MODE, handle_set_mode)
    hass.services.async_register(DOMAIN, SERVICE_SET_PASSIVE, handle_set_passive)
    hass.services.async_register(DOMAIN, SERVICE_SET_MANUAL, handle_set_manual)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        store = hass.data[DOMAIN].pop(entry.entry_id, {})
        for client in store.get(DATA_CLIENTS, {}).values():
            await client.async_close()
    return unload_ok
