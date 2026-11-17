# Changelog

## 0.5.0

- Remove RTC and next scheduled start sensors, decoders and serial queries.
- Remove the two retired entity registry entries on successful integration setup.
- Display charge current in mA with current device class and measurement state
  class. The unit is assumed at the user's request, not independently calibrated;
  the entity retains `unit_status: assumed` and its existing unique/entity IDs.
- Rename the displayed sensor to Charge current and retain raw payload evidence.
- Document the read-only protocol investigation and its limits.

Published without running tests at the user's request. Updating does not install
or restart Home Assistant automatically. Restart Home Assistant after updating.

## 0.4.1

- Preserve the failure reason, bounded raw response, rejected payload and query
  time in diagnostic entity attributes, including when the entity is unavailable.
- Distinguish no response, no matching valid response, invalid payload and
  serial communication errors without inventing dates or alarm settings.
- Log optional failures once per error transition and log recovery, without
  changing log levels or interrupting battery/power polling.
- Keep raw charge current unitless: an observed change from 0 to 2250 when
  external power was connected does not by itself establish milliamp units.

Published without running tests at the user's request. No RTC or alarm writes.

## 0.4.0

- Add read-only diagnostic sensors for UPS version, RTC, next scheduled start
  and raw charge current.
- Query only one diagnostic per status cycle, using the existing serial
  connection and querying battery/power status first.
- Isolate optional-query failures from the battery and on-battery entities.
- Validate response commands, checksums, BCD fields and calendar dates; retain
  diagnostic payload bytes as attributes. No configuration commands are sent.

Published without running the updated tests at the user's request. These new
readouts have not been physically validated on the UPS. Current units/scaling
and disabled-alarm encoding remain unverified. RTC/alarm dates follow the
official reader's UTC interpretation.

## 0.3.0

- Publish every successful poll even when values stay unchanged, allowing
  safety automations to use both entities' `last_reported` timestamps.
- Add an optional safe-host-shutdown blueprint with proposed 30%/30s/30s
  settings, explicit arming, continuous confirmation and a final telemetry guard.
- Add regression tests for unchanged poll timestamps and shutdown guard failures.

The blueprint is not installed or enabled automatically. Hardware shutdown and
power recovery remain untested.

## 0.2.0

- Add Home Assistant USB discovery, restricted by VID/PID, manufacturer and
  Argon USB product description to avoid matching unrelated Linux USB gadgets.
- Prefill the discovered serial path and resolve `/dev/serial/by-id/` aliases
  for both discovery and manual setup, preventing duplicate entries via aliases.
- Keep discovery passive: status queries begin only after setup confirmation.

Physical discovery and UPS validation remain pending.

## 0.1.0

- Add UI configuration for direct local USB serial polling.
- Add battery percentage and on-battery entities with shared status polling.
- Validate frames and checksums; handle fragmented replies and reconnect after
  communication failure, marking both entities unavailable until recovery.
- Add protocol/client and Home Assistant integration tests, plus HACS/hassfest CI.
- Include original community icons for the repository and Home Assistant.
- Document manual HAOS USB host-mode prerequisites and physical-test limitations.

Experimental initial release. Physical UPS validation is pending.
