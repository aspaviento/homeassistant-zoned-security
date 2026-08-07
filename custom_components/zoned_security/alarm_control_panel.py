"""Alarm control panel platform for Zoned Security."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_AWAY, MODE_HOME, MODE_NIGHT
from .models import (
    STATE_TO_MODE,
    ZonedSecuritySystem,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up Zoned Security alarm entities."""
    systems: dict[str, ZonedSecuritySystem] = hass.data[DOMAIN]["systems"]
    async_add_entities([ZonedSecurityAlarm(system) for system in systems.values()])


class ZonedSecurityAlarm(AlarmControlPanelEntity):
    """Zoned security alarm panel."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )
    _attr_code_arm_required = False
    _attr_code_format = None

    def __init__(self, system: ZonedSecuritySystem) -> None:
        self.system = system
        self._attr_name = system.config.name
        self._attr_unique_id = f"{DOMAIN}_{system.config.key}_alarm"
        self.entity_id = "alarm_control_panel.zoned_security"

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self.async_on_remove(
            self.system.async_add_listener(self._handle_system_update)
        )

    @callback
    def _handle_system_update(self) -> None:
        self.async_write_ha_state()

    @property
    def alarm_state(self) -> Any:
        """Return the state of the alarm."""
        return self.system.current_state

    @property
    def state(self) -> Any:
        """Return the state for older HA cores."""
        return self.system.current_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alarm attributes."""
        return {
            "target_state": self.system.target_state,
            "mode": STATE_TO_MODE.get(self.system.target_state),
            "active_zones": [
                zone for zone, active in self.system.zones_alarm.items() if active
            ],
        }

    @property
    def code_arm_required(self) -> bool:
        """Return whether a code is required for arming."""
        return False

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the alarm."""
        await self.system.async_disarm()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the alarm in home mode."""
        await self.system.async_arm(MODE_HOME)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the alarm in away mode."""
        await self.system.async_arm(MODE_AWAY)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm the alarm in night mode."""
        await self.system.async_arm(MODE_NIGHT)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Trigger the alarm."""
        await self.system.async_trigger()
