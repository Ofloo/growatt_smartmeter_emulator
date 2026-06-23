"""Sensor platform for SmartMeter Emulator."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    if power_sensor := entry.data.get("power_sensor"):
        entities.append(
            SmartMeterSensor(
                coordinator,
                power_sensor,
                "power",
                "W",
                "power",
            )
        )

    if voltage_sensor := entry.data.get("voltage_sensor"):
        entities.append(
            SmartMeterSensor(
                coordinator,
                voltage_sensor,
                "voltage",
                "V",
                "voltage",
            )
        )

    if current_sensor := entry.data.get("current_sensor"):
        entities.append(
            SmartMeterSensor(
                coordinator,
                current_sensor,
                "current",
                "A",
                "current",
            )
        )

    if frequency_sensor := entry.data.get("frequency_sensor"):
        entities.append(
            SmartMeterSensor(
                coordinator,
                frequency_sensor,
                "frequency",
                "Hz",
                "frequency",
            )
        )

    async_add_entities(entities)


class SmartMeterSensor(SensorEntity):
    """Representation of a SmartMeter sensor."""

    def __init__(
        self,
        coordinator,
        entity_id: str,
        sensor_type: str,
        unit: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entity_id = entity_id
        self.sensor_type = sensor_type
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = f"mdi:{icon}"
        self._attr_state = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Growatt {self.sensor_type.capitalize()}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.config_entry.entry_id}_{self.sensor_type}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.get_sensor_value(self.entity_id)

    def update_value(self, value: float) -> None:
        """Update the sensor value."""
        self._attr_native_value = value
        self.async_write_ha_state()
