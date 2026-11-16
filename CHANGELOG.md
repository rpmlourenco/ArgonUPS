# Changelog

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
