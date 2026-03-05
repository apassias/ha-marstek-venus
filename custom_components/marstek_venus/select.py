from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, CONF_HOST, CONF_NAME, CONF_PORT, DOMAIN


MODES = ["Auto", "AI", "Manual", "Passive"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    devices = entry.options.get(CONF_DEVICES, [])
    coords = hass.data[DOMAIN][entry.entry_id]["coordinators"]

    entities = []
    for dev in devices:
        did = f"{dev[CONF_HOST]}:{dev[CONF_PORT]}"
        coord = coords.get(did)
        if not coord:
            continue
        name = dev.get(CONF_NAME) or dev[CONF_HOST]
        entities.append(MarstekModeSelect(coord, did, name))
    async_add_entities(entities)


class MarstekModeSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, device_id: str, dev_name: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_mode"
        self._attr_name = f"{dev_name} Mode"
        self._attr_options = MODES
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Marstek {dev_name}",
            "manufacturer": "Marstek",
            "model": "Venus",
        }

    @property
    def current_option(self):
        return (self.coordinator.data.get("mode") or {}).get("mode")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode_config({"mode": option})
