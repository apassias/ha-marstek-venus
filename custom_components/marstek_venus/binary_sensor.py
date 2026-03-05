from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, CONF_HOST, CONF_NAME, CONF_PORT, DATA_COORDINATORS, DOMAIN


@dataclass(frozen=True, kw_only=True)
class MarstekBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY: tuple[MarstekBinaryDescription, ...] = (
    MarstekBinaryDescription(key="charging", name="Charging", value_fn=lambda d: d["bat"].get("charg_flag")),
    MarstekBinaryDescription(key="discharging", name="Discharging", value_fn=lambda d: d["bat"].get("dischrg_flag")),
    MarstekBinaryDescription(key="ct_connected", name="CT Connected", value_fn=lambda d: bool(d["em"].get("ct_state"))),
)


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
        for desc in BINARY:
            entities.append(MarstekBinarySensor(coord, did, name, desc))
    async_add_entities(entities)


class MarstekBinarySensor(CoordinatorEntity, BinarySensorEntity):
    entity_description: MarstekBinaryDescription

    def __init__(self, coordinator, device_id: str, dev_name: str, desc: MarstekBinaryDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._attr_unique_id = f"{device_id}_{desc.key}"
        self._attr_name = f"{dev_name} {desc.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Marstek {dev_name}",
            "manufacturer": "Marstek",
            "model": "Venus",
        }

    @property
    def is_on(self):
        return self.entity_description.value_fn(self.coordinator.data)
