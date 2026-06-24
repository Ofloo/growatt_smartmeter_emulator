"""Modbus server for SmartMeter Emulator.

Uses pymodbus modern async API.
"""
from __future__ import annotations

import asyncio
import logging
import socket
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
    from pymodbus.datastore import ModbusSequentialDataBlock
    from pymodbus import ModbusDeviceIdentification
    from pymodbus.datastore.simulator import ModbusSimulatorContext
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
        self.debug_logging = True  # Forceer debug-logging tijdens ontwikkeling

        # Configureer logging
        if self.debug_logging:
            _LOGGER.setLevel(logging.DEBUG)
            _LOGGER.debug("Debug logging enabled for Modbus server")
        else:
            _LOGGER.setLevel(logging.INFO)

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

    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("0.0.0.0", port)) == 0

    async def start(self) -> None:
        """Start the Modbus server asynchronously."""
        if self.debug_logging:
            _LOGGER.debug("Starting Modbus server setup")
        self.setup_registers()
        if self.debug_logging:
            _LOGGER.debug("Registers setup complete")

        if self.debug_logging:
            _LOGGER.debug("Checking if port %s is in use", self.port)
        if self.is_port_in_use(self.port):
            _LOGGER.error("Port %s is already in use", self.port)
            raise RuntimeError(f"Port {self.port} is already in use")

        if self.debug_logging:
            _LOGGER.debug("Created ModbusSequentialDataBlock")

        # Maak een ModbusSimulatorContext met 4 registers (40001-40004)
        config = {
            "setup": {
                "co size": 0,  # Coils (8 bit)
                "di size": 0,  # Discrete inputs (8 bit)
                "ir size": 0,  # Input registers (16 bit)
                "hr size": 4,  # Holding registers (16 bit)
            },
            "uint16": [
                [40001, 40004]  # 4 registers vanaf 40001
            ]
        }
        from pymodbus.datastore.simulator import ModbusSimulatorContext
        context = ModbusSimulatorContext(config, custom_actions={})
        if self.debug_logging:
            _LOGGER.debug("Created ModbusSimulatorContext with 4 registers")

        identity = ModbusDeviceIdentification()
        identity.VendorName = "SmartMeter Emulator"
        identity.ProductCode = "SM-EMUL-001"
        identity.VendorUrl = "https://github.com/"
        identity.ProductName = "SmartMeter Emulator"
        identity.ModelName = "SmartMeter Emulator"
        identity.MajorMinor = "1.0.0"
        if self.debug_logging:
            _LOGGER.debug("Configured ModbusDeviceIdentification")

        if self.debug_logging:
            _LOGGER.debug("Starting Modbus server on %s:%s", self.host, self.port)
        try:
            self.server = await StartAsyncTcpServer(
                context=context,
                identity=identity,
                address=(self.host, self.port),
            )
            if self.debug_logging:
                _LOGGER.debug("Modbus server started successfully")

            # Valideer dat de server luistert op de poort
            if self.debug_logging:
                _LOGGER.debug("Validating that the server is listening on port %s", self.port)
                if not self.is_port_in_use(self.port):
                    _LOGGER.error("Modbus server is not listening on port %s", self.port)
                    raise RuntimeError(f"Modbus server is not listening on port {self.port}")

            self.running = True
            _LOGGER.info(
                "Growatt Modbus server started on %s:%d", self.host, self.port
            )
        except Exception as e:
            _LOGGER.error("Failed to start Modbus server: %s", e, exc_info=self.debug_logging)
            raise

    async def stop(self) -> None:
        """Stop the Modbus server asynchronously."""
        if self.debug_logging:
            _LOGGER.debug("Stopping Modbus server")
        self.running = False
        if self.server:
            await self.server.stop()
            if self.debug_logging:
                _LOGGER.debug("Modbus server stopped successfully")
            _LOGGER.info("Growatt Modbus server stopped")
