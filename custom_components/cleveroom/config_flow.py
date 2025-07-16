"""Config flow for Cleveroom integration."""
import asyncio
import logging
from typing import Optional

import voluptuous as vol
from homeassistant import core
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TYPE,
    GATEWAY_TYPES,
    DEFAULT_PORT,
    CONF_SYSTEM_LEVEL,
    CONF_AUTO_CREATE_AREA,
    CREATE_AREA_OPTIONS,
    CONF_SECURE_CODE,
    SYSTEM_LEVEL_OPTIONS,
    CONF_ADAPTATION_HOMEKIT,
    ADAPTATION_HOMEKIT_OPTIONS,
)
from . import KLWBroadcast

_LOGGER = logging.getLogger(__name__)

# 1. 基本模式
# BASE_USER_DATA_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_GATEWAY_ID): str,
#         vol.Required(CONF_GATEWAY_TYPE): vol.In(GATEWAY_TYPES),
#         vol.Required(CONF_HOST): str,
#         vol.Required(CONF_PORT): int,
#         vol.Required(CONF_PASSWORD): str,
#         vol.Required(CONF_AUTO_CREATE_AREA): vol.In(CREATE_AREA_OPTIONS),
#         vol.Required(CONF_SYSTEM_LEVEL): vol.In(SYSTEM_LEVEL_OPTIONS),
#         vol.Optional(CONF_SECURE_CODE): str,  # secure_code 现在是可选的
#     }
# )
#
#
# def secure_code_if_gateway_type_1(value):
#     """Validate secure_code is provided if gateway_type is 1."""
#     gateway_type = value.get(CONF_GATEWAY_TYPE)
#     secure_code = value.get(CONF_SECURE_CODE)
#
#     if gateway_type == 1 and not secure_code:
#         raise vol.Invalid(
#             "secure_code is required when gateway_type is 1"
#         )
#     return value
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GATEWAY_ID): str,
        vol.Required(CONF_GATEWAY_TYPE): vol.In(GATEWAY_TYPES),
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): int,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SECURE_CODE): str,
        vol.Required(CONF_AUTO_CREATE_AREA): vol.In(CREATE_AREA_OPTIONS),
        vol.Required(CONF_ADAPTATION_HOMEKIT): vol.In(ADAPTATION_HOMEKIT_OPTIONS),
        # vol.Required(CONF_SYSTEM_LEVEL): vol.In(SYSTEM_LEVEL_OPTIONS),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cleveroom."""
    VERSION = 1

    def __init__(self):
        self.discovered_devices = None
        self.device_options = None  # 添加 device_options 属性
        self._discovery_task = None  # 添加 _discovery_task 属性
        self._selected_device = None  # 添加 _selected_device 属性
        self.gateway_type = 1

    async def async_step_user(self, user_input: Optional[dict] = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            try:
                # If validation succeeds, create the config entry
                sid = user_input[CONF_GATEWAY_ID]
                # chheck if sid is already in use
                entries = self._async_current_entries()
                for entry in entries:
                    if entry.data[CONF_GATEWAY_ID] == sid:
                        return self.async_abort(reason="Already Configured")

                user_input[CONF_GATEWAY_TYPE] = self.gateway_type
                return self.async_create_entry(
                    title=f"Cleveroom Device ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            except Exception as ex:
                _LOGGER.error("Error setting up device: %s", str(ex))

        return await self.async_step_discovery()

    async def async_step_discovery(self, user_input: Optional[dict] = None) -> FlowResult:
        """Handle the device discovery step."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover_devices()
            )

        if self._discovery_task.done():
            try:
                self.discovered_devices = await self._discovery_task
            except Exception as err:
                _LOGGER.error(f"Error discovering devices: {err}")
                return self.async_abort(reason="discovery_failed")

            if not self.discovered_devices:
                return self.async_abort(reason="no_devices_found")

            self.device_options = {}
            for device in self.discovered_devices:
                if (device["mac"] == '00-00-00-00-00-00'
                        or device["mac"] == '00-00-00-00-00-01'):
                    self.device_options[device["mac"]] = f"{device['devName']}"
                else:
                    self.device_options[device["mac"]] = (f"{device['devName']} "
                                                          f"({device['ip']}:{device['localport']})")

            return self.async_show_progress_done(next_step_id="device_picker")

        return self.async_show_progress(
            step_id='discovery',
            progress_task=self._discovery_task,
            progress_action="discovering",
        )

    async def _async_discover_devices(self):
        """Discover devices."""
        await asyncio.sleep(1)
        broadcast = KLWBroadcast()
        broadcast.init()
        discovered_devices = broadcast.search()
        # add a default device to the top
        default_device1 = {'ip': '', 'devName': 'Next Step (Client)',
                           'localport': 4196, 'destport': 0,
                           'groupip': '230.90.76.1', 'version': 'V1.587',
                           'mac': '00-00-00-00-00-01', 'sid': '',
                           'workmodel': 1}
        default_device2 = {'ip': '', 'devName': 'Next Step (Server)',
                           'localport': 4196, 'destport': 0,
                           'groupip': '230.90.76.1', 'version': 'V1.587',
                           'mac': '00-00-00-00-00-00', 'sid': '',
                           'workmodel': 0}
        discovered_devices.insert(0, default_device2)
        discovered_devices.insert(0, default_device1)
        return discovered_devices

    async def async_step_device_picker(self,
                                       user_input: Optional[dict] = None) -> FlowResult:
        """Show the device selection form."""
        errors = {}

        if user_input is not None:
            try:
                self._selected_device = next(
                    device for device in self.discovered_devices
                    if device["mac"] == user_input["device"]
                )
                return await self.async_step_config_options()
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        if not self.device_options:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="device_picker",  # 指定 step_id
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(self.device_options)  # 使用 device_options
            }),
            errors=errors,
        )

    async def async_step_config_options(self,
                                        user_input: Optional[dict] = None) -> FlowResult:
        """Handle the configuration options step."""
        errors = {}

        if user_input is not None:
            try:
                # 获取之前选择的设备信息
                #  从 _selected_device 中获取配置信息
                gateway_id = self._selected_device["sid"]

                # 合并设备信息和配置选项
                final_data = {
                    **{'gateway_id': gateway_id, **user_input}
                }

                return self.async_create_entry(title=f"Cleveroom ({final_data['gateway_id']})",
                                               data=final_data)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        else:
            # 显示配置选项表单
            #  从 _selected_device 中获取配置信息
            gateway_id = self._selected_device["sid"]
            gateway_type = self._selected_device["workmodel"]
            host = self._selected_device["ip"]
            port = self._selected_device["localport"]
            default_values = {
                CONF_GATEWAY_ID: gateway_id,
                CONF_GATEWAY_TYPE: gateway_type,
                CONF_HOST: host,
                CONF_PORT: port,
            }
            self.gateway_type = gateway_type
            return self.async_show_form(
                step_id="user", data_schema=self.get_config_options_schema(default_values), errors=errors
            )

    def get_config_options_schema(self, default_values: dict) -> vol.Schema:
        """Return a schema for the configuration options."""
        gw_type = default_values.get(CONF_GATEWAY_TYPE, 1)
        if gw_type == 1:
            return vol.Schema(
                {
                    vol.Required(CONF_GATEWAY_ID, default=default_values.get(CONF_GATEWAY_ID, "")): str,
                    vol.Required(CONF_HOST, default=default_values.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=default_values.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SECURE_CODE): str,
                    vol.Required(CONF_AUTO_CREATE_AREA): vol.In(CREATE_AREA_OPTIONS),
                    vol.Required(CONF_ADAPTATION_HOMEKIT): vol.In(ADAPTATION_HOMEKIT_OPTIONS),
                }
            )
        else:
            return vol.Schema(
                {
                    vol.Required(CONF_GATEWAY_ID, default=default_values.get(CONF_GATEWAY_ID, "")): str,
                    vol.Required(CONF_HOST, default=default_values.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=default_values.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Required(CONF_PASSWORD): str,
                    # vol.Optional(CONF_SECURE_CODE): str,
                    vol.Required(CONF_AUTO_CREATE_AREA): vol.In(CREATE_AREA_OPTIONS),
                    vol.Required(CONF_ADAPTATION_HOMEKIT): vol.In(ADAPTATION_HOMEKIT_OPTIONS),
                }
            )
