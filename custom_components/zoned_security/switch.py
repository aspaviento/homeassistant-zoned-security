"""Switch platform for Zoned Security."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    HELPER_DELAY_ALARM,
    HELPER_DISABLE_ALARM,
    HELPER_PRE_ALARM,
    MODE_AWAY,
    MODE_HOME,
    MODE_NIGHT,
    MODE_OBJECT_IDS,
)
from .models import MODE_TO_STATE, ZoneConfig, ZonedSecuritySystem


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up Zoned Security switches."""
    systems: dict[str, ZonedSecuritySystem] = hass.data[DOMAIN]["systems"]
    entities: list[SwitchEntity] = []

    for system in systems.values():
        entities.extend(
            [
                ModeSwitch(system, MODE_AWAY),
                ModeSwitch(system, MODE_NIGHT),
                ModeSwitch(system, MODE_HOME),
            ]
        )
        entities.extend(ZoneSwitch(system, zone) for zone in system.config.zones)
        entities.extend(
            HelperSwitch(system, helper)
            for helper in (
                HELPER_DELAY_ALARM,
                HELPER_PRE_ALARM,
                HELPER_DISABLE_ALARM,
            )
            if helper in system.config.helpers
        )

    async_add_entities(entities)


class BaseZonedSecuritySwitch(SwitchEntity):
    """Base switch for the zoned security integration."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, system: ZonedSecuritySystem) -> None:
        self.system = system

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self.async_on_remove(
            self.system.async_add_listener(self._handle_system_update)
        )

    @callback
    def _handle_system_update(self) -> None:
        self.async_write_ha_state()


class ModeSwitch(BaseZonedSecuritySwitch):
    """Switch that arms or disarms a mode."""

    def __init__(self, system: ZonedSecuritySystem, mode: str) -> None:
        super().__init__(system)
        self.mode = mode
        self._attr_name = system.config.modes[mode]
        self._attr_unique_id = f"{DOMAIN}_{system.config.key}_mode_{mode}"
        self.entity_id = f"switch.zoned_security_{MODE_OBJECT_IDS[mode]}"

    @property
    def is_on(self) -> bool:
        """Return true if this mode is active."""
        return self.system.target_state == MODE_TO_STATE[self.mode]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm this mode."""
        await self.system.async_arm(self.mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm when a mode button is turned off."""
        await self.system.async_disarm()


class ZoneSwitch(BaseZonedSecuritySwitch):
    """Switch that marks a zone alarm as active."""

    def __init__(self, system: ZonedSecuritySystem, zone: ZoneConfig) -> None:
        super().__init__(system)
        self.zone = zone
        self._attr_name = zone.name
        self._attr_unique_id = f"{DOMAIN}_{system.config.key}_zone_{slugify(zone.object_id)}"
        self.entity_id = f"switch.zoned_security_{zone.object_id}"

    @property
    def is_on(self) -> bool:
        """Return true if this zone is active."""
        return self.system.zones_alarm[self.zone.name]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate zone alarm."""
        await self.system.async_set_zone(self.zone.name, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear zone alarm."""
        await self.system.async_set_zone(self.zone.name, False)


class HelperSwitch(BaseZonedSecuritySwitch):
    """Helper switch for alarm workflows."""

    def __init__(self, system: ZonedSecuritySystem, helper: str) -> None:
        super().__init__(system)
        self.helper = helper
        self._attr_name = system.config.helpers[helper].name
        self._attr_unique_id = f"{DOMAIN}_{system.config.key}_helper_{helper}"
        self.entity_id = f"switch.zoned_security_{helper}"

    @property
    def is_on(self) -> bool:
        """Return true if this helper is active."""
        return self.system.helpers[self.helper]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn helper on."""
        await self.system.async_set_helper(self.helper, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn helper off."""
        await self.system.async_set_helper(self.helper, False)
