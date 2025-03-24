"""Services for Cleveroom integration."""
import logging
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from .klwiot import  KLWIOTClient
from .const import DOMAIN, CLIENTS_REGISTRY, GATEWAY_ID_TO_ENTRY_ID

_LOGGER = logging.getLogger(__name__)

SERVICE_REMOTE_COMMAND_SCHEMA = vol.Schema({
    vol.Required("gateway_id"):  cv.string,
    vol.Required("action"): cv.string,
    vol.Optional("payload"): vol.Any(dict, list, None)
})


def get_gateway_id_from_device_id(hass, device_id):
    """从 device_id 获取 gateway_id."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if not device:
        _LOGGER.error(f"设备 {device_id} 未找到")
        return None

    # 在标识符中寻找您的域
    for identifier in device.identifiers:
        # identifier 是一个元组 (domain, id)
        if identifier[0] == DOMAIN:
            return identifier[1]  # 这就是您的 gateway_id

    _LOGGER.error(f"设备 {device_id} 没有 {DOMAIN} 标识符")
    return None

async def async_register_services(hass: HomeAssistant):
    """Register services for Cleveroom integration."""

    async def handle_remote_command(call: ServiceCall):
        """Handle remote command service."""
        gateway_id = call.data["gateway_id"]
        # 转换 device_id 到 gateway_id
        if len(gateway_id)>12:
            gateway_id = get_gateway_id_from_device_id(hass, gateway_id)

        if not gateway_id or gateway_id not in CLIENTS_REGISTRY:
            _LOGGER.error(f"设备 {gateway_id} 没有对应的网关 ID 或网关未注册")
            return

        if gateway_id not in CLIENTS_REGISTRY:
            _LOGGER.error(f"Gateway ID {gateway_id} not found in CLIENTS_REGISTRY")
            return

        client = cast(KLWIOTClient, CLIENTS_REGISTRY[gateway_id])

        action = call.data["action"]
        payload = call.data.get("payload", {})
        _LOGGER.debug(f"Received remote command for {gateway_id}: {action} with payload {payload}")

        client.controller.control(action, payload)

    # 注册服务
    hass.services.async_register(
        DOMAIN,
        "remote_command",
        handle_remote_command,
        schema=SERVICE_REMOTE_COMMAND_SCHEMA
    )