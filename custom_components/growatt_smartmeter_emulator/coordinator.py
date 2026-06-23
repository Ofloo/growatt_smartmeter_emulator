"""Coordinator for SmartMeter Emulator."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorValue:
    """Represents a sensor value with metadata."""

    value: float | None
    entity_id: str
    last_updated: float | None = None


class SmartMeterEmulatorCoordinator(DataUpdateCoordinator[dict[str, SensorValue]]):
    """Coordinate smart meter data from Home Assistant sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="SmartMeter Emulator",
            update_interval=timedelta(seconds=1),
        )
        self.config_entry = config_entry
        self.sensors: dict[str, SensorValue] = {}

    async def _async_update_data(self) -> dict[str, SensorValue]:
        """Fetch data from sensors."""
        data = {}

        power_sensor = self.config_entry.data.get("power_sensor")
        voltage_sensor = self.config_entry.data.get("voltage_sensor")
        current_sensor = self.config_entry.data.get("current_sensor")
        frequency_sensor = self.config_entry.data.get("frequency_sensor")

        for sensor_id in [
            power_sensor,
            voltage_sensor,
            current_sensor,
            frequency_sensor,
        ]:
            if sensor_id:
                try:
                    state = self.hass.states.get(sensor_id)
                    if state and state.state not in ("unavailable", "unknown"):
                        value = float(state.state)
                        data[sensor_id] = SensorValue(
                            value=value,
                            entity_id=sensor_id,
                            last_updated=state.last_updated.timestamp()
                            if state.last_updated
                            else None,
                        )
                except (ValueError, TypeError) as err:
                    _LOGGER.warning(
                        "Invalid sensor value for %s: %s", sensor_id, err
                    )

        return data

    def get_sensor_value(self, entity_id: str) -> float | None:
        """Get the current value of a sensor."""
        if sensor := self.sensors.get(entity_id):
            return sensor.value
        return None

    def update_sensor(
        self, entity_id: str, value: float
    ) -> None:
        """Update a sensor value."""
        self.sensors[entity_id] = SensorValue(
            value=value, entity_id=entity_id
        )
        self.async_update_listeners()
