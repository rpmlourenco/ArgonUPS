# USB protocol research

Version 0.5.0 subsequently removed RTC/alarm queries and entities and adopted
mA as an explicitly assumed current unit at the user's request. The evidence
below records the earlier investigation; this presentation change does not
independently verify the scale or measurement point.

## Scope and evidence

Investigation on 2026-11-17 of one Argon PWR UPS 27W 5000mAh connected
to a Raspberry Pi 5 running HAOS. Command `0x04` returned decimal `17`
(`0x11`); no evidence establishes a dotted firmware version for that byte.

The existing integration continued to own the serial port. No second serial
reader was opened, no UPS settings were written, and no Home Assistant service,
restart, installation or configuration change was performed. Vendor code and
the product datasheet were inspected on the PC. The only direct additional
device transactions were standard USB HID GET_REPORT requests for advertised
reports, using the existing Python runtime and a read-only device handle.

These observations are device-specific research, not validation of every
Argon UPS firmware or of the integration's full behavior. Automated tests were
not run as part of this investigation.

## Charge current: what is established

The official reader decodes command `0x02` as an unsigned two-byte big-endian
integer named `device_chargecurrent`. It supplies neither a unit nor a scaling
factor, and does not establish whether the value is measured current or a
programmed current limit.

The user observed zero on battery, followed by 2250 after connecting external
power. Read-only inspection of the recorder subsequently showed this sequence:

| UTC time | Raw current | Battery at approximately that time |
| --- | ---: | ---: |
| 19:31:55 | 2250 | 76% |
| 19:38:35 | 1450 | 82% |
| 19:47:00 | 950 | 88% |
| 19:48:33 | 900 | 89% |

Intermediate nonzero current values were also multiples of 50. The reported
payload `03 b6` corresponds to decimal 950, confirming the implemented byte
order against actual hardware data.

This supports an association with charging and a taper as charge increases.
Interpreting 2250 as 2250 mA (2.25 A), with 50 mA steps, is a plausible working
hypothesis. The observations do **not** establish that interpretation, the
measurement point, or whether the number is an ADC reading versus a setpoint.
Battery percentage is another uncalibrated device output, so integrating this
number and comparing it with percentage changes cannot independently calibrate
its unit. The integration kept the value unitless during this investigation;
0.5.0 later adopted mA as an explicit assumption.

Assigning a confirmed unit requires either a matching firmware implementation,
identification of the controller/register conversion, or an independent
electrical measurement at the relevant point. No matching UPS firmware image,
schematic or conversion was identified in the inspected public sources. The
Argon ONE case firmware updater targets a different device and is not evidence
for this UPS protocol.

## RTC: valid transport, rejected date

The integration's warning captured:

```text
FE 06 05 08 1F 21 10 34 42 D7
```

The checksum is valid: the sum of preceding bytes modulo 256 is `D7`.
Following the official six-byte order (year, month, day, hour, minute, second),
the payload is `08 1F 21 10 34 42`. The month byte `1F` is not valid BCD, and
interpreting it as ordinary binary would produce month 31. Reordering the
bytes does not make every byte valid BCD either.

This rules out a simple timeout or checksum failure for that sample. It does
not distinguish an uninitialized/invalid clock from a firmware format difference.
No date correction, timezone correction or automatic RTC initialization is
justified by this frame. No claim is made that the bytes are static: repeated
warnings are suppressed by reason/message, so the absence of further warnings
does not establish a stopped clock.

## Next start: request-shaped frame only

The captured bytes were:

```text
FE 00 07 05
```

This is checksum-valid but byte-for-byte identical to the query, with no date
payload. The official reader needs at least five payload bytes to decode a
scheduled start. A request echo, an empty reply, an unsupported feature and an
unset alarm cannot be distinguished from this capture. In particular, this is
**not** proof that the alarm is disabled. Treating it as unavailable is safer
than manufacturing a date or asserting that no wake is scheduled.

## HID: advertised fields do not establish working telemetry

The separate HID interface advertises Power Device (`0x84`) and Battery System
(`0x85`) usages. Its descriptor includes remaining capacity, runtime to empty,
average times, voltage and present status. The descriptor does not advertise a
current usage that could establish the scale of serial command `0x02`.

Standard HID feature reads returned only one byte, the report identifier:

| Report | Advertised meaning | Returned length | Returned byte |
| --- | --- | ---: | --- |
| `0x0C` | Remaining capacity | 1 | `0C` |
| `0x0D` | Runtime to empty | 1 | `0D` |
| `0x1A` | Average time to full | 1 | `1A` |
| `0x1C` | Average time to empty | 1 | `1C` |
| `0x0B` | Voltage | 1 | `0B` |
| `0x07` | Present status | 1 | `07` |

Standard GET_INPUT_REPORT requests for capacity and present status also returned
only the identifier. No interrupt input report arrived during a three-second
read window. The remaining bytes in the allocated buffers were initialized to
zero locally; **they were not zero measurements returned by the UPS**.

These probes do not demonstrate working HID telemetry on this device. Merely
finding a runtime field in the descriptor is insufficient to add a remaining
runtime sensor. No SET_REPORT or HID output reports were sent.

## Sources and next useful experiment

- [Official serial reader](https://github.com/Argon40Tech/Argon40case/blob/a23299ba70fd76ce92ac3887a773ba770007832b/src/scripts/argonupsrtcd.py)
- [Official product datasheets repository](https://github.com/Argon40Tech/argon-datasheets)
- [Official case firmware updater, a separate target](https://github.com/Argon40Tech/Argon40case/blob/master/src/argonone-firmwareupdate.py)
- [Linux hidraw API: GET_FEATURE and GET_INPUT_REPORT semantics](https://docs.kernel.org/hid/hidraw.html)

An independently measured current can test the milliamp hypothesis. A meter
on the USB input measures input current, not necessarily battery charge current:
the Pi load, battery voltage and conversion losses must be accounted for.
Locating a matching firmware binary or controller schematic would provide a
stronger way to identify the conversion without changing the running system.
Initializing the RTC or programming an alarm would be a separate write
experiment requiring explicit authorization; neither was done here.
