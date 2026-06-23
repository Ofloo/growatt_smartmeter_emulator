"""Register map for SmartMeter Emulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RegisterDefinition:
    """Definition of a single Modbus register."""

    address: int
    name: str
    value_type: str  # int16, uint16, int32, uint32, float
    scale: float = 1.0
    offset: int = 0
    signed: bool = False
    unit: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    sensor_entity_id: str | None = None
    description: str = ""


class RegisterMap:
    """Manages the Modbus register map."""

    def __init__(self) -> None:
        """Initialize the register map."""
        self.registers: Dict[int, RegisterDefinition] = {}

    def add_register(self, register: RegisterDefinition) -> None:
        """Add a register to the map."""
        self.registers[register.address] = register

    def get_register(self, address: int) -> RegisterDefinition | None:
        """Get a register by address."""
        return self.registers.get(address)

    def get_value(
        self, address: int, sensor_value: float | None
    ) -> int | None:
        """Convert a sensor value to a register value."""
        if sensor_value is None:
            return None

        register = self.get_register(address)
        if not register:
            return None

        value = sensor_value * register.scale + register.offset

        if register.signed:
            if value < -32768:
                value = -32768
            elif value > 32767:
                value = 32767
            return int(value)
        else:
            if value < 0:
                value = 0
            elif value > 65535:
                value = 65535
            return int(value)

    def load_from_profile(self, profile: Dict[str, Any]) -> None:
        """Load registers from a YAML-like profile."""
        for addr_str, reg_config in profile.get("registers", {}).items():
            address = int(addr_str)
            register = RegisterDefinition(
                address=address,
                name=reg_config.get("name", f"Register {address}"),
                value_type=reg_config.get("value_type", "int16"),
                scale=reg_config.get("scale", 1.0),
                offset=reg_config.get("offset", 0),
                signed=reg_config.get("signed", False),
                unit=reg_config.get("unit"),
                min_value=reg_config.get("min_value"),
                max_value=reg_config.get("max_value"),
                sensor_entity_id=reg_config.get("sensor_entity_id"),
                description=reg_config.get("description", ""),
            )
            self.add_register(register)
