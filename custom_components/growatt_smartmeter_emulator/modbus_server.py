"""Modbus server for SmartMeter Emulator.

Uses pymodbus modern async API.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE,
)

_LOGGER = logging.getLogger(__name__)

try:
    from pymodbus.server import StartAsyncTcpServer
    from pymodbus.datastore import ModbusServerContext, ModbusSequentialDataBlock
    from pymodbus import ModbusDeviceIdentification
except ImportError as err:
    _LOGGER.error("Failed to import pymodbus: %s", err)
    raise


@dataclass
class RegisterMapping:
    """Mapping for a single register."""

    address: int
    value: int
    sensor_entity_id: str | None = None
    scale: float = 1.0
    offset: int = 0
    signed: bool = False
    description: str = ""


class ModbusServer:
    """Modbus TCP server for SmartMeter Emulator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Modbus server."""
        self.hass = hass
        self.config_entry = config_entry
        self.host = config_entry.data.get(CONF_HOST, "0.0.0.0")
        self.port = config_entry.data.get(CONF_PORT, 502)
        self.slave_id = config_entry.data.get(CONF_SLAVE, 1)

        self.register_map: dict[int, RegisterMapping] = {}
        self.server = None
        self.running = False
        self.loop = None

    def setup_registers(self) -> None:
        """Setup register map based on configuration."""
        self.register_map = {
            40001: RegisterMapping(
                address=40001,
                value=0,
                sensor_entity_id=self.config_entry.data.get("power_sensor"),
                scale=1,
                signed=True,
                description="Active Power",
            ),
            40002: RegisterMapping(
                address=40002,
                value=0,
                sensor_entity_id=self.config_entry.data.get("voltage_sensor"),
                scale=10,
                signed=False,
                description="AC Voltage",
            ),
            40003: RegisterMapping(
                address=40003,
                value=0,
                sensor_entity_id=self.config_entry.data.get("current_sensor"),
                scale=10,
                signed=False,
                description="Current",
            ),
            40004: RegisterMapping(
                address=40004,
                value=int(self.config_entry.data.get("frequency", 50)) * 100,
                sensor_entity_id=None,
                scale=100,
                signed=False,
                description="Frequency",
            ),
        }

    def update_register_from_sensor(self, address: int) -> bool:
        """Update a register value from the corresponding sensor."""
        if address not in self.register_map:
            return False

        mapping = self.register_map[address]
        if not mapping.sensor_entity_id:
            return False

        state = self.hass.states.get(mapping.sensor_entity_id)
        if not state or state.state in ("unavailable", "unknown"):
            return False

        try:
            sensor_value = float(state.state)
            register_value = int((sensor_value * mapping.scale) + mapping.offset)

            if mapping.signed:
                if register_value < -32768:
                    register_value = -32768
                elif register_value > 32767:
                    register_value = 32767
            else:
                if register_value < 0:
                    register_value = 0
                elif register_value > 65535:
                    register_value = 65535

            self.register_map[address].value = register_value
            _LOGGER.debug(
                "Register update: %d = %d (sensor: %s, raw: %f)",
                address,
                register_value,
                mapping.sensor_entity_id,
                sensor_value,
            )
            return True
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid sensor value for %s: %s", mapping.sensor_entity_id, err
            )
            return False

    def update_all_registers(self) -> None:
        """Update all registers from their sensors."""
        for address in self.register_map:
            self.update_register_from_sensor(address)

    def get_register(self, address: int) -> int | None:
        """Get a register value."""
        if address in self.register_map:
            return self.register_map[address].value
        return None

    def start(self) -> None:
        """Start the Modbus server."""
        self.setup_registers()

        store = ModbusSequentialDataBlock(0, [0] * 100)

        # Maak een ModbusServerContext zonder slave_context (pymodbus v3.6.0+)
        context = ModbusServerContext(slaves={}, single=True)

        identity = ModbusDeviceIdentification()
        identity.VendorName = "SmartMeter Emulator"
        identity.ProductCode = "SM-EMUL-001"
        identity.VendorUrl = "https://github.com/"
        identity.ProductName = "SmartMeter Emulator"
        identity.ModelName = "SmartMeter Emulator"
        identity.MajorMinor = "1.0.0"

        self.server = StartAsyncTcpServer(
            context=context,
            identity=identity,
            address=(self.host, self.port),
        )

        self.running = True
        _LOGGER.info(
            "Growatt Modbus server started on %s:%d", self.host, self.port
        )

    def stop(self) -> None:
        """Stop the Modbus server."""
        self.running = False
        if self.server:
            asyncio.run_coroutine_threadsafe(
                self.server.stop(), self.loop
            )
            _LOGGER.info("Growatt Modbus server stopped")
