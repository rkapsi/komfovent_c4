# Komfovent C4 Modbus registers

Transcribed from `MODBUS_C4.pdf` (Komfovent, "Visio-C4_modbus.vsd", 2013/2014).
That PDF is the only primary source for this integration.

## Connection

| Setting | Value |
| --- | --- |
| TCP port | 502 |
| Serial baud rate | 19200 |
| Data bits | 8 |
| Parity | Even |
| Stop bits | 1 |

The documentation notes that runs longer than 10 m need a ground wire in
addition to A and B, and that long runs want line termination resistors.

DOMEKT units reach Modbus either directly over RS-485 (RJ-45 socket, pins 4/5/6
= A/B/GND) or over Ethernet through a Komfovent "Ping" gateway. With a C4 PLUS
panel the gateway sits between the panel and the unit.

## Register numbering

The tables below use the 1-based register numbers printed in the PDF. This
integration subtracts one to get the Modbus address put on the wire (see
`Register.address` in `registers.py`). This convention has been confirmed
against a real C4 unit.

All C4 registers are single 16-bit words. There are no 32-bit pairs.

## General (1000–1013)

| Register | Description | Type | Access | Range / values |
| --- | --- | --- | --- | --- |
| 1000 | C4 Start/Stop | integer | R/W | 1 = start, 0 = stop |
| 1001 | Season | integer | R/W | 1 = winter, 0 = summer |
| 1002 | Time | 2× char | R/W | 8:05 ⇒ `0x0805` |
| 1003 | Day of the week | integer | R/W | 1 = Mon … 7 = Sun |
| 1004 | Month-day | 2× char | R/W | 9 May ⇒ `0x0509` |
| 1005 | Year | integer | R/W | |
| 1006 | Modbus address | integer | R/W | 1…100 |
| 1007 | Alarm status (warnings) | binary | R | bit 14 = service, bit 13 = heater off, bit 11 = rotor stop |
| 1008 | Alarm status (stop flags) | binary | R | see below |
| 1009 | Alarm status (stop code) | integer | R | see below |
| 1010 | Recuperator level | integer | R | 0…100 % |
| 1011 | Electric heater level | integer | R | 0…100 % |
| 1012 | Water heating level | integer | R | 0…100 % |
| 1013 | Water cooling level | integer | R | 0…100 % |

### Stop flags (1008), by bit

1. Supply sensor B1
2. Heater overheating
3. Water temp low
4. Rotor stop
5. Frost possibility
6. Air temp high
7. Air temp low

### Stop codes (1009)

| Code | Meaning |
| --- | --- |
| 3 | Rotor stop |
| 4 | Heater overheating |
| 9 | Supply sensor B1 |
| 19 | Air temp low |
| 20 | Air temp high |
| 27 | Water temp low |
| 28 | Frost possibility |

## Ventilation (1100–1116)

| Register | Description | Type | Access | Range / values |
| --- | --- | --- | --- | --- |
| 1100 | Ventilation level (manual) | integer | R/W | 1…3 |
| 1101 | Ventilation level (current) | integer | R | 0…4 |
| 1102 | Mode (auto/manual) | integer | R/W | 0 = manual, 1 = auto |
| 1103 | Intake intensity level 1 (EC) | integer | R/W | 20…100 / 0 |
| 1104 | Intake intensity level 2 (EC/AC) | integer | R/W | 20…100 / 0…2 |
| 1105 | Intake intensity level 3 (EC) | integer | R/W | 20…100 / 0 |
| 1106 | Intake intensity level 4 (EC) | integer | R/W | 20…100 / 0 |
| 1107 | Exhaust intensity level 1 (EC) | integer | R/W | 20…100 / 0 |
| 1108 | Exhaust intensity level 2 (EC/AC) | integer | R/W | 20…100 / 0…2 |
| 1109 | Exhaust intensity level 3 (EC) | integer | R/W | 20…100 / 0 |
| 1110 | Exhaust intensity level 4 (EC) | integer | R/W | 20…100 / 0 |
| 1111 | "OVR" enable | integer | R/W | 1 = OVR enabled |
| 1112 | "OVR" time | integer | R/W | 1…90 |
| 1113 | "OVR" time (current) | integer | R | 0…90 |
| 1114 | AHU fans status | binary | R | 1 = operating, 0 = stopped |
| 1115 | Supply fan level (current) | integer | R | 0…100 |
| 1116 | Exhaust fan level (current) | integer | R | 0…100 |

Level 4 is the "OVR" boost level; the panel only exposes levels 1–3 for manual
selection, which is why register 1101 has a wider range than 1100.

## Temperature (1200–1205)

| Register | Description | Type | Access | Range / values |
| --- | --- | --- | --- | --- |
| 1200 | Supply air temp, °C | integer | R | −30…75 (×10, 25.0 °C ⇒ 250) |
| 1201 | Setpoint temp, °C | integer | R/W | 0…300 (×10) |
| 1202 | Temp. correction, °C | integer | R/W | −90…+90 (×10, +5 °C ⇒ 50) |
| 1203 | Temp. correction start time | 2× char | R/W | 8:05 ⇒ `0x0805` |
| 1204 | Temp. correction stop time | 2× char | R/W | 8:05 ⇒ `0x0805` |
| 1205 | Water temp, °C | integer | R | −10…110 (×10) |

> Note 1205, not 1203. Getting these two confused is easy and silent.

## Schedule (1300–1362)

Three start/stop time pairs per weekday at 1300–1341 (`0x0000`…`0x1800`,
i.e. 0:00–24:00), then one ventilation level per slot at 1342–1362 (0…3).

**Not implemented.** These 63 registers are not polled and no entities are
exposed for them. The weekly schedule is configured on the unit's own panel;
mirroring it into Home Assistant would roughly double the size of this
integration for something that is set once. Register 1102 switches between
following that schedule (auto) and ignoring it (manual), which covers the
common case.

## What the C4 does not have

Worth stating explicitly, because it explains why this integration is small and
why it shares no code with the C6/C8 one:

- no firmware or model register, so the controller cannot be identified over
  Modbus at all — you must know you have a C4
- no airflow or pressure control, and no flow sensors
- no air quality, CO₂, VOC or humidity sensors
- no eco mode, holiday mode or away mode
- no alarm history
- no extract, outdoor, or room temperature sensors — supply air and water are
  the only two temperatures reported
