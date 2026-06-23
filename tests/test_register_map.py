"""Tests for SmartMeter Emulator register map."""
from custom_components.growatt_smartmeter_emulator.register_map import (
    RegisterMap,
    RegisterDefinition,
)


def test_register_map_init():
    """Test RegisterMap initialization."""
    register_map = RegisterMap()
    assert register_map.registers == {}


def test_register_map_add():
    """Test adding a register."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40001,
        name="Test Register",
        value_type="int16",
        scale=1.0,
        signed=True,
    )

    register_map.add_register(register)
    assert 40001 in register_map.registers
    assert register_map.registers[40001].name == "Test Register"


def test_register_map_get():
    """Test getting a register."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40001,
        name="Test Register",
        value_type="int16",
        scale=1.0,
        signed=True,
    )

    register_map.add_register(register)

    result = register_map.get_register(40001)
    assert result is not None
    assert result.address == 40001

    result = register_map.get_register(99999)
    assert result is None


def test_register_map_get_value():
    """Test value conversion."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40002,
        name="Voltage Register",
        value_type="uint16",
        scale=10.0,
        signed=False,
    )

    register_map.add_register(register)

    value = register_map.get_value(40002, 230.0)
    assert value == 2300

    value = register_map.get_value(99999, 100.0)
    assert value is None


def test_register_map_signed_values():
    """Test signed value handling."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40001,
        name="Power Register",
        value_type="int16",
        scale=1.0,
        signed=True,
    )

    register_map.add_register(register)

    value = register_map.get_value(40001, -2500.0)
    assert value == -2500

    value = register_map.get_value(40001, 2500.0)
    assert value == 2500


def test_register_map_unsigned_values():
    """Test unsigned value handling."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40002,
        name="Voltage Register",
        value_type="uint16",
        scale=10.0,
        signed=False,
    )

    register_map.add_register(register)

    value = register_map.get_value(40002, 230.0)
    assert value == 2300


def test_register_map_bounds_checking():
    """Test value bounds checking."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40001,
        name="Limited Register",
        value_type="int16",
        scale=1000.0,
        signed=True,
    )

    register_map.add_register(register)

    value = register_map.get_value(40001, 100.0)
    assert value == 32767

    value = register_map.get_value(40001, -100.0)
    assert value == -32768


def test_register_map_bounds_unsigned():
    """Test unsigned bounds checking."""
    register_map = RegisterMap()

    register = RegisterDefinition(
        address=40002,
        name="Limited Register",
        value_type="uint16",
        scale=1000.0,
        signed=False,
    )

    register_map.add_register(register)

    value = register_map.get_value(40002, 100.0)
    assert value == 65535


def test_load_from_profile():
    """Test loading registers from profile."""
    register_map = RegisterMap()

    profile = {
        "registers": {
            "40001": {
                "name": "Power",
                "value_type": "int16",
                "scale": 1.0,
                "signed": True,
            },
            "40002": {
                "name": "Voltage",
                "value_type": "uint16",
                "scale": 10.0,
                "signed": False,
            },
        }
    }

    register_map.load_from_profile(profile)

    assert 40001 in register_map.registers
    assert 40002 in register_map.registers
    assert register_map.registers[40001].name == "Power"
    assert register_map.registers[40002].name == "Voltage"
