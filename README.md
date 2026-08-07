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

## Installation with HACS

This repository can be installed as a HACS custom repository.

1. Open HACS in Home Assistant.
2. Go to custom repositories.
3. Add `https://github.com/aspaviento/homeassistant-zoned-security` as an
   `Integration`.
4. Install `Zoned Security`.
5. Add a YAML configuration, for example by adapting
   `examples/zoned_security.yaml`.
6. Restart Home Assistant.

Zoned Security is currently YAML-based. After installing it from HACS, do not use
Settings -> Devices & services -> Add integration for setup. Configure it in
YAML instead.

## Manual Installation

Copy `custom_components/zoned_security` into your Home Assistant
`custom_components` directory, then add a YAML configuration.

For a package-based setup, copy `examples/zoned_security.yaml` to your Home
Assistant `packages` directory and adapt it to your zones and notification service.

Restart Home Assistant after installing or changing the integration code.

## Configuration

The integration is configured under the `zoned_security` YAML key.

Top-level options:

- `systems`: map of configured security systems. Version `0.1.x` supports one
  public production system even though the schema is shaped for future expansion.

System options:

- `name`: display name for the alarm control panel.
- `default`: initial state. Accepted values are `disarmed`, `unarmed`,
  `armed-home`, `armed-away`, and `armed-night`.
- `stored`: whether the target alarm mode and zone states are persisted.
- `modes`: display names for `home`, `away`, and `night` mode switches.
- `zones`: list of zone definitions.
- `helpers`: helper switch definitions.
- `notifications`: optional Home Assistant notification service calls.

Zone options:

- `name`: display name for the zone switch and notification context.
- `object_id`: stable slug used to build the zone switch entity ID.

Helper options:

- `name`: display name for the helper switch.
- `period`: optional timer duration in seconds.
- `auto_off`: whether the helper turns itself off when the timer expires.
- `stored`: reserved for helper persistence. Helpers are normally transient.

Notification options:

- `service`: Home Assistant notification service, such as `notify.notify` or a
  mobile-app notification service.
- `title`: notification title.
- `message`: base message.
- `priority`: optional notification priority passed as service data.
- `sound`: optional notification sound passed as service data.
- `mute_seconds`: per-notification throttle period.

## Example Configuration

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

## Entities

For a system configured with the example above, the integration creates:

- `alarm_control_panel.zoned_security`
- `switch.zoned_security_home_mode`
- `switch.zoned_security_away_mode`
- `switch.zoned_security_night_mode`
- `switch.zoned_security_delay_alarm`
- `switch.zoned_security_pre_alarm`
- `switch.zoned_security_disable_alarm`
- one zone switch per configured zone, for example
  `switch.zoned_security_front_door_zone`

The alarm control panel exposes these attributes:

- `target_state`: the armed/disarmed target state.
- `mode`: `home`, `away`, `night`, or `null`.
- `active_zones`: current active zone names.

## Services

Zoned Security does not currently register custom Home Assistant services.

Use the normal Home Assistant services for its entities:

- `alarm_control_panel.alarm_arm_home`
- `alarm_control_panel.alarm_arm_away`
- `alarm_control_panel.alarm_arm_night`
- `alarm_control_panel.alarm_disarm`
- `switch.turn_on`
- `switch.turn_off`

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

## Data and Storage

When `stored: true`, Zoned Security stores the target alarm state and active zone
states using Home Assistant's storage helpers. It does not store notification
credentials. Notification credentials, if any, remain owned by the configured
Home Assistant notification integration.

## External References

This integration is inspired by the former `homebridge-automation-switches`
security-system model. The original repository is no longer available in its
previous location, but archived documentation may still be useful for
understanding the Homebridge behavior that motivated this project.

## License

MIT

## Notes

This integration is currently YAML-based and does not implement a Home Assistant
config flow. The integration page will therefore show that it was not set up from
the UI.
