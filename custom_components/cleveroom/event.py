"""
Cleveroom integration for Home Assistant - Binary Sensor
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.const import (
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from . import (DOMAIN, ENTITY_REGISTRY, KLWIOTClient, DeviceType,
               device_registry_area_update, is_event,
               generate_object_id)
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # Changed to async_setup_entry
        hass: HomeAssistant,
        entry: ConfigEntry,  # Added entry: ConfigEntry
        async_add_entities: AddEntitiesCallback,
) -> None:
    gateway_data = hass.data[DOMAIN][entry.entry_id]  # Access data from entry
    devices = gateway_data["devices"]
    client = gateway_data["client"]
    gateway_id = gateway_data["gateway_id"]
    auto_area = gateway_data["auto_area"]
    # floor_registry = fr.async_get(hass)
    # area_registry = ar.async_get(hass)
    # device_registry = dr.async_get(hass)
    events = []
    for device in devices:
        try:
            if is_event(device):
                event = CleveroomEvent(hass, device, client, gateway_id,auto_area)
                events.append(event)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][event.unique_id] = event
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}"
                f", error message: {e}")

    async_add_entities(events)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_event(device) and device["oid"] not in ENTITY_REGISTRY[entry.entry_id]:
                    _LOGGER.info(f"add event new devices: {device['oid']}")
                    event = CleveroomEvent(hass, device, client, gateway_id,auto_area)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(
                            hass, async_add_entities, [event], False), hass.loop)

                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][event.unique_id] = event

            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')},"
                                f" error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomEvent(EventEntity):
    """Representation of a  Binary Sensor."""

    def __init__(self, hass, device, client, gateway_id, auto_area):
        """Initialize the KLW entity."""
        self.hass = hass
        self._client = cast(KLWIOTClient, client)
        self._device = device
        self._oid = device["oid"]
        detail = device["detail"]
        self._full_name = detail['name']
        self._object_id = generate_object_id( self._oid,'event')
        self._name = self._full_name

        self._attr_device_class = EventDeviceClass.BUTTON
        self._attr_event_types = ["cleveroom_event"]
        # if auto_area == 1:
        #     self._attr_device_info = DeviceInfo(
        #         identifiers={(DOMAIN, self._oid)},
        #         name=self._full_name,
        #         manufacturer="Cleveroom",
        #         model="Generic"
        #     )
        # else:

        self._attr_device_info = None
        self.init_or_update_entity_state(device)

    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]
        self._name = detail["name"]

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._oid

    @property
    def name(self) -> str:
        return self._name

    async def trigger_event(self):
        """
        Trigger an event.
        """
        try:
            self._trigger_event("cleveroom_event", {"extra_data": self._oid})
            # 使用事件总线
            self.async_write_ha_state()
            _LOGGER.debug(f"Entity {self._oid} {self.name}  event triggered!")

        except Exception as e:
            _LOGGER.error(f"Failed to update entity {self._oid}  {self.name}  [{self.entity_id}] : {e}")

    async def async_update(self):
        """
        Update the entity state.
        """
        pass