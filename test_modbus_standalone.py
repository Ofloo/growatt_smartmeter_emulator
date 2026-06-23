#!/usr/bin/env python3
"""Testscript voor Modbus-server buiten Home Assistant."""
import asyncio
import logging

# Configureer logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

try:
    from pymodbus.datastore import (
        ModbusServerContext,
        ModbusSequentialDataBlock,
        ModbusDeviceContext,
    )
    from pymodbus.server import StartAsyncTcpServer
    from pymodbus import ModbusDeviceIdentification
except ImportError as err:
    log.error("Failed to import pymodbus: %s", err)
    raise

# Maak een Modbus-servercontext
log.debug("Creating ModbusSequentialDataBlock")
store = ModbusSequentialDataBlock(1, [0] * 100)

log.debug("Creating ModbusDeviceContext")
dummy_device = ModbusDeviceContext()

log.debug("Creating ModbusServerContext")
context = ModbusServerContext(devices={0: dummy_device})

# Configureer de Modbus-identiteit
log.debug("Creating ModbusDeviceIdentification")
identity = ModbusDeviceIdentification()
identity.VendorName = "SmartMeter Emulator"
identity.ProductCode = "SM-EMUL-001"
identity.VendorUrl = "https://github.com/"
identity.ProductName = "SmartMeter Emulator"
identity.ModelName = "SmartMeter Emulator"
identity.MajorMinor = "1.0.0"

# Start de server
log.debug("Starting Modbus server on 0.0.0.0:502")
asyncio.run(
    StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("0.0.0.0", 502),
    )
)
