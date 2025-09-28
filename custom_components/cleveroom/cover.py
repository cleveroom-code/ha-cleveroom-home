"""
Cleveroom cover platform.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry  # Import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity
from . import  KLWIOTClient, ENTITY_REGISTRY, device_registry_area_update, DeviceType, is_cover, \
    generate_object_id
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # Changed to async_setup_entry
        hass: HomeAssistant,
        entry: ConfigEntry,  # Added entry: ConfigEntry
        async_add_entities: AddEntitiesCallback,
) -> None:
    gateway_data = hass.data[DOMAIN][entry.entry_id]  # Access data from entry
    devices = gateway_data["devices"]
    gateway_id = gateway_data["gateway_id"]
    auto_area = gateway_data["auto_area"]
    adapted_homekit = gateway_data["adapted_homekit"]
    predictive_feedback = gateway_data["predictive_feedback"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    # If adapted_homekit is enabled, do not setup cover entities
    if adapted_homekit == 1:
        _LOGGER.debug("adapted_homekit is enabled, not setup cover entities")
        return

    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    covers = []
    for device in devices:
        try:
            if is_cover(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                cover = CleveroomCover(hass, device, client, gateway_id,auto_area,predictive_feedback)
                covers.append(cover)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][cover.unique_id] = cover
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(covers)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_cover(device):
                    _LOGGER.info(f"add cover new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    cover = CleveroomCover(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [cover], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][cover.unique_id] = cover
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomCover(KLWEntity,CoverEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self.entity_id = f"cover.{self._object_id}"

        self._is_on = False
        self._scale = 0
        self._current_cover_position = 0

        self.init_or_update_entity_state(device)

        self._error_message = None
        # 设置支持的功能
        if device['detail'].get("scale", 255)<=10:
            self._attr_supported_features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.SET_POSITION
                | CoverEntityFeature.STOP
            )
        else:
            self._attr_supported_features = (
                    CoverEntityFeature.OPEN
                    | CoverEntityFeature.CLOSE
                    | CoverEntityFeature.STOP
            )

    def init_or_update_entity_state(self, device):

        self._device = device

        self._is_on = device["detail"].get("on", self._is_on)
        self._scale = device["detail"].get("scale", self._scale)
        self._current_cover_position = self._scale * 10  # transform to 0-100


    @property
    def current_cover_position(self) -> int | None:
        """cover postion 0-100."""
        return self._current_cover_position

    @property
    def extra_state_attributes(self):
        if self._error_message:
            return {"error_message": self._error_message}
        return None

    async def async_open_cover(self, **kwargs):
        _LOGGER.debug(f"open cover: {self._oid}")
        self._client.controller.control("ShadeOpen", [{"oid": self._oid}])
        self._scale = 10
        self._current_cover_position = 100
        self._is_on = True
        self.set_device_detail_field("on", True)
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        _LOGGER.debug(f"close cover: {self._oid}")
        self._client.controller.control("ShadeClose", [{"oid": self._oid}])
        self._scale = 0
        self._current_cover_position = 0
        self._is_on = False
        self.set_device_detail_field("on", False)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        _LOGGER.debug(f"stop cover: {self._oid}")
        self._client.controller.control("ShadePause", [{"oid": self._oid}])
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        if "position" in kwargs:
            position = kwargs["position"]
            _LOGGER.debug(f"set cover position: {self._oid}, position: {position}")
            self._client.controller.control("SetShadeScale", [{"oid": self._oid, "value": position}])
            scale = int(position / 10)
            self._scale = scale
            self._current_cover_position = position
            self.set_device_detail_field("scale", scale)
            self.async_write_ha_state()

    @property
    def current_cover_position(self):
        return self._current_cover_position

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return None

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return None

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._current_cover_position == 0
