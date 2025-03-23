"""
Integrate Cleveroom into Home Assistant.

For more detailed information, please refer to: https://www.cleveroom.com
"""

import asyncio
import logging
from typing import cast

import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD
from homeassistant.helpers import translation

from .const import CONF_GATEWAY_ID, CONF_GATEWAY_TYPE, CONF_AUTO_CREATE_AREA, MANUAL_CREATE_AREA, DOMAIN, \
    GATEWAY_TYPE_SERVER, CONF_SECURE_CODE, GATEWAY_TYPES, CLIENTS_REGISTRY
from .services import async_register_services
from .klwiot import (KLWIOTClientLC, KLWIOTClient, KLWBroadcast, DeviceType, has_method
, BucketDataManager)

_LOGGER = logging.getLogger(__name__)

# leveroom has implemented most platforms, but the "remote" platform is poorly supported.Therefore, we use 'event' instead of 'remote'.
# so integration is paused.
PLATFORMS = ["light", "sensor", "climate", "cover", "switch", "binary_sensor", "fan"
    , "button", "alarm_control_panel","scene", "media_player","event"]
# PLATFORMS = ["event","button"]
ENTITY_REGISTRY = {}


async def async_setup_entry(hass: HomeAssistant,
                            entry: ConfigEntry) -> bool:
    """Set up Cleveroom from a config entry."""
    gateway_id = entry.data[CONF_GATEWAY_ID]
    gateway_type = entry.data[CONF_GATEWAY_TYPE]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    auto_area = entry.data.get(CONF_AUTO_CREATE_AREA, MANUAL_CREATE_AREA)
    language = hass.config.language

    await translation.async_load_integrations(hass, {DOMAIN})

    _LOGGER.info(
        f"Initialize Cleveroom Gateway：{gateway_id}，"
        f"type：{GATEWAY_TYPES[gateway_type]}，address：{host}:{port} language:{language}")
    # zh-Hans

    file_path = f'./{gateway_id}.json'  # Construct the file path
    bucket_data_manager = BucketDataManager(file_path)

    @callback
    def data_changed_callback():
        """Callback to save data when it changes."""
        if device_bucket:
            asyncio.run_coroutine_threadsafe(
                bucket_data_manager.async_save_data(device_bucket.get_bucket()), hass.loop)

    client = None
    if gateway_type == GATEWAY_TYPE_SERVER:
        client = KLWIOTClient(
            host=host,
            port=port,
            client_id=gateway_id,
            password=password,
            system_level=2,
            connect_timeout=10,
            reconnect_interval=15,
            keeplive=True,
            language=language,
            bucket_manager=bucket_data_manager,
            data_changed_callback=data_changed_callback,
        )
    else:
        secure_code = entry.data[CONF_SECURE_CODE]
        client = KLWIOTClientLC(
            host=host,
            port=port,
            client_id=gateway_id,
            password=password,
            code=secure_code,
            system_level=2,
            connect_timeout=10,
            reconnect_interval=15,
            keeplive=True,
            language=language,
            bucket_manager=bucket_data_manager,
            data_changed_callback=data_changed_callback,
        )
    # client.enable_logger()
    device_bucket = client.devicebucket
    await device_bucket.async_load_data()
    # add the listener for client
    client.on("on_login_success", on_login_success)
    client.on("on_login_failed", on_login_failed)
    client.on("on_connect_change", on_connect_change)

    # Save gateway.py data to hass.data,it's support multiple gateways
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "gateway_id": gateway_id,
        "gateway_type": gateway_type,
        "host": host,
        "port": port,
        "password": password,
        "client": client,
        "auto_area": auto_area,
        "devices": [],
    }
    #save client to CLIENTS_REGISTRY
    CLIENTS_REGISTRY[gateway_id] = client

    # connect_result = await hass.async_add_executor_job(client.connect)
    if not await hass.async_add_executor_job(client.connect):
        _LOGGER.error("Cleveroom connect failure")
        return False
    await discover_cleveroom_devices(hass, entry, client)
    # 创建 Cleveroom 网关设备

    # Register platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # register listener after all flatfroms config
    client.on("on_device_change", on_device_change_wrapper(hass, entry))

    # register services
    await async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """
        Unload a config entry.
        Note: it will be called when the integration is removed or reload from the UI.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client = hass.data[DOMAIN][entry.entry_id]["client"]  # 使用 entry.entry_id 获取正确的 client
        # clean cache
        client.devicebucket.clear_bucket()
        # stop client
        client.stop()
        # remove the client from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def get_translation(hass: HomeAssistant, key: str, default_value) -> str:
    """
    Get the translation for a given key.
    """
    language = hass.config.language
    translations = translation.async_get_cached_translations(
        hass, language, DOMAIN
    )
    return translations.get(f"component.{DOMAIN}.cleveroom.{key}", default_value)


async def discover_cleveroom_devices(hass: HomeAssistant, entry: ConfigEntry, client: KLWIOTClient):
    """Discover Cleveroom devices."""
    _LOGGER.info("discover_ Cleveroom devices...")
    try:
        await asyncio.sleep(5)  # waiting 5s
        # Not all devices in the bucket are supported. ！！！
        devices = client.devicebucket.get_bucket_values()
        _LOGGER.debug(f"Discovered {len(devices)} devices")
        # Save devices to hass.data
        hass.data[DOMAIN][entry.entry_id]["devices"] = devices
        return devices
    except Exception as e:
        _LOGGER.exception(f"Discover Cleveroom Failure: {e}")
        return []


def on_login_success():
    """
    Cleveroom Login Success
    """
    _LOGGER.info("Cleveroom Login Succcess")


def on_login_failed():
    """
    Cleveroom Login Failed
    """
    _LOGGER.error("Cleveroom Login Failure")


def on_connect_change(state):
    """
    Cleveroom Connect State Change
    """
    _LOGGER.info(f"Cleveroom connect state Change to: {state}")


def on_device_change_wrapper(hass: HomeAssistant, entry: ConfigEntry):
    """
    Cleveroom Device Change
    """
    def on_device_change(device, is_new):
        oid = device.get("oid")
        entity = ENTITY_REGISTRY.get(entry.entry_id, {}).get(oid)
        if entity:
            #trigger event
            if is_event(device) and has_method(entity, 'trigger_event'):
                asyncio.run_coroutine_threadsafe(entity.trigger_event(), hass.loop)

            if not is_new:
                # entity.init_or_update_entity_state(device)
                asyncio.run_coroutine_threadsafe(entity.async_update(), hass.loop)

            # if is_event(device):
            #     hass.bus.async_fire("cleveroom_scene_activated", {"oid": oid})
        else:
            pass

    return on_device_change


async def device_registry_area_update(
        floor_registry, area_registry, device_registry, entry, device):
    """Update the area of the device."""
    floor_name = device["detail"].get("fName", "")
    room_name = device["detail"].get("rName", "")
    device_name = device["detail"].get("dName", "")
    # fid=0 and rid=0 is no need to create area,it's a global device
    if device["detail"]["fid"] == 0 or device["detail"]["rid"] == 0:
        return
    try:
        fid = device["detail"]["fid"]

        floor_area = floor_registry.async_get_floor_by_name(floor_name)
        if floor_area is None:
            floor_area = floor_registry.async_create(name=floor_name, level=fid)
            _LOGGER.info("Create floor area: %s",floor_name)

        room_area = area_registry.async_get_area_by_name(room_name)
        if room_area is None:
            room_area = area_registry.async_create(name=room_name, floor_id=floor_area.floor_id)
            _LOGGER.info("Create room area: %s",room_name)

        # binding area and floor
        area_registry.async_update(
            area_id=room_area.id,
            floor_id=floor_area.floor_id,
        )
        new_device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device["oid"])},
            name=f"{floor_name} {room_name} {device_name}".strip(),
            manufacturer="Cleveroom",
            model="Generic"
        )
        # 更新设备信息，设置 area_id
        device_registry.async_update_device(
            new_device.id,
            area_id=room_area.id,
        )
    except Exception as e:
        _LOGGER.error(f"Generate area failure: {e}", device)


def is_light(device):
    """Check if the device is a light."""
    return device["detail"]["category"] in [
        DeviceType.TOGGLE_LIGHT,
        DeviceType.ADJUST_LIGHT,
        DeviceType.RGB_LIGHT,
        DeviceType.WARM_LIGHT,
        DeviceType.RGBW_LIGHT,
    ]


def is_sensor(device):
    """Check if the device is a sensor."""
    detail = device["detail"]
    category = detail["category"]
    twoside = detail.get("twoside", False)
    return category == DeviceType.SENSOR and twoside is False


def is_climate(device):
    """Check if the device is a climate control device."""
    return device["detail"]["category"] == DeviceType.AIR_CONDITION


def is_cover(device):
    """Check if the device is a cover."""
    return device["detail"]["category"] == DeviceType.CURTAIN


def is_switch(device):
    """Check if the device is a switch."""
    return device["detail"]["category"] == DeviceType.TOGGLE


def is_binary_sensor(device):
    """Check if the device is a binary sensor."""
    detail = device["detail"]
    category = detail["category"]
    twoside = detail.get("twoside", False)
    is_binary = twoside or category == DeviceType.DRY
    return (category in (DeviceType.SENSOR,DeviceType.DRY)) and is_binary


def is_fan(device):
    """Check if the device is a fan."""
    return device["detail"]["category"] == DeviceType.FRESH_AIR


def is_alarm_control_panel(device):
    """Check if the device is an alarm control panel."""
    return (
            device["detail"]["category"] == DeviceType.SECURITY
            and device["detail"]["uid"] == "243"
    )


def is_scene(device):
    """Check if the device is a scene."""
    return device["detail"]["category"] == DeviceType.SCENE


def is_media_player(device):
    """Check if the device is a media player."""
    return (
            device["detail"]["category"] == DeviceType.MUSIC_PLAYER and device["type"] == 3
    )


def is_heater(device):
    """Check if the device is a heater."""
    return device["detail"]["category"] == DeviceType.FLOOR_HEATING

def is_event(device):
    """Check if the device is an event."""
    return device["detail"]["category"] == DeviceType.EVENT

def generate_object_id( oid: str,prefix:str = 'entity',) -> str:
    """
    Generate a unique object ID for the entity.
    """
    # object_id = f"entity_{oid.lower().replace("-", "_").replace(".", "_")}"
    object_id = "{}_{}".format(prefix,oid.lower().replace("-", "_").replace(".", "_"))
    object_id = re.sub(r'[^a-z0-9_]', '', object_id)
    return object_id
