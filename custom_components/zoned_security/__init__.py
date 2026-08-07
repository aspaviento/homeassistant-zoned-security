"""Zoned Security integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEFAULT, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery

from .const import (
    CONF_AUTO_OFF,
    CONF_HELPERS,
    CONF_MODES,
    CONF_OBJECT_ID,
    CONF_MUTE_SECONDS,
    CONF_NOTIFICATIONS,
    CONF_PERIOD,
    CONF_RESET_ACTIVE_ZONES_ON_EXPIRE,
    CONF_PRIORITY,
    CONF_STORED,
    CONF_SYSTEMS,
    CONF_ZONES,
    DEFAULT_DELAY_SECONDS,
    DOMAIN,
    HELPER_DELAY_ALARM,
    HELPER_DISABLE_ALARM,
    HELPER_PRE_ALARM,
    MODE_AWAY,
    MODE_HOME,
    MODE_NIGHT,
)
from .models import (
    STATE_ARMED_AWAY,
    STATE_ARMED_HOME,
    STATE_ARMED_NIGHT,
    STATE_DISARMED,
    HelperConfig,
    SystemConfig,
    ZoneConfig,
    ZonedSecuritySystem,
    notification_from_config,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_MODE_NAMES = {
    MODE_HOME: "Home",
    MODE_AWAY: "Away",
    MODE_NIGHT: "Night",
}

DEFAULT_HELPERS = {
    HELPER_DELAY_ALARM: {
        CONF_NAME: "Delay Alarm",
        CONF_PERIOD: DEFAULT_DELAY_SECONDS,
        CONF_AUTO_OFF: True,
        CONF_STORED: False,
    },
    HELPER_PRE_ALARM: {
        CONF_NAME: "Pre Alarm",
        CONF_PERIOD: DEFAULT_DELAY_SECONDS,
        CONF_AUTO_OFF: True,
        CONF_STORED: False,
    },
    HELPER_DISABLE_ALARM: {
        CONF_NAME: "Disable Alarm",
        CONF_AUTO_OFF: False,
        CONF_STORED: False,
    },
}

DEFAULT_STATES = {
    "armed-away": STATE_ARMED_AWAY,
    "armed-home": STATE_ARMED_HOME,
    "armed-night": STATE_ARMED_NIGHT,
    "disarmed": STATE_DISARMED,
    "unarmed": STATE_DISARMED,
}

HELPER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PERIOD): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_AUTO_OFF, default=False): cv.boolean,
        vol.Optional(CONF_STORED, default=False): cv.boolean,
        vol.Optional(CONF_RESET_ACTIVE_ZONES_ON_EXPIRE, default=False): cv.boolean,
    }
)

NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Optional("service"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("message"): cv.string,
        vol.Optional(CONF_PRIORITY): vol.Coerce(int),
        vol.Optional("sound"): cv.string,
        vol.Optional(CONF_MUTE_SECONDS, default=60): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)

SYSTEM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_DEFAULT, default="disarmed"): vol.In(DEFAULT_STATES),
        vol.Optional(CONF_STORED, default=True): cv.boolean,
        vol.Optional(CONF_MODES, default={}): {
            vol.In([MODE_HOME, MODE_AWAY, MODE_NIGHT]): vol.Schema(
                {vol.Required(CONF_NAME): cv.string}
            )
        },
        vol.Required(CONF_ZONES): vol.All(
            cv.ensure_list,
            [
                vol.Any(
                    cv.string,
                    vol.Schema(
                        {
                            vol.Required(CONF_NAME): cv.string,
                            vol.Required(CONF_OBJECT_ID): cv.slug,
                        }
                    ),
                )
            ],
        ),
        vol.Optional(CONF_HELPERS, default={}): {
            vol.In([HELPER_DELAY_ALARM, HELPER_PRE_ALARM, HELPER_DISABLE_ALARM]): HELPER_SCHEMA
        },
        vol.Optional(CONF_NOTIFICATIONS, default={}): {
            cv.string: NOTIFICATION_SCHEMA,
        },
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SYSTEMS): {
                    cv.slug: SYSTEM_SCHEMA,
                }
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Zoned Security from YAML."""
    domain_config = config.get(DOMAIN)
    if not domain_config:
        return True

    systems: dict[str, ZonedSecuritySystem] = {}
    for key, system_data in domain_config[CONF_SYSTEMS].items():
        system_config = _build_system_config(key, system_data)
        system = ZonedSecuritySystem(hass, system_config)
        await system.async_load()
        systems[key] = system

    hass.data[DOMAIN] = {"systems": systems}

    await discovery.async_load_platform(hass, "alarm_control_panel", DOMAIN, {}, config)
    await discovery.async_load_platform(hass, "switch", DOMAIN, {}, config)

    _LOGGER.info("Loaded %d zoned security system(s)", len(systems))
    return True


def _build_system_config(key: str, data: dict[str, Any]) -> SystemConfig:
    modes = DEFAULT_MODE_NAMES | {
        mode: mode_data[CONF_NAME] for mode, mode_data in data.get(CONF_MODES, {}).items()
    }

    helpers: dict[str, HelperConfig] = {}
    helper_data = DEFAULT_HELPERS | data.get(CONF_HELPERS, {})
    for helper_key, helper_config in helper_data.items():
        helpers[helper_key] = HelperConfig(
            name=helper_config[CONF_NAME],
            period=helper_config.get(CONF_PERIOD),
            auto_off=helper_config.get(CONF_AUTO_OFF, False),
            stored=helper_config.get(CONF_STORED, False),
            reset_active_zones_on_expire=helper_config.get(
                CONF_RESET_ACTIVE_ZONES_ON_EXPIRE, False
            ),
        )

    notifications = {
        notification_key: notification_from_config(notification_config)
        for notification_key, notification_config in data.get(CONF_NOTIFICATIONS, {}).items()
    }
    zones = [
        ZoneConfig(name=zone, object_id=f"{cv.slugify(zone)}_zone")
        if isinstance(zone, str)
        else ZoneConfig(name=zone[CONF_NAME], object_id=zone[CONF_OBJECT_ID])
        for zone in data[CONF_ZONES]
    ]

    return SystemConfig(
        key=key,
        name=data[CONF_NAME],
        default=DEFAULT_STATES[data[CONF_DEFAULT]],
        stored=data[CONF_STORED],
        modes=modes,
        zones=zones,
        helpers=helpers,
        notifications=notifications,
    )
