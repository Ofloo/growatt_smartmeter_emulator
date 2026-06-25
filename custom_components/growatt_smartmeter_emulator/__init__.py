"""SmartMeter Emulator integration."""
from __future__ import annotations

import logging
import os
import sys

# Voeg de lokale pymodbus v3.5.4 toe aan sys.path VOORDAT andere imports worden uitgevoerd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import SmartMeterEmulatorCoordinator
from .modbus_server import ModbusServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SmartMeter Emulator integration."""
    hass.data.setdefault(DOMAIN, {})

    modbus_server = ModbusServer(hass, entry)
    await modbus_server.start()
    hass.data[DOMAIN]["modbus_server"] = modbus_server

    coordinator = SmartMeterEmulatorCoordinator(hass, entry, modbus_server)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_setup_listeners()

    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    entry.async_on_unload(lambda: hass.async_create_task(modbus_server.stop()))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Starting unload of SmartMeter Emulator integration")

    modbus_server = hass.data[DOMAIN].get("modbus_server")
    if modbus_server:
        _LOGGER.debug("Stopping Modbus server")
        await modbus_server.stop()
        _LOGGER.debug("Modbus server stopped")
    else:
        _LOGGER.warning("Modbus server not found in hass.data[DOMAIN]")

    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        _LOGGER.debug("Clearing coordinator sensors_map")
        coordinator.sensors_map.clear()
        _LOGGER.debug("Coordinator sensors_map cleared")
    else:
        _LOGGER.warning("Coordinator not found in hass.data[DOMAIN][%s]", entry.entry_id)

    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("Unload platforms result: %s", result)

    _LOGGER.debug("Unload of SmartMeter Emulator integration completed")
    return result


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update option."""
    await hass.config_entries.async_reload(entry.entry_id)
