# Zoned Security for Home Assistant

Zoned Security is a YAML-configured Home Assistant custom integration for a
zone-based alarm workflow. It exposes one alarm control panel plus helper
switches for modes, zones, pre-alarm, delayed alarm, manual inhibition, and
notifications.

It is designed for households that want Home Assistant to own the alarm state
while HomeKit automations feed zone triggers into Home Assistant. It can also be
used entirely from Home Assistant automations.

## Project Lineage

This project is inspired by the security-system behavior from the former
`homebridge-automation-switches` Homebridge plugin. That plugin is no longer
maintained in its original repository, but its model remains useful: represent an
alarm system with modes, zone switches, automation helper switches, and delayed
alarm handling.

Zoned Security brings that pattern into Home Assistant so the alarm state can be
managed locally and then optionally exposed to HomeKit through Home Assistant's
HomeKit Bridge.

## Features

- Alarm control panel with `home`, `away`, `night`, and `disarmed` states.
- Configurable zone switches.
- Configurable mode switches.
- Helper switches for delayed alarm, pre-alarm, and manual alarm inhibition.
- Optional notification services for alarm, inhibited alarm, and pre-alarm events.
- Logbook activity entries for mode changes, zone triggers, and alarm outcomes.
- Persisted alarm mode and zone state when enabled.

## Intended HomeKit Usage

A common deployment model is:

1. Configure the alarm system and zones in Home Assistant.
2. Expose the alarm control panel and selected switches through Home Assistant's
   HomeKit Bridge.
3. Keep existing HomeKit automations responsible for deciding when a real sensor
   should turn on a zone switch.
4. Let Zoned Security handle the shared alarm state, delay window, inhibition,
   notifications, and cleanup behavior.

This keeps sensor-specific logic in HomeKit when desired, while centralizing the
alarm state machine in Home Assistant.

## Status

This is an early custom integration. It is not a certified alarm system and should
not be used as the only safety-critical security layer.

Version `0.1.x` is intended for one configured security system. The YAML schema is
structured under `systems` for future expansion, but multiple concurrent systems
are not a supported public contract yet.

## Installation

Copy `custom_components/zoned_security` into your Home Assistant
`custom_components` directory, then add a YAML configuration.

For a package-based setup, copy `examples/zoned_security.yaml` to your Home
Assistant `packages` directory and adapt it to your zones and notification service.

Restart Home Assistant after installing or changing the integration code.

## Example

```yaml
zoned_security:
  systems:
    main:
      name: Security System
      default: disarmed
      stored: true

      modes:
        away:
          name: Away
        night:
          name: Night
        home:
          name: Home

      zones:
        - name: Front Door
          object_id: front_door_zone
        - name: Patio
          object_id: patio_zone

      helpers:
        delay_alarm:
          name: Delay Alarm
          period: 60
          auto_off: true
          stored: false
        pre_alarm:
          name: Pre Alarm
          period: 60
          auto_off: true
          stored: false
        disable_alarm:
          name: Disable Alarm
          stored: false

      notifications:
        alarm:
          service: notify.notify
          title: Security System
          message: Alarm activated
          priority: 1
          mute_seconds: 60
        alarm_inhibited:
          service: notify.notify
          title: Security System
          message: Alarm inhibited
          priority: 0
          mute_seconds: 60
        prealert:
          service: notify.notify
          title: Security System
          message: Pre-alarm activated
          priority: 0
          mute_seconds: 60
```

## Alarm Flow

When the system is armed and a zone switch turns on, the alarm enters
`triggered`. If the `delay_alarm` helper exists, Zoned Security turns it on and
waits for its timer to expire.

When `delay_alarm` expires:

- If `disable_alarm` is off, the integration sends the configured `alarm`
  notification with mode, triggering zone, active zones, and time.
- If `disable_alarm` is on, the integration sends `alarm_inhibited`, turns
  `disable_alarm` off, and clears the active zones.

The `pre_alarm` helper is a simple timed helper. Higher-level pre-alarm logic can
be implemented with Home Assistant or HomeKit automations.

### Pre-Alarm

The `pre_alarm` helper is intentionally simple: it turns on, can auto-off after a
configured period, and can send a `prealert` notification. This makes it useful
for two-step alarm workflows where the first sensor activation only marks a
pre-alarm state and a later activation escalates to the real alarm.

### Delayed Alarm

The `delay_alarm` helper represents the grace period between a zone trigger and
the final alarm action. During this period another automation or a user can turn
on `disable_alarm` to inhibit the alarm.

### Alarm Inhibition

The `disable_alarm` helper is a manual inhibition flag. It is evaluated when
`delay_alarm` expires. If it is on, Zoned Security sends the inhibited
notification, turns `disable_alarm` off, clears active zones, and returns the
system to its armed base state.

## Notes

This integration is currently YAML-based and does not implement a Home Assistant
config flow. The integration page will therefore show that it was not set up from
the UI.
