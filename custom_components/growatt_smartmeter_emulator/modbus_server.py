"""Modbus server for SmartMeter Emulator.

Simple on-demand Modbus server that fetches sensor values directly when requested.
Designed for compatibility with multiple pymodbus versions.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass

import pymodbus
from packaging import version

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from pymodbus import ModbusDeviceIdentification
from pymodbus.datastore import ModbusServerContext, ModbusSimulatorContext
from pymodbus.datastore.context import ExcCodes
from pymodbus.exceptions import ModbusException
from pymodbus.server import StartAsyncTcpServer

# Detect pymodbus version and API compatibility
PYMODBUS_VERSION = version.parse(pymodbus.__version__)
NEW_API = PYMODBUS_VERSION >= version.parse("3.13.0")


def create_modbus_server_context(slave_id: int, context) -> ModbusServerContext:
    """Create a ModbusServerContext compatible with both old and new pymodbus APIs.

    Args:
        slave_id: The slave ID to use for the context
        context: The Modbus context to wrap

    Returns:
        ModbusServerContext: A properly initialized server context
    """
    try:
        # Try the new API first (pymodbus >= 3.13.0)
        return ModbusServerContext(devices={slave_id: context})
    except TypeError:
        # Fallback to old API (pymodbus < 3.13.0)
        return ModbusServerContext(slaves={slave_id: context}, single=True)


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


class OnDemandModbusContext(ModbusSimulatorContext):
    """Custom context that fetches sensor values on-demand."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the on-demand Modbus context."""
        # Initialize the base class with minimal configuration
        super().__init__({}, None)
        self.hass = hass
        self.config_entry = config_entry
        self.register_map = self._setup_register_map()

    def _setup_register_map(self) -> dict:
        """Setup register map based on configuration."""
        return {
            40001: {
                "sensor": self.config_entry.data.get("power_sensor"),
                "scale": 1,
                "signed": True,
                "description": "Active Power",
            },
            40002: {
                "sensor": self.config_entry.data.get("voltage_sensor"),
                "scale": 10,
                "signed": False,
                "description": "AC Voltage",
            },
            40003: {
                "sensor": self.config_entry.data.get("current_sensor"),
                "scale": 10,
                "signed": False,
                "description": "Current",
            },
            40004: {
                "sensor": None,  # Frequency is a fixed value
                "scale": 100,
                "signed": False,
                "description": "Frequency",
                "default": int(self.config_entry.data.get("frequency", 50)),
            },
        }

    def _get_sensor_value(self, mapping: dict) -> int:
        """Get sensor value and convert to register format."""
        try:
            # For frequency (fixed value)
            if mapping.get("sensor") is None:
                if "default" in mapping:
                    value = int(mapping["default"] * mapping["scale"])
                    _LOGGER.debug("Static value: raw=%s, scaled=%s",
                                  mapping["default"], value)
                    return value
                _LOGGER.debug("Static value defaulting to 0")
                return 0

            # For sensor-based values
            entity_id = mapping["sensor"]
            _LOGGER.debug("Fetching sensor value for %s", entity_id)

            if not entity_id:
                _LOGGER.warning("No sensor configured for mapping")
                raise ValueError("No sensor configured")

            state = self.hass.states.get(entity_id)
            if not state:
                _LOGGER.warning("Sensor %s not found", entity_id)
                raise ValueError(f"Sensor {entity_id} not found")

            if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                _LOGGER.warning("Sensor %s is %s", entity_id, state.state)
                raise ValueError(f"Sensor {entity_id} is {state.state}")

            try:
                value = float(state.state)
                _LOGGER.debug("Sensor %s raw value: %s", entity_id, state.state)
            except ValueError as e:
                _LOGGER.warning(
                    "Invalid sensor value for %s: %s",
                    entity_id,
                    state.state
                )
                raise ValueError(f"Invalid value for {entity_id}: {state.state}") from e

            register_value = int((value * mapping["scale"]) + mapping.get("offset", 0))
            _LOGGER.debug(
                "Sensor %s: raw=%s, scaled=%s, register=%s",
                entity_id, state.state, value, register_value
            )

            # Apply bounds checking
            if mapping.get("signed", False):
                if register_value < -32768:
                    register_value = -32768
                    _LOGGER.debug("Clamping to signed min: %s", register_value)
                elif register_value > 32767:
                    register_value = 32767
                    _LOGGER.debug("Clamping to signed max: %s", register_value)
            else:
                if register_value < 0:
                    register_value = 0
                    _LOGGER.debug("Clamping to unsigned min: %s", register_value)
                elif register_value > 65535:
                    register_value = 65535
                    _LOGGER.debug("Clamping to unsigned max: %s", register_value)

            return register_value

        except Exception as e:
            _LOGGER.warning("Error getting sensor value: %s", e)
            raise ModbusException(f"Sensor value error: {str(e)}")

    async def async_getValues(
        self,
        device_id: int,
        func_code: int,
        address: int,
        count: int = 1
    ) -> list[int] | ExcCodes:
        """Get values from registers asynchronously with proper address handling.

        This method handles both 0-based (common in Modbus) and 40001-based addressing.
        """
        _LOGGER.debug(
            "MODBUS REQUEST: device_id=%s, func_code=%s, address=%s, count=%s",
            device_id, func_code, address, count
        )

        # 1. Validate function code (only support holding registers)
        if func_code != 3:
            _LOGGER.warning("Unsupported function code: %s", func_code)
            return ExcCodes.ILLEGAL_FUNCTION

        # 2. Normalize the start address
        # Some clients send 0 for register 40001, others send 40001 directly
        start_address = address
        if start_address < 40001:
            # Client is using 0-based addressing (common in Modbus)
            start_address += 40001

        _LOGGER.debug("Normalized start address: %s", start_address)

        # 3. Validate address range
        if start_address < 40001 or start_address > 40004:
            _LOGGER.warning("Invalid register address: %s", start_address)
            return ExcCodes.ILLEGAL_ADDRESS

        # 4. Check if the requested range is valid
        end_address = start_address + count - 1
        if end_address > 40004:
            _LOGGER.warning(
                "Invalid register range: %s-%s (exceeds 40004)",
                start_address,
                end_address
            )
            return ExcCodes.ILLEGAL_ADDRESS

        # 5. Collect values for the requested range
        values = []
        for i in range(count):
            current_address = start_address + i

            # Check if register exists
            if current_address not in self.register_map:
                _LOGGER.warning(
                    "Register %s not found in register map",
                    current_address
                )
                return ExcCodes.ILLEGAL_ADDRESS

            try:
                # Get the register value
                mapping = self.register_map[current_address]
                reg_value = self._get_sensor_value(mapping)

                # Modbus registers are 16-bit unsigned, convert negative values
                if reg_value < 0:
                    reg_value = (1 << 16) + reg_value  # 2's complement
                    _LOGGER.debug(
                        "Converted negative value to unsigned: %s",
                        reg_value
                    )

                values.append(reg_value)
                _LOGGER.debug("Register %s value: %s", current_address, reg_value)

            except Exception as e:
                _LOGGER.error(
                    "Error reading register %s: %s",
                    current_address,
                    e
                )
                return ExcCodes.SERVER_DEVICE_FAILURE

        _LOGGER.debug("Returning values: %s", values)
        return values

    async def async_OLD_getValues(
        self,
        func_code: int,
        address: int,
        count: int = 1
    ) -> list[int] | ExcCodes:
        """Get values from registers asynchronously (legacy method).

        Wrapper for async_getValues with simplified interface.
        """
        _LOGGER.debug(
            "async_OLD_getValues called: func_code=%s, address=%s, count=%s",
            func_code, address, count
        )
        # Delegate to async_getValues (which handles address normalization)
        return await self.async_getValues(0, func_code, address, count)

    async def async_OLD_setValues(
        self,
        func_code: int,
        address: int,
        values: list[int] | list[bool]
    ) -> None | ExcCodes:
        """Set values in registers (not supported in this implementation)."""
        # This is a read-only implementation, so we just return success
        return None

    def getValues(self, fc_as_hex: int, address: int, count: int = 1) -> list[int]:
        """Get values from registers - fetches sensor values on-demand."""
        try:
            # Only support holding registers (function code 3)
            if fc_as_hex != 3:
                raise ModbusException(f"Unsupported function code: {fc_as_hex}")

            # Convert internal address to external address (40001-40004)
            external_address = address + 40001

            # Validate address range
            if external_address < 40001 or external_address > 40004:
                raise ModbusException(f"Invalid register address: {external_address}")

            # Fetch all 4 registers on-demand (to ensure consistency)
            values = []
            for i in range(4):  # Always fetch all 4 registers
                current_external_address = 40001 + i
                if current_external_address in self.register_map:
                    try:
                        mapping = self.register_map[current_external_address]
                        value = self._get_sensor_value(mapping)
                        values.append(value)
                    except Exception as e:
                        _LOGGER.error(
                            "Failed to get value for register %d: %s",
                            current_external_address,
                            e
                        )
                        raise
                else:
                    values.append(0)

            # Return only the requested registers
            start_index = address
            end_index = start_index + count
            return values[start_index:end_index]

        except ModbusException:
            raise
        except Exception as e:
            _LOGGER.error("Error in getValues: %s", e)
            raise ModbusException("Internal server error")

    def __getitem__(self, slave_id):
        """Get slave context - return self for single slave setup."""
        return self

    def slaves(self):
        """Return list of slave IDs."""
        return [1]  # Default slave ID


class ModbusServer:
    """Simple on-demand Modbus TCP server for SmartMeter Emulator."""

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
        # Hardcode debug_logging to True for development
        self.debug_logging = True  # config_entry.data.get("debug_logging", True)

        if self.debug_logging:
            _LOGGER.setLevel(logging.DEBUG)
            _LOGGER.debug("Debug logging enabled for Modbus server")
        else:
            _LOGGER.setLevel(logging.INFO)

        # For backward compatibility with tests
        self.register_map: dict[int, RegisterMapping] = {}
        self.context = None
        self.server = None
        self.running = False

    def setup_registers(self) -> None:
        """Setup register map based on configuration (for backward compatibility)."""
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

    async def start(self) -> None:
        """Start the Modbus server asynchronously."""
        _LOGGER.debug("Starting Modbus server setup")
        self.setup_registers()
        _LOGGER.debug("Registers setup complete")

        # Create on-demand Modbus context
        _LOGGER.debug("Creating OnDemandModbusContext")
        self.context = OnDemandModbusContext(self.hass, self.config_entry)
        _LOGGER.debug("Context created: %s", type(self.context))
        _LOGGER.debug("Context register map: %s", self.context.register_map)
        _LOGGER.debug("Context register map size: %s", len(self.context.register_map))

        # Verify context methods
        _LOGGER.debug(
            "Context has async_getValues: %s",
            hasattr(self.context, 'async_getValues')
        )
        _LOGGER.debug(
            "Context has async_OLD_getValues: %s",
            hasattr(self.context, 'async_OLD_getValues')
        )

        # Create server context with version-agnostic API
        _LOGGER.debug("Creating ModbusServerContext with slave_id: %s", self.slave_id)
        server_context = create_modbus_server_context(self.slave_id, self.context)
        _LOGGER.debug("ModbusServerContext created: %s", type(server_context))
        _LOGGER.debug(
            "ModbusServerContext devices: %s",
            getattr(
                server_context,
                '_devices',
                getattr(server_context, '_slaves', 'Unknown')
            )
        )

        # Setup device identification
        identity = ModbusDeviceIdentification()
        identity.VendorName = "SmartMeter Emulator"
        identity.ProductCode = "SM-EMUL-001"
        identity.VendorUrl = "https://github.com/Ofloo/growatt_smartmeter_emulator"
        identity.ProductName = "SmartMeter Emulator"
        identity.ModelName = "SmartMeter Emulator"
        identity.MajorMinorRevision = "2.0.0"

        _LOGGER.debug("Starting Modbus server on %s:%d", self.host, self.port)
        try:
            _LOGGER.debug(
                "Attempting to start Modbus server with context type: %s",
                type(server_context)
            )

            # Start the server in the background so it doesn't block setup
            import asyncio
            self.server_task = asyncio.create_task(
                self._run_modbus_server(server_context, identity)
            )

            # Give the server a moment to start
            await asyncio.sleep(0.1)

            self.running = True
            _LOGGER.info(
                "Growatt Modbus server started on %s:%d (slave ID: %d)",
                self.host,
                self.port,
                self.slave_id,
            )
            _LOGGER.debug("Modbus server running status: %s", self.running)

            # Verify server is running
            await self._verify_server()
        except Exception as e:
            _LOGGER.error(
                "Failed to start Modbus server: %s",
                e,
                exc_info=self.debug_logging
            )
            raise

    async def _verify_server(
        self,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ) -> bool:
        """Verify the server is running and accessible with retry logic."""
        for attempt in range(max_retries):
            try:
                _LOGGER.debug(
                    "Verifying server on %s:%s (attempt %s/%s)",
                    self.host, self.port, attempt + 1, max_retries
                )

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((self.host, self.port))

                    if result == 0:
                        _LOGGER.debug("Server verification successful")
                        return True
                    else:
                        _LOGGER.warning(
                            "Server not listening on %s:%s (error: %s)",
                            self.host, self.port, result
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)

            except Exception as e:
                _LOGGER.error("Server verification failed: %s", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        _LOGGER.error("Server verification failed after %s attempts", max_retries)
        return False

    async def _run_modbus_server(self, server_context, identity):
        """Run the Modbus server in the background with enhanced error handling."""
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                _LOGGER.info(
                    "Starting Modbus server on %s:%s (attempt %s/%s)",
                    self.host, self.port, attempt + 1, max_attempts
                )

                # Add delay before starting to allow network initialization
                await asyncio.sleep(0.1 * (attempt + 1))

                self.server = await StartAsyncTcpServer(
                    context=server_context,
                    identity=identity,
                    address=(self.host, self.port),
                )

                _LOGGER.info("Modbus server running successfully")
                return

            except OSError as e:
                if e.errno == 98:  # Address already in use
                    _LOGGER.warning(
                        "Port %s already in use, attempt %s/%s: %s",
                        self.port, attempt + 1, max_attempts, e
                    )
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)
                else:
                    _LOGGER.error("Modbus server OSError: %s", e)
                    raise
            except Exception as e:
                _LOGGER.error("Modbus server error: %s", e, exc_info=True)
                raise

        _LOGGER.error("Failed to start Modbus server after %s attempts", max_attempts)
        raise RuntimeError(f"Failed to start Modbus server on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the Modbus server asynchronously."""
        _LOGGER.debug("Stopping Modbus server")
        self.running = False

        if hasattr(self, 'server_task') and self.server_task:
            _LOGGER.debug("Cancelling server task")
            self.server_task.cancel()
            try:
                await self.server_task
                _LOGGER.debug("Server task completed")
            except asyncio.CancelledError:
                _LOGGER.debug("Server task cancelled")
            except Exception as e:
                _LOGGER.error("Error stopping server task: %s", e)

        if self.server:
            try:
                # Use stop() instead of kill() for compatibility with tests
                await self.server.stop()
                _LOGGER.info("Growatt Modbus server stopped")
            except Exception as e:
                _LOGGER.error("Error stopping Modbus server: %s", e)
        else:
            _LOGGER.debug("No server instance to stop")

    async def update_register(self, address: int, value: int) -> bool:
        """Update a register value directly (for backward compatibility)."""
        if address not in self.register_map:
            return False

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
        return True

    async def update_register_from_sensor(self, address: int) -> bool:
        """Update a register value from the corresponding sensor.

        For backward compatibility.
        """
        # For backward compatibility, we need to actually update the register value
        if address not in self.register_map:
            return False

        mapping = self.register_map[address]
        if not mapping.sensor_entity_id:
            return False

        state = self.hass.states.get(mapping.sensor_entity_id)
        if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
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
            return True
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Invalid sensor value for %s: %s",
                mapping.sensor_entity_id,
                err
            )
            return False

    async def update_all_registers(self) -> None:
        """Update all registers from their sensors.

        For backward compatibility - no-op in new implementation.
        """
        # In the new implementation, registers are fetched on-demand, so this is a no-op
        pass

    def get_register(self, address: int) -> int | None:
        """Get a register value.

        For compatibility with existing code.
        """
        # This is just for compatibility - in the new implementation,
        # values are fetched on-demand when requested via Modbus
        try:
            # If context is not initialized yet, return a default value
            # from the register map
            if self.context is None:
                if address in self.register_map:
                    return self.register_map[address].value
                return None

            internal_address = address - 40001
            if 0 <= internal_address <= 3:
                # Fetch the value on-demand
                values = self.context.getValues(3, internal_address, 1)
                return values[0] if values else None
        except Exception:
            # If there's an error, fall back to the register map
            if address in self.register_map:
                return self.register_map[address].value
            pass
        return None
