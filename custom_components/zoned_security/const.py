"""Constants for the Zoned Security integration."""

from __future__ import annotations

DOMAIN = "zoned_security"

CONF_SYSTEMS = "systems"
CONF_ZONES = "zones"
CONF_OBJECT_ID = "object_id"
CONF_MODES = "modes"
CONF_HELPERS = "helpers"
CONF_NOTIFICATIONS = "notifications"

CONF_PERIOD = "period"
CONF_AUTO_OFF = "auto_off"
CONF_STORED = "stored"
CONF_RESET_ACTIVE_ZONES_ON_EXPIRE = "reset_active_zones_on_expire"
CONF_NOTIFY_SERVICE = "service"
CONF_TITLE = "title"
CONF_MESSAGE = "message"
CONF_PRIORITY = "priority"
CONF_SOUND = "sound"
CONF_MUTE_SECONDS = "mute_seconds"

MODE_HOME = "home"
MODE_AWAY = "away"
MODE_NIGHT = "night"

MODE_OBJECT_IDS = {
    MODE_HOME: "home_mode",
    MODE_AWAY: "away_mode",
    MODE_NIGHT: "night_mode",
}

HELPER_DELAY_ALARM = "delay_alarm"
HELPER_PRE_ALARM = "pre_alarm"
HELPER_DISABLE_ALARM = "disable_alarm"

NOTIFICATION_ALARM = "alarm"
NOTIFICATION_ALARM_INHIBITED = "alarm_inhibited"
NOTIFICATION_PREALERT = "prealert"

DEFAULT_DELAY_SECONDS = 60
DEFAULT_MUTE_SECONDS = 60
