"""
Cleveroom ventilation platform.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast, Optional, Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity
from . import  ENTITY_REGISTRY, KLWIOTClient, device_registry_area_update, DeviceType, is_fan, generate_object_id
from .const import DOMAIN
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cleveroom ventilation devices."""
    gateway_data = hass.data[DOMAIN][entry.entry_id]
    devices = gateway_data["devices"]
    client = gateway_data["client"]
    gateway_id = gateway_data["gateway_id"]
    auto_area = gateway_data["auto_area"]
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    ventilations = []
    for device in devices:
        try:
            if is_fan(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                ventilation = CleveroomFan(hass, device, client, gateway_id,auto_area)
                ventilations.append(ventilation)

                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][ventilation.unique_id] = ventilation
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                f"error message: {e}")

    async_add_entities(ventilations)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_fan(device):
                    _LOGGER.info(f"add ventilation new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    ventilation = CleveroomFan(hass, device, client, gateway_id,auto_area)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [ventilation], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][ventilation.unique_id] = ventilation
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                                f"error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomFan(KLWEntity,FanEntity):
    """Representation of a Cleveroom ventilation device."""

    def __init__(self, hass, device, client, gateway_id, auto_area):
        """Initialize the ventilation device."""
        super().__init__(hass, device, client, gateway_id, auto_area)

        self.entity_id = f"fan.{self._object_id}"

        self._is_on = False
        self._speed = 0  #
        self._attr_speed_count = 3

        self._attr_supported_features = (
                FanEntityFeature.TURN_ON |
                FanEntityFeature.TURN_OFF |
                FanEntityFeature.SET_SPEED
        )
        self._attr_speed_count = 3

        self.init_or_update_entity_state(device)

    def init_or_update_entity_state(self, device):

        self._device = device
        detail = device["detail"]
        # 读取设备状态
        self._is_on = detail.get("on", False)
        #speed 1-3 ->0~2
        if detail.get("speed") is not None:
            v = detail.get("speed")
            if 1 <= v <= 3:
                self._speed = v

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def percentage(self) -> str | None:
        speeds = [0,33, 66, 100]
        return speeds[self._speed]

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    async def async_turn_on(self, speed: Optional[str] = None,
                            percentage: Optional[int] = None,
                            preset_mode: Optional[str] = None,
                            **kwargs: Any) -> None:
        """Turn the ventilation on."""
        _LOGGER.debug(f"Turning on ventilation {self._oid}")
        try:
            self._client.controller.control("DeviceOn", [{"oid": self._oid}])
            self._is_on = True
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn on ventilation {self._oid}: {e}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ventilation off."""
        _LOGGER.debug(f"Turning off ventilation {self._oid}")
        try:
            self._client.controller.control("DeviceOff", [{"oid": self._oid}])
            self._is_on = False
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off ventilation {self._oid}: {e}")

    async def async_set_percentage(self, percentage: int):
        """Set the speed of the ventilation."""
        _LOGGER.debug(f"Setting speed to {percentage} for ventilation {self._oid}")
        try:
            # 0~100 to 4 gears => 0，1，2，3
            if percentage == 0:
                await self.async_turn_off()
                return
            elif percentage <= 33:
                cleveroom_speed = 0
            elif percentage <= 66:
                cleveroom_speed = 1
            else:
                cleveroom_speed = 2
            if not self._is_on:
                await self.async_turn_on()
            self._client.controller.control(
                "SetSpeed", [{"oid": self._oid, "value": cleveroom_speed}])
            # 判断是否打开
            self._speed = cleveroom_speed
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error(f"Failed to set speed for ventilation {self._oid}: {e}")

