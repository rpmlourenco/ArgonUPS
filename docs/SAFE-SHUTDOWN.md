# Safe host shutdown with Argon UPS

The [automation blueprint](../blueprints/automation/argon_ups_safe_shutdown.yaml)
creates an optional automation with shutdown disabled by default. It is separate from the
integration: installing Argon UPS never adds or enables a shutdown automation.
Run it on the Home Assistant host actually powered by this UPS, not on a second
Home Assistant server. Select both entities from the same Argon UPS device.

## Proposed starting values

| Setting | Proposal | Reason |
| --- | --- | --- |
| Battery threshold | At or below 30% | Conservative reserve until runtime is measured under the real load |
| Confirmation | 30 seconds | About three normal poll intervals; shorter than the EcoFlow example's two minutes for this smaller UPS |
| Maximum report age | 30 seconds for each entity | Three times the normal 10-second poll interval; rejects old/future reports |

These are initial engineering choices, not manufacturer-specified thresholds
or measured remaining runtime. Capacity, load, battery age and percentage
calibration affect the reserve. No minimum-discharge setting, second battery
measurement or input/output power is exposed by this integration, so it cannot
reproduce the EcoFlow checks. Both readings come from one status response and
are not independent measurements.

The guard requires explicit boolean arming, both sensors registered to the same
device, a finite percentage from 0 through the threshold, `On battery`
explicitly `on`, and fresh timestamps for both entities. Zero is allowed because
it is a valid percentage in the Argon protocol; unknown/unavailable is never
converted to zero. External power, invalid/missing data, stale data or a future
timestamp blocks the action. A failed serial query marks both entities
unavailable, interrupting confirmation. Values are checked again immediately
before the shutdown action. A normal manual **Run actions** is blocked by the
trigger-ID condition. Do not bypass conditions or manually invoke the service.

## Required integration version

**Install Argon UPS 0.6.0 or newer for the current blueprint.** The original
shutdown-only blueprint requires 0.3.0 or newer. Earlier
versions suppress entity writes for unchanged status samples. Their
`last_reported` timestamps can therefore be old during healthy communication,
making a freshness guard block a necessary shutdown. Version 0.3.0 republishes
each successful poll, including unchanged readings. This updates `last_reported`,
not necessarily `last_changed`, and does not force recording duplicate states.

Freshness proves that Home Assistant received a successful poll, not that the
UPS firmware measured its battery correctly. No software-only guard can rule
out plausible but incorrect hardware data. The policy blocks shutdown on loss
of telemetry, so a real outage combined with USB failure may prevent shutdown.

## Create and validate the automation

1. Update the integration to 0.6.0 or newer and load that version using Home
   Assistant's normal update procedure. Verify both entities are available.
2. In **Settings → Automations & scenes → Blueprints → Import blueprint**, use:

   ```text
   https://github.com/rpmlourenco/ArgonUPS/blob/main/blueprints/automation/argon_ups_safe_shutdown.yaml
   ```

   If using an unpublished checkout, copy the blueprint into the target host's
   blueprint directory yourself when authorized; the GitHub URL only works once
   the file has been published.
3. Create an automation from the blueprint. Choose the two entities belonging
   to this host's UPS. Keep the proposed values initially and leave **Allow host
   shutdown** off. You can also disable the automation during commissioning.
4. With shutdown still disabled, check telemetry in Developer Tools → Template,
   replacing the example entity IDs if your instance uses different ones:

   ```jinja
   {% for id in ['sensor.argon_ups_battery', 'binary_sensor.argon_ups_on_battery'] %}
     {% set e = states[id] %}
     {{ id }}: {{ states(id) }}, age:
     {{ (as_timestamp(now()) - as_timestamp(e.last_reported)) | round(1)
        if e is defined and e is not none else 'missing' }} seconds
   {% endfor %}
   ```

   Refresh the template after several polls. Each age should normally stay
   below 30 seconds, even when the percentage and power source do not change.
5. During a separately authorized, supervised power-transition test, confirm
   that `On battery` changes to `on` when external power is removed and returns
   to `off` when restored. Keep **Allow host shutdown** off. Do not drain
   the UPS or unplug its USB/data connection as a substitute for a mains test.
6. Only turn on **Allow host shutdown**, save and enable the automation once the
   selected host, entities, freshness and power-source behavior are verified.
   The input is saved with the automation; Home Assistant normally restores
   the enabled state after a restart. No blueprint edits are needed.

Confirmation timers reset on restart/reload. Timing depends on polling and
Home Assistant's scheduling, so it is not a precise cutoff timer. An initial
20% reading with `On battery = off` does not meet the shutdown guard.

## What is shut down and what happens afterwards

The shutdown action is `hassio.host_shutdown`. On HAOS/Supervised it shuts
down the entire host, including its apps. It does not disable UPS output and
does not power the host on again. A Pi that remains powered by the UPS can stay
off when mains returns; power recovery must be validated separately for the
specific Pi/UPS/firmware configuration. Optional **periodic Pi wake** can schedule
the Pi's native RTC before shutdown, then recheck external power after boot.
It defaults off, with a configurable 15-minute interval (30 minutes proposed
for production), and requires manual bootloader preparation. It is not an
immediate mains-return trigger. See [native RTC wake](NATIVE-RTC-WAKE.md) for
setup, failure behavior and battery-depletion limitations.

An ordinary shutdown was observed on the user's device on 2026-11-17: 30% at
22:45:35 Europe/Madrid, action after 30 seconds, Recorder closed normally and
the next boot reported the data filesystem clean. The user restarted using the
power button. This does not validate the new periodic wake path, which remains
untested physically. No shutdown or production activation was performed while
developing that new path.

References: [Host shutdown](https://www.home-assistant.io/actions/hassio.host_shutdown/),
[automation triggers](https://www.home-assistant.io/docs/automation/trigger/).
