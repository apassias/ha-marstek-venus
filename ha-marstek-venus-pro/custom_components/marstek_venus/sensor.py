from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICES,
    CONF_ENERGY_UNITS_PER_WH,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DATA_COORDINATORS,
    DOMAIN,
    DEFAULT_ENERGY_UNITS_PER_WH,
)


@dataclass(frozen=True, kw_only=True)
class MarstekSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any], float], Any]
    energy_units_per_wh_aware: bool = False


SENSORS: tuple[MarstekSensorDescription, ...] = (
    # Battery
    MarstekSensorDescription(
        key="soc",
        name="Battery SOC",
        native_unit_of_measurement="%",
        value_fn=lambda d, s: d["bat"].get("soc"),
    ),
    MarstekSensorDescription(
        key="bat_temp",
        name="Battery Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d, s: d["bat"].get("bat_temp"),
    ),
    MarstekSensorDescription(
        key="bat_capacity_wh",
        name="Battery Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d, s: d["bat"].get("bat_capacity"),
    ),
    MarstekSensorDescription(
        key="rated_capacity_wh",
        name="Battery Rated Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d, s: d["bat"].get("rated_capacity"),
    ),

    # Meter power
    MarstekSensorDescription(
        key="phase_a_power",
        name="Phase A Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["em"].get("a_power"),
    ),
    MarstekSensorDescription(
        key="phase_b_power",
        name="Phase B Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["em"].get("b_power"),
    ),
    MarstekSensorDescription(
        key="phase_c_power",
        name="Phase C Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["em"].get("c_power"),
    ),
    MarstekSensorDescription(
        key="total_power",
        name="Total Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["em"].get("total_power"),
    ),

    # Mode powers
    MarstekSensorDescription(
        key="ongrid_power",
        name="On-grid Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["mode"].get("ongrid_power"),
    ),
    MarstekSensorDescription(
        key="offgrid_power",
        name="Off-grid Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d, s: d["mode"].get("offgrid_power"),
    ),

    # Wi-Fi diagnostics
    MarstekSensorDescription(
        key="wifi_ssid",
        name="WiFi SSID",
        value_fn=lambda d, s: d["wifi"].get("ssid"),
    ),
    MarstekSensorDescription(
        key="wifi_rssi",
        name="WiFi RSSI",
        native_unit_of_measurement="dBm",
        value_fn=lambda d, s: d["wifi"].get("rssi"),
    ),
    MarstekSensorDescription(
        key="wifi_ip",
        name="WiFi IP",
        value_fn=lambda d, s: d["wifi"].get("sta_ip"),
    ),

    # Energy dashboard sensors (kWh), based on firmware energy counters (units-per-Wh configurable)
    MarstekSensorDescription(
        key="grid_import_energy_kwh",
        name="Grid Import Energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        energy_units_per_wh_aware=True,
        value_fn=lambda d, units_per_wh: (d["em"].get("input_energy") / (units_per_wh * 1000.0))
        if d["em"].get("input_energy") is not None
        else None,
    ),
    MarstekSensorDescription(
        key="grid_export_energy_kwh",
        name="Grid Export Energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        energy_units_per_wh_aware=True,
        value_fn=lambda d, units_per_wh: (d["em"].get("output_energy") / (units_per_wh * 1000.0))
        if d["em"].get("output_energy") is not None
        else None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    devices = entry.options.get(CONF_DEVICES, [])
    units_per_wh = float(entry.options.get(CONF_ENERGY_UNITS_PER_WH, DEFAULT_ENERGY_UNITS_PER_WH))
    coords = hass.data[DOMAIN][entry.entry_id]["coordinators"]

    entities: list[SensorEntity] = []
    for dev in devices:
        did = f"{dev[CONF_HOST]}:{dev[CONF_PORT]}"
        coord = coords.get(did)
        if not coord:
            continue
        name = dev.get(CONF_NAME) or dev[CONF_HOST]
        for desc in SENSORS:
            entities.append(MarstekSensor(coord, did, name, desc, units_per_wh))
    async_add_entities(entities)


class MarstekSensor(CoordinatorEntity, SensorEntity):
    entity_description: MarstekSensorDescription

    def __init__(self, coordinator, device_id: str, dev_name: str, desc: MarstekSensorDescription, units_per_wh: float) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._units_per_wh = units_per_wh
        self._attr_unique_id = f"{device_id}_{desc.key}"
        self._attr_name = f"{dev_name} {desc.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Marstek {dev_name}",
            "manufacturer": "Marstek",
            "model": "Venus",
        }

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data, self._units_per_wh)
