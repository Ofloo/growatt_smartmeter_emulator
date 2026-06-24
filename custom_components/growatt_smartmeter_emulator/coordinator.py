"""Coordinator for SmartMeter Emulator."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.debounce import Debouncer
from homeassistant.config_entries import ConfigEntry

from .modbus_server import ModbusServer

_LOGGER = logging.getLogger(__name__)


class SmartMeterEmulatorCoordinator:
    """Coordinate smart meter data from Home Assistant sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        modbus_server: ModbusServer,
    ) -> None:
        """Initialize my coordinator."""
        self.hass = hass
        self.config_entry = config_entry
        self.modbus_server = modbus_server
        self.sensors: dict[str, float] = {}
        self.sensors_map: dict[int, str] = {
            40001: config_entry.data.get("power_sensor"),
            40002: config_entry.data.get("voltage_sensor"),
            40003: config_entry.data.get("current_sensor"),
            40004: config_entry.data.get("frequency_sensor"),
        }
        self.debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=0.1,
            immediate=True,
            function=self._handle_sensor_update,
        )

    async def async_setup_listeners(self) -> None:
        """Setup listeners for sensor state changes with debouncing."""
        registered_sensors = [sensor for sensor in self.sensors_map.values() if sensor]
        async_track_state_change_event(
            self.hass,
            registered_sensors,
            self.debouncer.async_call,
        )
        _LOGGER.debug("Sensor listeners registered")

    async def _handle_sensor_update(self, event: dict) -> None:
        """Handle sensor state changes and update Modbus registers."""
        entity_id = event.get("entity_id")
        new_state = event.get("new_state")

        if not entity_id or not new_state:
            return

        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning("Sensor %s is unavailable, gebruik standaardwaarde 0", entity_id)
            value = 0.0
        else:
            try:
                value = float(new_state.state)
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Invalid sensor value for %s: %s", entity_id, err)
                return

        for address, sensor_entity_id in self.sensors_map.items():
            if sensor_entity_id == entity_id:
                register_value = int(value * 10)
                self.modbus_server.update_register(address, register_value)
                self.sensors[entity_id] = value
                _LOGGER.debug("Register update: %d = %d (sensor: %s)", address, register_value, entity_id)
                break

    def get_sensor_value(self, entity_id: str) -> float | None:
        """Get the current value of a sensor."""
        return self.sensors.get(entity_id)
