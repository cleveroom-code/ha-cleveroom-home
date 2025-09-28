"""
Platform for alarm control panel integration.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
from enum import StrEnum
from typing import cast

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity)
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature, CodeFormat)
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import logging

from .base import KLWEntity
from .const import DOMAIN
from . import ( KLWIOTClient, ENTITY_REGISTRY,
               get_translation, is_alarm_control_panel, generate_object_id)

_LOGGER = logging.getLogger(__name__)

#add AlarmControlPanelState Enum ,it's the same as the one in homeassistant,but compatible with older versions
class AlarmControlPanelState(StrEnum):
    """Alarm control panel entity states."""

    DISARMED = "disarmed"
    ARMED_HOME = "armed_home"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"
    ARMED_VACATION = "armed_vacation"
    ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
    PENDING = "pending"
    ARMING = "arming"
    DISARMING = "disarming"
    TRIGGERED = "triggered"


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    gateway_data = hass.data[DOMAIN][entry.entry_id]
    devices = gateway_data["devices"]
    client = gateway_data["client"]
    gateway_id = gateway_data["gateway_id"]
    auto_area = gateway_data["auto_area"]
    predictive_feedback = gateway_data["predictive_feedback"]
    securitys = []

    for device in devices:
        try:
            if is_alarm_control_panel(device):
                security = CleveroomAlarmControlPanel(hass, device, client, gateway_id,auto_area,predictive_feedback)
                securitys.append(security)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][security.unique_id] = security
        except Exception as e:
            _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(securitys)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_alarm_control_panel(device):
                    _LOGGER.info(f"add alarm panel new devices: {device['oid']}")
                    security = CleveroomAlarmControlPanel(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [security], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][security.unique_id] = security
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async def async_add_entities_wrapper(hass, async_add_entities, entities,
                                         update_before_add = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomAlarmControlPanel(KLWEntity,AlarmControlPanelEntity):
    """Representation of a KLWIOT Alarm Control Panel."""

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback) -> None:
        """Initialize the alarm control panel."""
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self._attr_alarm_state = AlarmControlPanelState.DISARMED  # Initial state using _attr_alarm_state
        self._attr_name = get_translation(hass, "security_system_title", "Cleveroom Security System")
        self._name = self._attr_name
        self._attr_code_format = None  # Assuming numeric code
        self._attr_code_arm_required = False  # Code IS required for arming

        self.entity_id = f"alarm_control_panel.{self._object_id}"  # generate entity_id

        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
        )

        self.init_or_update_entity_state(device)


    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]

        self._attr_name = detail.get("coverName", "")
        state = detail.get("cover")

        if state == 2 or state == 0:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        elif state == 1:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED


    @property
    def code_format(self) -> CodeFormat | None:
        return self._attr_code_format

    @property
    def code_arm_required(self) -> bool:
        return self._attr_code_arm_required

    @property
    def alarm_state(self):
        """Return the state of the alarm control panel."""
        return self._attr_alarm_state

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.info("Send arm away command")
        try:
            self._client.controller.control("SetSecurity", [{"oid": self._oid, "value": 2}])
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"error: {e}")

    async def async_alarm_arm_home(self, code=None) -> None:
        """Send arm home command."""
        _LOGGER.info("Send arm home command")
        await self.async_alarm_arm_away(code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Send disarm command")
        try:
            self._client.controller.control("SetSecurity", [{"oid": self._oid, "value": 1}])
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"error: {e}")

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send trigger command."""
        _LOGGER.info("Send trigger command")
        try:
            self._client.controller.control("SetSecurity", [{"oid": self._oid, "value": 2}])
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"error: {e}")
