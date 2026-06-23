# SmartMeter Emulator for Home Assistant

A Home Assistant custom integration that emulates a Modbus smart meter for Growatt inverters and other Modbus devices.

## Overview

This integration creates a virtual Modbus TCP server that emulates a real external smart meter. It uses existing Home Assistant sensor entities (like DSMR smart meter sensors or inverter sensors) and exposes them as Modbus registers that can be read by your Growatt inverter or other Modbus masters.

## Features

- ✅ Modbus TCP Server (emulates smart meter)
- ✅ Real-time sensor-to-register mapping
- ✅ Configurable register scaling and offsets
- ✅ Support for signed and unsigned values
- ✅ Profile-based configuration (easy to add new devices)
- ✅ Generic meter profile and Growatt MIN-4600TL-XH profile included
- ✅ Home Assistant HACS integration

## Supported Devices

### Currently Tested
- ✅ Growatt MIN-4600TL-XH hybrid inverter

### Should Work With
- Any Modbus TCP master/inverter
- Other Growatt inverters with similar register maps
- Modbus RTU via RS485 (planned)

## Installation

### via HACS (Recommended)

1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Navigate to HACS > Integrations
3. Click the three dots in the top right > "Add custom repository"
4. Enter: `https://github.com/SmartMeterEmulator/growatt_smartmeter_emulator` (replace with your actual repo URL)
5. Click "Add"
6. Search for "SmartMeter Emulator"
7. Click "Install"
8. Restart Home Assistant
9. Go to Settings > Devices & Services > Add Integration > "SmartMeter Emulator"

### Manual Installation

1. Copy the `custom_components/growatt_smartmeter_emulator` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > "SmartMeter Emulator"

## Configuration

### Step 1: Add Integration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **SmartMeter Emulator**
3. Fill in the configuration:

**Basic Settings:**
- **Host**: `0.0.0.0` (default, listen on all interfaces)
- **Port**: `502` (default Modbus TCP port)
- **Slave ID**: `1` (Modbus device address)
- **Power Sensor**: Select your power sensor entity (required)

**Optional Sensors:**
- Voltage sensor entity
- Current sensor entity
- Frequency sensor entity

### Step 2: Configure Growatt Inverter

Once the integration is running, configure your Growatt inverter to read from the Modbus server:

1. Access your Growatt inverter's Modbus configuration
2. Set Modbus TCP/RTU parameters:
   - Server IP: Your Home Assistant IP
   - Port: `502` (or your configured port)
   - Slave ID: `1` (or your configured slave ID)
3. Configure register addresses based on the profile

### Step 3: Monitor

The integration will automatically:
- Read values from your configured Home Assistant sensors
- Convert them to Modbus register values (with scaling)
- Listen for Modbus requests from your inverter
- Respond with the current values

## Register Map

### Generic Meter Profile (40001-40016)

| Address | Name | Type | Scale | Unit | Description |
|---------|------|------|-------|------|-------------|
| 40001 | Active Power | int16 | 1.0 | W | -2500 to 2500 W |
| 40002 | AC Voltage | uint16 | 10.0 | V | 230.0 V |
| 40003 | Current | uint16 | 10.0 | A | 12.5 A |
| 40004 | Frequency | uint16 | 100.0 | Hz | 50.00 Hz |
| 40005 | Import Power | uint16 | 1.0 | W | Grid import |
| 40006 | Export Power | uint16 | 1.0 | W | Grid export |
| 40007 | Daily Import | uint16 | 1.0 | kWh | Day energy in |
| 40008 | Daily Export | uint16 | 1.0 | kWh | Day energy out |
| 40011 | Total Import | uint32 | 1.0 | kWh | Lifetime in |
| 40013 | Total Export | uint32 | 1.0 | kWh | Lifetime out |
| 40015 | Temperature | uint16 | 10.0 | °C | Inverter temp |
| 40016 | Operation Time | uint32 | 1.0 | h | Hours running |

## Sensor Value Handling

### Scaling Formula

```
register_value = int((sensor_value × scale) + offset)
```

### Signed vs Unsigned

- **Signed** (int16): -32,768 to 32,767
  - Use for: Power (negative = export, positive = import)
  
- **Unsigned** (uint16): 0 to 65,535
  - Use for: Voltage, Current, Frequency, Energy

### Invalid Value Handling

The integration handles these cases gracefully:
- ✅ `unavailable` → Register not updated
- ✅ `unknown` → Register not updated
- ✅ `NaN` → Register not updated
- ✅ `infinity` → Register not updated

Only valid numeric sensor values update the Modbus registers.

## Troubleshooting

### Server Won't Start on Port 502

**Error**: "Address already in use"

**Solution**: Port 502 requires root privileges on Linux. Options:
1. Use a different port (e.g., 5020) and forward with iptables
2. Run Home Assistant with CAP_NET_BIND_SERVICE
3. Use a reverse proxy

### Inverter Can't Connect

**Check**:
1. Firewall allows port 502 (or your configured port)
2. Home Assistant IP is correct in inverter settings
3. Network is reachable (ping test)
4. Modbus TCP is enabled on inverter

### Values Not Updating

**Check**:
1. Sensor entities exist and have valid values
2. Sensors are not `unavailable` or `unknown`
3. Sensor values are numeric (not strings)
4. Home Assistant logs for warnings about invalid values

### Wrong Values

**Check**:
1. Scaling factors match your sensors
2. Signed/unsigned配置 is correct
3. Register address mapping is accurate

## Custom Profiles

You can create custom register profiles by adding YAML files to `custom_components/growatt_smartmeter_emulator/profiles/`:

```yaml
name: My Custom Meter
registers:
  40001:
    name: "Custom Register"
    value_type: "int16"
    scale: 1.0
    signed: true
    unit: "W"
    sensor_entity_id: "sensor.my_power"
    description: "Custom power reading"
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
flake8
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Built with [pymodbus](https://github.com/riptideio/pymodbus)
- For Home Assistant [Core](https://www.home-assistant.io/)

## Support

- 🐛 [Report bugs](https://github.com/SmartMeterEmulator/growatt_smartmeter_emulator/issues)
- 💡 [Request features](https://github.com/SmartMeterEmulator/growatt_smartmeter_emulator/issues)
- 📚 [Read docs](https://github.com/SmartMeterEmulator/growatt_smartmeter_emulator/wiki)

---

**Note**: This integration emulates a Modbus server and does NOT act as a Modbus client. It passively responds to requests from your inverter - it never actively polls the inverter.
