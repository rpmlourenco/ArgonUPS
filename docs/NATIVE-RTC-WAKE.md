# Periodic native Pi wake

Requires Argon UPS **0.6.0 or newer**, the updated shutdown blueprint and a
Raspberry Pi 5 running HAOS/Supervised with a writable native RTC wake alarm.
This feature uses the **Pi's own RTC**, not the Argon UPS RTC. The retired UPS
clock and next-start sensors remain removed.

## Behavior and settings

The blueprint adds two inputs:

| Input | Default | Purpose |
| --- | --- | --- |
| Enable periodic Pi wake | Off | Explicitly opt into native RTC writes after host preparation |
| Wake retry interval | 15 minutes | Use 15 minutes for a supervised test; change to 30 minutes for production |

Before each confirmed low-battery shutdown, the integration arms the native
RTC and reads the alarm back. The interval runs from alarm preparation, not
from the end of shutdown. The blueprint checks the full battery/freshness/device
guard again immediately before `hassio.host_shutdown`. If the guard no longer
passes, it cancels the integration's own alarm instead of shutting down.

At the next Home Assistant start:

- The integration's previous alarm is cancelled if it is still present;
  another application's alarm is left untouched.
- With external power, the host stays running; no retry shutdown is requested.
- On battery above the shutdown threshold, it stays running and the ordinary
  low-battery trigger remains active.
- On battery at/below the threshold, it waits for fresh telemetry and the
  configured continuous confirmation, then schedules another wake and shuts down.
- Missing/invalid telemetry prevents automatic shutdown, as in the original
  policy. The startup branch waits up to two minutes; the ordinary low-battery
  trigger can still act after telemetry later recovers.

This is **periodic checking, not detection of mains restoration while off**.
Recovery can take one interval plus boot time. The algorithm uses the
on-battery flag, not nonzero charging current: external power with a full
battery must also keep the Pi running.

**Every boot consumes battery.** There is no reserve cutoff or maximum attempt
count. A long outage can exhaust the UPS. There is no guarantee of waking after
the UPS stops supplying the Pi; no separate RTC backup battery is assumed.
This mechanism does not control UPS output and cannot guarantee recovery from
complete UPS depletion.

If scheduling fails, the error is logged and the blueprint **still shuts down**
when its final safety guard passes. Protecting data takes priority over a
recovery feature. A failure must not leave a low-battery host running simply
because its wake alarm is unavailable. No wake is promised in that case.

## One-time host preparation

The integration does not edit the bootloader, install packages or restart HAOS.
The Raspberry Pi documentation requires these bootloader settings for low-power
RTC wake:

```ini
POWER_OFF_ON_HALT=1
WAKE_ON_GPIO=0
```

Keep `WAIT_FOR_POWER_BUTTON` absent/default `0` or explicitly `0` if it is
already present. Do not set it to `1`: that requests waiting for the button
after complete power loss. Preserve all other settings, especially `BOOT_ORDER`.

On the investigated HAOS installation, the host already contains
`rpi-eeprom-config`, `rpi-eeprom-update`, `vcgencmd` and `vi`; its boot partition
is `/mnt/boot`. No vendor installer is needed. In an authorized HAOS **host**
SSH shell (not the Terminal app's container), a manual preparation is:

```sh
vcgencmd bootloader_config
vcgencmd bootloader_config > /mnt/data/argon-ups-bootloader-before-rtc.conf
EDITOR=vi rpi-eeprom-config --edit
```

Edit only the power settings above and save. This tool stages an EEPROM update
for the next reboot and can use the installed firmware image; review its output
before proceeding. Do not stage another update over an existing pending one.
Reboot the host yourself when ready. Afterwards verify the active configuration:

```sh
vcgencmd bootloader_config
cat /sys/class/rtc/rtc0/name
cat /sys/class/rtc/rtc0/since_epoch
cat /sys/class/rtc/rtc0/wakealarm
```

The name must identify `rpi-rtc`; the alarm can be blank when not armed.
The integration checks the driver, rejects a system/RTC clock difference over
five seconds, rejects another application's active alarm, and verifies its own
alarm by readback. It **cannot verify from an alarm readback alone that the
bootloader has the required configuration or that physical wake will succeed**.
The sysfs/device access observed on one HAOS installation is not a guarantee
for every container/security configuration.

## Install and perform a supervised test

1. Update the integration to 0.6.0 or newer using HACS and restart Home Assistant
   yourself to load the new actions.
2. Prepare and verify the bootloader settings above. Keep periodic wake off
   until this is done.
3. Re-import/update the blueprint from its GitHub URL. Updating HACS does not
   replace an already imported blueprint. Keep the existing automation/entity
   IDs and selections.
4. Keep **Allow host shutdown** enabled only for the intended host and enable
   **Enable periodic Pi wake**. Set **Wake retry interval** to **15 minutes**
   for the test. The low-battery threshold and confirmation inputs remain
   independent (initial proposals: 30% and 30 seconds).
5. During an authorized supervised low-battery test, inspect `native_wake.wake_time`
   in the automation trace (the schedule action's response). At info log level,
   the integration also records `Native Pi RTC wake scheduled for ...`.
   Confirm that the host shuts down, then returns after the interval.
6. Verify both cases: external power restored before wake keeps HA running;
   continuing on battery at/below the threshold causes a newly scheduled wake
   and another clean shutdown after fresh continuous confirmation.
7. Once verified, change the blueprint input to **30 minutes** for production.

Do not use **Run actions** or a direct host-shutdown action to test the
automation. Manual execution without the expected trigger ID remains blocked.
The startup branch only runs when periodic wake is explicitly enabled. An
ordinary HA restart/reload resets confirmation timers.

The integration exposes `argon_ups.schedule_wake` and `argon_ups.cancel_wake`.
Neither action powers off or restarts the host. Scheduling independently
requires the correct pair of entities from one loaded Argon entry, fresh
on-battery telemetry and a battery level at/below the supplied threshold.
Cancellation affects only the alarm owned by this integration. Ownership is
persisted before scheduling returns; alarms survive integration unloading and
host shutdown. Do not concurrently use another application to manage this RTC.

## Validation status

On 2026-11-17, read-only inspection confirmed the `rpi-rtc` driver and writable
RTC sysfs access inside the user's Core container. No alarm was set, no EEPROM
change was staged and no automatic shutdown/reboot/wake test was performed while
developing this feature. Physical RTC wake remains **unverified**. The earlier
ordinary low-battery shutdown was observed to complete cleanly; that does not
validate this new wake path. Automated tests were not run at the user's request.

References: [Raspberry Pi native RTC wake](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#real-time-clock-rtc),
[Pi power bootloader settings](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#POWER_OFF_ON_HALT),
[Linux RTC wakealarm implementation](https://github.com/torvalds/linux/blob/master/drivers/rtc/sysfs.c).
