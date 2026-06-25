"""Coordinator for SmartMeter Emulator."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
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
        self.sensors_map: dict[int, str] = {
            40001: config_entry.data.get("power_sensor"),
            40002: config_entry.data.get("voltage_sensor"),
            40003: config_entry.data.get("current_sensor"),
            40004: config_entry.data.get("frequency_sensor"),
        }

    async def async_setup_listeners(self) -> None:
        """Setup listeners for sensor state changes."""
        registered_sensors = [sensor for sensor in self.sensors_map.values() if sensor]
        async_track_state_change_event(
            self.hass,
            registered_sensors,
            self._handle_sensor_update,
        )
        _LOGGER.debug("Sensor listeners registered")

    async def _handle_sensor_update(self, event) -> None:
        """Handle sensor state changes and update Modbus registers."""
        # Haal event data op (compatibel met Home Assistant Event object)
        if hasattr(event, "data"):
            event_data = event.data
        elif hasattr(event, "as_dict"):
            event_data = event.as_dict().get("data", {})
        else:
            _LOGGER.error("Ongeldig event object: %s", event)
            return

        # Haal entity_id en new_state op
        entity_id = event_data.get("entity_id")
        new_state = event_data.get("new_state")

        # Logging voor debug
        _LOGGER.debug(
            "Event ontvangen: entity_id=%s, new_state=%s",
            entity_id,
            new_state.state if new_state else None,
        )

        if not entity_id or not new_state:
            _LOGGER.warning("Ongeldige event data: %s", event_data)
            return

        # Validatie van sensorwaarde
        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning(
                "Sensor %s is unavailable, gebruik standaardwaarde 0", entity_id
            )
            value = 0.0
        else:
            try:
                value = float(new_state.state)
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Invalid sensor value for %s: %s", entity_id, err)
                return

        # Update de bijbehorende register (adres 40001-40004)
        for address, sensor_entity_id in self.sensors_map.items():
            if sensor_entity_id == entity_id:
                # Gebruik de scale van de register mapping
                mapping = self.modbus_server.register_map.get(address)
                if mapping:
                    register_value = int(value * mapping.scale)
                    await self.modbus_server.update_register(address, register_value)
                    _LOGGER.debug(
                        "Register update: %d = %d (sensor: %s, raw: %f)",
                        address,
                        register_value,
                        entity_id,
                        value,
                    )
                else:
                    register_value = int(value * 10)
                    await self.modbus_server.update_register(address, register_value)
                    _LOGGER.debug(
                        "Register update: %d = %d (sensor: %s, raw: %f)",
                        address,
                        register_value,
                        entity_id,
                        value,
                    )
                break

    def get_sensor_value(self, entity_id: str) -> float | None:
        """Get the current value of a sensor."""
        for address, sensor_entity_id in self.sensors_map.items():
            if sensor_entity_id == entity_id:
                register_value = self.modbus_server.get_register(address)
                if register_value is not None:
                    mapping = self.modbus_server.register_map.get(address)
                    if mapping:
                        return register_value / mapping.scale
        return None
