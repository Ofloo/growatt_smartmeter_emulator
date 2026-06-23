# AGENTS.md
# Growatt MIN-4600TL-XH Smart Meter Emulator - Home Assistant HACS Integration

## Projectdoel

Bouw een Home Assistant HACS custom integration die een virtuele Modbus smart meter emuleert.

Het doel is dat een Growatt inverter zich gedraagt alsof er een echte externe Modbus energiemeter aangesloten is.

Eerste doelhardware:

Growatt MIN-4600TL-XH hybride inverter.

De integratie gebruikt bestaande Home Assistant sensoren (zoals DSMR slimme meter en inverter sensoren) en publiceert deze als Modbus registers.

Architectuur:

Home Assistant
    |
    | sensor entities
    |
Growatt Meter Emulator
    |
    | Modbus TCP Server
    |
RS485/Ethernet Modbus Gateway
    |
Growatt inverter


## Belangrijk concept

De Growatt inverter is Modbus master/client.

De emulator is Modbus slave/server.

De emulator mag NOOIT actief de inverter uitlezen.

Correct:

Growatt:
"Read holding register 40001"

Emulator:
"40001 = huidig actief vermogen"


De software simuleert een extern apparaat.


## Architectuurprincipes

De implementatie moet generiek blijven.

Gebruik een profiel-gebaseerde registermap.

Voorbeeld:

profiles/
    generic_meter.yaml
    growatt_min_4600tl_xh.yaml


De Python code mag niet afhankelijk zijn van vaste Growatt registers.

Een nieuw apparaat moet toegevoegd kunnen worden door alleen een nieuw registerprofiel.


## Technologie

Gebruik:

- Python 3
- Home Assistant Custom Component architectuur
- HACS compatibel
- asyncio
- pymodbus
- Home Assistant entity API


Geen blocking code.

Geen aparte polling threads.

Gebruik correcte Home Assistant lifecycle.


## Functionaliteit

De integratie moet:

1. Een Modbus TCP slave/server starten.
2. Een interne register database onderhouden.
3. Home Assistant sensoren volgen.
4. Sensorwaarden converteren naar Modbus registers.
5. Modbus requests beantwoorden.
6. Registerwaarden realtime bijwerken.


## Eerste implementatie

Maak een Modbus TCP server.

Default:

IP:
0.0.0.0

Poort:
502


Configurabel:

- bind address
- poort
- slave/unit ID


## Register architectuur

Gebruik een abstract registermodel.

Ondersteun:

- Holding registers
- Input registers
- signed waarden
- scaling factors
- offsets


Voorbeeld registerprofiel:

40001:
Actief vermogen

Bron:
power sensor

Eenheid:
Watt

Voorbeeld:

-2500 = 2500W teruglevering


40002:
AC spanning

Schaal:

waarde / 10

Voorbeeld:

2300 = 230.0V


40003:
Frequentie

Schaal:

waarde / 100

Voorbeeld:

5000 = 50.00Hz


40004:
Stroom

Schaal:

waarde / 10

Voorbeeld:

125 = 12.5A


40005:
Import vermogen


40006:
Export vermogen


## Home Assistant koppeling

Configuratie via config_flow.py.

Gebruik UI configuratie.


Instellingen:

- power sensor entity_id
- voltage sensor entity_id
- current sensor entity_id
- frequency sensor entity_id


Voorbeeld:

sensor.energy_grid_power

sensor.growatt_modbus_load_ac_voltage

sensor.slimme_meter_gateway_stroom_fase_1


Niet uitgaan van vaste entity namen.


## Sensor verwerking

Voor elke sensor:

- controleer beschikbaarheid
- controleer numerieke waarde
- converteer correct naar registerwaarde
- log fouten


Ondersteun foutwaarden:

- unavailable
- unknown
- NaN
- infinity


Een ongeldige waarde mag nooit zomaar een Modbus register vervuilen.


## Software structuur

Maak:

custom_components/
    growatt_smartmeter_emulator/
        __init__.py
        manifest.json
        config_flow.py
        const.py
        coordinator.py
        modbus_server.py
        register_map.py
        profiles/
            generic_meter.yaml
            growatt_min_4600tl_xh.yaml
        sensor.py
        README.md


## Modbus server

De server moet:

- wachten op requests
- registers beantwoorden
- meerdere requests verwerken
- netjes stoppen bij Home Assistant shutdown


## Logging

Gebruik duidelijke logging.


INFO:

Growatt Modbus emulator started


DEBUG:

Register update:

40001:
-1500


WARNING:

Invalid sensor value:
sensor.xxx = NaN


## Toekomstige uitbreidingen

Architectuur voorbereiden voor:

- Modbus RTU via RS485
- ESP32 backend
- MQTT backend
- meerdere fases
- 3 fase meters
- andere invertermerken


## Testen

Maak tests voor:

- register mapping
- scaling
- signed values
- sensor updates
- NaN handling
- Modbus requests
- config flow


## Documentatie

README.md moet bevatten:

- installatie via HACS
- configuratie
- Modbus werking
- registerprofielen
- Growatt voorbeeld
- probleemoplossing


## Belangrijk

Bouw eerst de generieke Modbus slave infrastructuur.

Maar ontwerp vanaf het begin voor de Growatt MIN-4600TL-XH.

De Growatt registermap moet een apart profiel zijn en niet hardcoded in de Python code.