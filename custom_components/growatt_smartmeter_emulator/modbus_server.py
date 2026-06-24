"""Modbus server for SmartMeter Emulator.

Uses pymodbus modern async API with ModbusSlaveContext.
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

try:
    from pymodbus.datastore import ModbusServerContext
    from pymodbus.server import StartAsyncTcpServer
    from pymodbus import ModbusDeviceIdentification
except ImportError as err:
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.error("Failed to import pymodbus: %s", err)
    raise

_LOGGER = logging.getLogger(__name__)


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
        self.debug_logging = config_entry.data.get("debug_logging", True)

        # Configureer logging
        if self.debug_logging:
            _LOGGER.setLevel(logging.DEBUG)
            _LOGGER.debug("Debug logging enabled for Modbus server")
        else:
            _LOGGER.setLevel(logging.INFO)

        self.register_map: dict[int, RegisterMapping] = {}
        self.context = None
        self.server = None
        self.running = False

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

    async def update_register(self, address: int, value: int) -> bool:
        """Update a register value directly."""
        if address not in self.register_map:
            return False

        # Validatie
        if self.register_map[address].signed:
            if value < -32768:
                value = -32768
            elif value > 32767:
                value = 32767
        else:
            if value < 0:
                value = 0
            elif value > 65535:
                value = 65535

        self.register_map[address].value = value

        # Update de Modbus-context als de server draait
        if self.context:
            await self.context.async_OLD_setValues(3, address - 40001, [value])
            _LOGGER.debug(
                "Register update: %d = %d (gebaseerd op interne addr %d)",
                address,
                value,
                address - 40001,
            )

        return True

    async def update_register_from_sensor(self, address: int) -> bool:
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

            # Update de register map
            self.register_map[address].value = register_value

            # Update de Modbus-context
            if self.context:
                await self.context.async_OLD_setValues(3, address - 40001, [register_value])
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

    async def update_all_registers(self) -> None:
        """Update all registers from their sensors."""
        for address in self.register_map:
            await self.update_register_from_sensor(address)

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
        _LOGGER.debug("Starting Modbus server setup")
        self.setup_registers()
        _LOGGER.debug("Registers setup complete")

        if self.is_port_in_use(self.port):
            _LOGGER.error("Port %s is already in use", self.port)
            raise RuntimeError(f"Port {self.port} is already in use")

        # Maak een ModbusSimulatorContext met 4 registers (40001-40004)
        # De interne register adressen zijn 0-3, maar de Modbus-protocol gebruikt 40001-40004
        config = {
            "setup": {
                "co size": 0,
                "di size": 0,
                "ir size": 0,
                "hr size": 4,
                "shared blocks": False,
                "type exception": "none",
                "defaults": {
                    "value": {
                        "bits": 0,
                        "uint16": 0,
                        "uint32": 0,
                        "float32": 0,
                        "string": "",
                    },
                    "action": {
                        "bits": None,
                        "uint16": None,
                        "uint32": None,
                        "float32": None,
                        "string": None,
                    }
                }
            },
            "invalid": [],
            "write": [],
            "repeat": [],
            "bits": [],
            "uint16": [[0, 3]],
            "uint32": [],
            "float32": [],
            "string": [],
        }
        from pymodbus.datastore.simulator import ModbusSimulatorContext
        self.context = ModbusSimulatorContext(config, custom_actions={})
        _LOGGER.debug("Created ModbusSimulatorContext with 4 Holding Registers")

        # Maak ModbusDeviceIdentification
        identity = ModbusDeviceIdentification()
        identity.VendorName = "SmartMeter Emulator"
        identity.ProductCode = "SM-EMUL-001"
        identity.VendorUrl = "https://github.com/"
        identity.ProductName = "SmartMeter Emulator"
        identity.ModelName = "SmartMeter Emulator"
        identity.MajorMinor = "1.0.0"
        _LOGGER.debug("Configured ModbusDeviceIdentification")

        # Start de Modbus-server
        _LOGGER.debug(
            "Starting Modbus server on %s:%d",
            self.host,
            self.port,
        )
        try:
            self.server = await StartAsyncTcpServer(
                context=self.context,
                identity=identity,
                address=(self.host, self.port),
            )
            _LOGGER.info(
                "Growatt Modbus server started on %s:%d (slave ID: %d)",
                self.host,
                self.port,
                self.slave_id,
            )

            # Valideer dat de server luistert op de poort
            if not self.is_port_in_use(self.port):
                _LOGGER.error("Modbus server is not listening on port %s", self.port)
                raise RuntimeError(f"Modbus server is not listening on port {self.port}")

            self.running = True
        except Exception as e:
            _LOGGER.error("Failed to start Modbus server: %s", e, exc_info=self.debug_logging)
            raise

    async def stop(self) -> None:
        """Stop the Modbus server asynchronously."""
        _LOGGER.debug("Stopping Modbus server")
        self.running = False
        if self.server:
            self.server.kill()
            _LOGGER.info("Growatt Modbus server stopped")
