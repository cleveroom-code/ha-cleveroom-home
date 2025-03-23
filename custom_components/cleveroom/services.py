"""Services for Cleveroom integration."""
import logging
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .klwiot import  KLWIOTClient
from .const import DOMAIN,CLIENTS_REGISTRY
_LOGGER = logging.getLogger(__name__)

SERVICE_REMOTE_COMMAND_SCHEMA = vol.Schema({
    vol.Required("gateway_id"):  cv.string,
    vol.Required("action"): cv.string,
    vol.Optional("payload"): vol.Any(dict, list, None)
})

async def async_register_services(hass: HomeAssistant):
    """Register services for Cleveroom integration."""
    
    async def handle_remote_command(call: ServiceCall):
        """Handle remote command service."""
        gateway_id = call.data["gateway_id"]
        if gateway_id not in CLIENTS_REGISTRY:
            _LOGGER.error(f"Gateway ID {gateway_id} not found in CLIENTS_REGISTRY")
            return

        client = cast(KLWIOTClient, CLIENTS_REGISTRY[gateway_id])

        action = call.data["action"]
        payload = call.data.get("payload", {})
        _LOGGER.debug(f"Received remote command for {gateway_id}: {action} with payload {payload}")
        # 处理服务调用
        if action is None or payload is None:
            _LOGGER.error("Action and payload cannot be both None")
            return
        client.controller.control(action, payload)
    
    # 注册服务
    hass.services.async_register(
        DOMAIN,
        "remote_command",
        handle_remote_command,
        schema=SERVICE_REMOTE_COMMAND_SCHEMA
    )