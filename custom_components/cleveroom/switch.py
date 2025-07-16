"""
Cleveroom integration for Home Assistant - Switch
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from config.custom_components.cleveroom import is_cover
from .base import KLWEntity
from . import ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, is_switch, \
    generate_object_id
from .const import DOMAIN
_LOGGER = logging.getLogger(__name__)


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
    adapted_homekit = gateway_data["adapted_homekit"]
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    switches = []
    for device in devices:
        cover_to_switch = False
        if adapted_homekit == 1 and is_cover(device):
            _LOGGER.debug("adapted_homekit is enabled, cover will be treated as switch")
            cover_to_switch = True

        try:
            if is_switch(device) or cover_to_switch:
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                toggle = CleveroomSwitch(hass, device, client, gateway_id,auto_area)
                switches.append(toggle)

                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][toggle.unique_id] = toggle
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(switches)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_switch(device):
                    _LOGGER.info(f"add switch new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    toggle = CleveroomSwitch(hass, device, client, gateway_id,auto_area)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [toggle], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][toggle.unique_id] = toggle
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                                f"error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomSwitch(KLWEntity,SwitchEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area):
        super().__init__(hass, device, client, gateway_id, auto_area)

        self.entity_id = f"switch.{self._object_id}"

        self._is_on = False
        self.init_or_update_entity_state(device)


    def init_or_update_entity_state(self, device):

        self._device = device
        detail = device["detail"]

        self._is_on = detail.get("on", self._is_on)

    @property
    def unique_id(self) -> str:
        return self._oid

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    async def async_turn_on(self, **kwargs):
        self._client.controller.control("DeviceOn", [{"oid": self._oid}])
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._client.controller.control("DeviceOff", [{"oid": self._oid}])
        self.async_write_ha_state()
