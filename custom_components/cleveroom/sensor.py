"""
Cleveroom integration for Home Assistant - Sensor
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    UnitOfTemperature,
    SensorStateClass,  # Import SensorStateClass
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
from homeassistant.config_entries import ConfigEntry  # Import ConfigEntry

from .base import KLWEntity
from . import ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, is_scene, is_sensor, \
    generate_object_id
from .const import DOMAIN
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

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
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    sensors = []
    for device in devices:
        try:
            if is_sensor(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                sensor = CleveroomSensor(hass, device, client, gateway_id,auto_area)
                sensors.append(sensor)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][sensor.unique_id] = sensor
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(sensors)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_sensor(device):
                    _LOGGER.info(f"add sensor new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    sensor = CleveroomSensor(hass, device, client, gateway_id,auto_area)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [sensor], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][sensor.unique_id] = sensor
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                                f"error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomSensor(KLWEntity,SensorEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area):
        super().__init__(hass, device, client, gateway_id, auto_area)

        self.entity_id = f"sensor.{self._object_id}"

        self._unit = ''
        self._value = 0
        self._did = device["detail"]["did"]

        if self._did == 20:  # temperature
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 22:  # humidity
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 21:  # illuminance
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
            self._attr_unit_of_measurement = "lx"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 135:  # air quality
            self._attr_device_class = SensorDeviceClass.AQI
            self._attr_unit_of_measurement = ""
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 120:  # PM2.5
            self._attr_device_class = SensorDeviceClass.PM25
            self._attr_unit_of_measurement = "ug/m3"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 121:  # CO2
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_unit_of_measurement = "ppm"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 123:  # CO
            self._attr_device_class = SensorDeviceClass.CO
            self._attr_unit_of_measurement = "ppm"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 124:  # formaldehyde
            self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
            self._attr_unit_of_measurement = "µg/m³"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 126:  # noise
            self._attr_device_class = SensorDeviceClass.SOUND_PRESSURE
            self._attr_unit_of_measurement = "dB"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 128:  # pressure
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_unit_of_measurement = "kPa"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 40:  #
            self._attr_device_class = SensorDeviceClass.WIND_SPEED
            self._attr_unit_of_measurement = "m/s"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 42:  # rain
            self._attr_device_class = SensorDeviceClass.PRECIPITATION
            self._attr_unit_of_measurement = "mm"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 43:  # UV
            self._attr_device_class = SensorDeviceClass.IRRADIANCE
            self._attr_unit_of_measurement = "W/m²"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 44:  # illuminance
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
            self._attr_unit_of_measurement = "lx"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._did == 45:  # pressure
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_unit_of_measurement = "kPa"
            self._attr_state_class = SensorStateClass.MEASUREMENT

        else:  # other sensor
            self._attr_device_class = None
            self._attr_unit_of_measurement = None
            self._attr_state_class = None

        self.init_or_update_entity_state(device)

    def init_or_update_entity_state(self, device):

        self._device = device
        detail = device["detail"]
        self._value = detail["value"]

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    @property
    def native_value(self):
        return self._value

    @property
    def native_unit_of_measurement(self):
        return self._attr_unit_of_measurement

