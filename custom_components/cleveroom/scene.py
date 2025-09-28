"""
Platform for scene integration.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast, Any

from homeassistant.components.scene import Scene
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity
from . import  ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, is_scene, \
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
    predictive_feedback = gateway_data["predictive_feedback"]
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    scenes = []
    for device in devices:
        try:
            if is_scene(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                scene = CleveroomScene(hass, device, client, gateway_id,auto_area,predictive_feedback)
                scenes.append(scene)

                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][scene.unique_id] = scene
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(scenes)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_scene(device):
                    _LOGGER.info(f"add scene new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    scene = CleveroomScene(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [scene], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][scene.unique_id] = scene
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                                f"error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomScene(KLWEntity,Scene):
    """Representation of a Cleveroom Scene."""

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback) -> None:
        """Initialize the scene."""
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        detail = device["detail"]
        fName = detail.get("fName", "")
        rName = detail.get("rName", "")
        dName = detail.get("dName", "")
        if detail['fid'] == 0:
            fName = ""
        if detail['rid'] == 0:
            rName = ""

        self._full_name = f"{fName} {rName} {dName}".strip()
        self.entity_id = f"scene.{self._object_id}"
        self._name = self._full_name

    def init_or_update_entity_state(self, device):
        # scene not support state
        pass

    @property
    def unique_id(self) -> str:
        return self._oid

    @property
    def name(self) -> str:
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    async def async_activate(self, **kwargs: Any) -> None:
        try:
            self._client.controller.control("SceneTrigger", [{"oid": self._oid}])
            _LOGGER.info(f"Scene {self._name} activated successfully.")
        except Exception as e:
            _LOGGER.error(f"Failed to activate scene {self._name}: {e}")
