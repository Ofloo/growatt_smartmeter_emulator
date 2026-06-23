"""SmartMeter Emulator integration."""
from __future__ import annotations

import logging

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

    coordinator = SmartMeterEmulatorCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    modbus_server = ModbusServer(hass, entry)
    modbus_server.start()
    hass.data[DOMAIN]["modbus_server"] = modbus_server

    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    entry.async_on_unload(lambda: modbus_server.stop())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    modbus_server = hass.data[DOMAIN].get("modbus_server")
    if modbus_server:
        await modbus_server.stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update option."""
    await hass.config_entries.async_reload(entry.entry_id)
