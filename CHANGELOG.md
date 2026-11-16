# Changelog

## 0.1.0

- Add UI configuration for direct local USB serial polling.
- Add battery percentage and on-battery entities with shared status polling.
- Validate frames and checksums; handle fragmented replies and reconnect after
  communication failure, marking both entities unavailable until recovery.
- Add protocol/client and Home Assistant integration tests, plus HACS/hassfest CI.
- Include original community icons for the repository and Home Assistant.
- Document manual HAOS USB host-mode prerequisites and physical-test limitations.

Experimental initial release. Physical UPS validation is pending.
