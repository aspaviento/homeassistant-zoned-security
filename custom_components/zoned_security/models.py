"""Shared state model for Zoned Security."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MESSAGE,
    CONF_MUTE_SECONDS,
    CONF_NOTIFY_SERVICE,
    CONF_PRIORITY,
    CONF_SOUND,
    CONF_TITLE,
    DEFAULT_MUTE_SECONDS,
    DOMAIN,
    HELPER_DELAY_ALARM,
    HELPER_DISABLE_ALARM,
    HELPER_PRE_ALARM,
    MODE_AWAY,
    MODE_HOME,
    MODE_NIGHT,
    NOTIFICATION_ALARM,
    NOTIFICATION_ALARM_INHIBITED,
    NOTIFICATION_PREALERT,
)

try:
    from homeassistant.components.alarm_control_panel import AlarmControlPanelState

    STATE_ARMED_AWAY = AlarmControlPanelState.ARMED_AWAY
    STATE_ARMED_HOME = AlarmControlPanelState.ARMED_HOME
    STATE_ARMED_NIGHT = AlarmControlPanelState.ARMED_NIGHT
    STATE_DISARMED = AlarmControlPanelState.DISARMED
    STATE_TRIGGERED = AlarmControlPanelState.TRIGGERED
except ImportError:  # pragma: no cover - compatibility for older HA cores
    from homeassistant.const import (
        STATE_ALARM_ARMED_AWAY,
        STATE_ALARM_ARMED_HOME,
        STATE_ALARM_ARMED_NIGHT,
        STATE_ALARM_DISARMED,
        STATE_ALARM_TRIGGERED,
    )

    STATE_ARMED_AWAY = STATE_ALARM_ARMED_AWAY
    STATE_ARMED_HOME = STATE_ALARM_ARMED_HOME
    STATE_ARMED_NIGHT = STATE_ALARM_ARMED_NIGHT
    STATE_DISARMED = STATE_ALARM_DISARMED
    STATE_TRIGGERED = STATE_ALARM_TRIGGERED

_LOGGER = logging.getLogger(__name__)

MODE_TO_STATE = {
    MODE_HOME: STATE_ARMED_HOME,
    MODE_AWAY: STATE_ARMED_AWAY,
    MODE_NIGHT: STATE_ARMED_NIGHT,
}

STATE_TO_MODE = {value: key for key, value in MODE_TO_STATE.items()}


@dataclass
class HelperConfig:
    """Configuration for a helper switch."""

    name: str
    period: int | None = None
    auto_off: bool = False
    stored: bool = False
    reset_active_zones_on_expire: bool = False


@dataclass
class NotificationConfig:
    """Configuration for a notification action."""

    service: str | None = None
    title: str | None = None
    message: str | None = None
    priority: int | None = None
    sound: str | None = None
    mute_seconds: int = DEFAULT_MUTE_SECONDS


@dataclass
class AlarmTriggerContext:
    """Context captured when the system enters triggered state."""

    zone: str | None
    target_state: Any
    active_zones: list[str]
    triggered_at: datetime


@dataclass
class ZoneConfig:
    """Configuration for a security zone."""

    name: str
    object_id: str


@dataclass
class SystemConfig:
    """Configuration for one zoned security system."""

    key: str
    name: str
    default: Any = STATE_DISARMED
    stored: bool = True
    modes: dict[str, str] = field(default_factory=dict)
    zones: list[ZoneConfig] = field(default_factory=list)
    helpers: dict[str, HelperConfig] = field(default_factory=dict)
    notifications: dict[str, NotificationConfig] = field(default_factory=dict)


class ZonedSecuritySystem:
    """Runtime state for a zoned security system."""

    def __init__(self, hass: HomeAssistant, config: SystemConfig) -> None:
        self.hass = hass
        self.config = config
        self._store = Store(hass, 1, f"{DOMAIN}.{config.key}")
        self._listeners: list[Callable[[], None]] = []
        self._timer_unsub: dict[str, Any] = {}
        self._last_notification: dict[str, datetime] = {}
        self._alarm_context: AlarmTriggerContext | None = None

        self.target_state: Any = config.default
        self.zones_alarm = {zone.name: False for zone in config.zones}
        self.helpers = {key: False for key in config.helpers}

    async def async_load(self) -> None:
        """Load persisted state."""
        if not self.config.stored:
            return

        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        target_state = stored.get("target_state")
        if target_state in set(MODE_TO_STATE.values()) | {STATE_DISARMED}:
            self.target_state = target_state

        stored_zones = stored.get("zones_alarm")
        if isinstance(stored_zones, dict):
            self.zones_alarm = {
                zone.name: stored_zones.get(zone.name) is True
                for zone in self.config.zones
            }

    async def async_store(self) -> None:
        """Persist state."""
        if not self.config.stored:
            return

        await self._store.async_save(
            {
                "target_state": self.target_state,
                "zones_alarm": self.zones_alarm,
            }
        )

    @property
    def current_state(self) -> Any:
        """Return current alarm state."""
        if any(self.zones_alarm.values()) and self.target_state != STATE_DISARMED:
            return STATE_TRIGGERED
        return self.target_state

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_arm(self, mode: str) -> None:
        """Arm the system in a mode."""
        previous_state = self.target_state
        self.target_state = MODE_TO_STATE[mode]
        await self.async_store()
        if previous_state != self.target_state:
            self._log_activity(f"mode changed to {self._mode_label(self.target_state)}")
        self._notify_listeners()

    async def async_disarm(self) -> None:
        """Disarm the system."""
        previous_state = self.target_state
        self.target_state = STATE_DISARMED
        await self.async_store()
        if previous_state != self.target_state:
            self._log_activity("mode changed to disarmed")
        self._notify_listeners()

    async def async_trigger(self) -> None:
        """Trigger the alarm through the default alarm zone."""
        if self.config.zones:
            await self.async_set_zone(self.config.zones[0].name, True)
            return

        await self._handle_alarm_triggered()
        self._notify_listeners()

    async def async_set_zone(self, zone: str, active: bool) -> None:
        """Set a zone alarm state."""
        was_triggered = self.current_state == STATE_TRIGGERED
        self.zones_alarm[zone] = active
        await self.async_store()

        is_triggered = self.current_state == STATE_TRIGGERED
        if is_triggered and not was_triggered:
            self._alarm_context = AlarmTriggerContext(
                zone=zone if active else None,
                target_state=self.target_state,
                active_zones=self._active_zones(),
                triggered_at=dt_util.utcnow(),
            )
            self._log_activity(
                f"zone {zone} triggered in {self._mode_label(self.target_state)}"
            )
            await self._handle_alarm_triggered()
        elif not is_triggered:
            self._alarm_context = None

        self._notify_listeners()

    async def async_set_helper(self, helper: str, active: bool) -> None:
        """Set helper switch state."""
        self._cancel_timer(helper)
        self.helpers[helper] = active

        if active:
            if helper == HELPER_PRE_ALARM:
                await self.async_send_notification(NOTIFICATION_PREALERT)
            helper_config = self.config.helpers.get(helper)
            if helper_config and helper_config.period:
                self._start_timer(helper, helper_config.period)

        self._notify_listeners()

    async def _handle_alarm_triggered(self) -> None:
        if self.helpers.get(HELPER_DISABLE_ALARM):
            return

        if HELPER_DELAY_ALARM in self.helpers:
            await self.async_set_helper(HELPER_DELAY_ALARM, True)
            return

        await self.async_send_notification(NOTIFICATION_ALARM)

    @callback
    def _start_timer(self, helper: str, period: int) -> None:
        _LOGGER.info("Starting %s timer for %s seconds", helper, period)
        self._timer_unsub[helper] = self.hass.loop.call_later(
            period,
            lambda: self.hass.async_create_task(self._timer_done(helper)),
        )

    @callback
    def _cancel_timer(self, helper: str) -> None:
        unsub = self._timer_unsub.pop(helper, None)
        if unsub:
            unsub.cancel()

    async def _timer_done(self, helper: str) -> None:
        _LOGGER.info("%s timer expired", helper)
        self._timer_unsub.pop(helper, None)
        helper_config = self.config.helpers.get(helper)

        if helper_config and helper_config.auto_off:
            self.helpers[helper] = False
            if helper_config.reset_active_zones_on_expire:
                self._clear_active_zones()
                await self.async_store()

        if helper == HELPER_DELAY_ALARM:
            if self.helpers.get(HELPER_DISABLE_ALARM):
                _LOGGER.info("Alarm actions inhibited because Disable Alarm is active")
                self.helpers[HELPER_DISABLE_ALARM] = False
                self._clear_active_zones()
                self._alarm_context = None
                await self.async_store()
                self._log_activity("alarm inhibited")
                await self.async_send_notification(NOTIFICATION_ALARM_INHIBITED)
            else:
                alarm_context = self._alarm_context or self._context_from_active_zones()
                self._log_activity("alarm activated")
                await self.async_send_notification(
                    NOTIFICATION_ALARM, alarm_context
                )
                self._alarm_context = alarm_context if self._active_zones() else None

        self._notify_listeners()

    async def async_send_notification(
        self,
        notification_key: str,
        context: AlarmTriggerContext | None = None,
    ) -> None:
        """Send a throttled notification."""
        config = self._notification_config(notification_key)
        if not config or not config.service:
            return

        now = dt_util.utcnow()
        last = self._last_notification.get(notification_key)
        if last and now - last < timedelta(seconds=config.mute_seconds):
            return

        domain, _, service = config.service.partition(".")
        if not domain or not service:
            _LOGGER.warning("Invalid notification service configured: %s", config.service)
            return

        data: dict[str, Any] = {
            "message": self._notification_message(config, context),
        }
        if config.title:
            data["title"] = config.title

        extra: dict[str, Any] = {}
        if config.priority is not None:
            extra["priority"] = config.priority
        if config.sound:
            extra["sound"] = config.sound
        if extra:
            data["data"] = extra

        await self.hass.services.async_call(domain, service, data, blocking=False)
        self._last_notification[notification_key] = now

    def _notification_config(self, notification_key: str) -> NotificationConfig | None:
        """Return configured notification, with an inhibited fallback."""
        config = self.config.notifications.get(notification_key)
        if config:
            return config

        if notification_key == NOTIFICATION_ALARM_INHIBITED:
            alarm_config = self.config.notifications.get(NOTIFICATION_ALARM)
            if alarm_config:
                return replace(alarm_config, message="Alarm inhibited", priority=0)

        return None

    def _notification_message(
        self,
        config: NotificationConfig,
        context: AlarmTriggerContext | None,
    ) -> str:
        """Build a notification message with optional alarm context."""
        message = config.message or self.config.name
        if context is None:
            return message

        mode = STATE_TO_MODE.get(context.target_state)
        mode_name = self.config.modes.get(mode, mode) if mode else None
        state_value = getattr(context.target_state, "value", context.target_state)
        lines = [
            message,
            f"Mode: {mode_name or 'unknown'} ({mode or 'unknown'}, {state_value})",
            f"Zone: {context.zone or 'unknown'}",
            f"Active zones: {', '.join(context.active_zones) or 'none'}",
            f"Time: {dt_util.as_local(context.triggered_at).isoformat(timespec='seconds')}",
        ]
        return "\n".join(lines)

    def _active_zones(self) -> list[str]:
        """Return active zone names in configured order."""
        return [zone.name for zone in self.config.zones if self.zones_alarm[zone.name]]

    def _context_from_active_zones(self) -> AlarmTriggerContext | None:
        """Build alarm context from the current active zones."""
        active_zones = self._active_zones()
        if not active_zones or self.target_state == STATE_DISARMED:
            return None

        return AlarmTriggerContext(
            zone=active_zones[0],
            target_state=self.target_state,
            active_zones=active_zones,
            triggered_at=dt_util.utcnow(),
        )

    def _clear_active_zones(self) -> None:
        """Clear all active zones."""
        self.zones_alarm = {zone.name: False for zone in self.config.zones}

    def _mode_label(self, state: Any) -> str:
        """Return a readable alarm mode label."""
        mode = STATE_TO_MODE.get(state)
        if mode:
            return self.config.modes.get(mode, mode)

        state_value = getattr(state, "value", state)
        return str(state_value)

    def _log_activity(self, message: str) -> None:
        """Write an alarm activity entry to Home Assistant Logbook."""
        try:
            from homeassistant.components.logbook import async_log_entry
        except ImportError:
            return

        async_log_entry(
            self.hass,
            name=self.config.name,
            message=message,
            domain=DOMAIN,
            entity_id="alarm_control_panel.zoned_security",
        )


def notification_from_config(data: dict[str, Any]) -> NotificationConfig:
    """Build notification config from YAML."""
    return NotificationConfig(
        service=data.get(CONF_NOTIFY_SERVICE),
        title=data.get(CONF_TITLE),
        message=data.get(CONF_MESSAGE),
        priority=data.get(CONF_PRIORITY),
        sound=data.get(CONF_SOUND),
        mute_seconds=data.get(CONF_MUTE_SECONDS, DEFAULT_MUTE_SECONDS),
    )
