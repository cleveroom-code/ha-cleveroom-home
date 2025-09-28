"""
Cleveroom Remote Platform
For more detailed information, please refer to: https://www.cleveroom.com
"""
import logging
from typing import cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.components.remote import (
    PLATFORM_SCHEMA,
    RemoteEntity,
    DEFAULT_DELAY_SECS, RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity
from . import  ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, generate_object_id
from .const import DOMAIN
_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"
CONF_COMMANDS = "commands"
CONF_STATE_ENTITY = "state_entity"
CONF_ACTIVITY_LIST = "activity_list"
CONF_TARGET_ENTITY = "target_entity"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_DEVICE): cv.string,
    vol.Optional(CONF_COMMANDS, default={}): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_STATE_ENTITY): cv.entity_id,
    # vol.Optional(CONF_ACTIVITY_LIST, default=[]): cv.ensure_list,
    # vol.Optional(CONF_TARGET_ENTITY): cv.entity_id,
})
# support max 24 keys
COMMANDS = {
    "key1": 0,
    "key2": 1,
    "key3": 2,
    "key4": 3,
    "key5": 4,
    "key6": 5,
    "key7": 6,
    "key8": 7,
    "key9": 8,
    "key10": 9,
    "key11": 10,
    "key12": 11,
    "key13": 12,
    "key14": 13,
    "key15": 14,
    "key16": 15,
    "key17": 16,
    "key18": 17,
    "key19": 18,
    "key20": 19,
    "key21": 20,
    "key22": 21,
    "key23": 22,
    "key24": 23
}
LANGUANG_RC = {
    "Back": 0,
    "Menu": 1,
    "V+": 2,
    "V-": 3,
    "←": 4,
    "→": 7,
    "↑": 5,
    "↓": 6,
    "OK": 8,
}


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
    remotes = []
    for device in devices:
        try:
            if device["detail"]["category"] == DeviceType.TOGGLE:  #
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                player = CleveroomRemote(hass, device, client, gateway_id,auto_area,predictive_feedback)
                remotes.append(player)

                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][player.unique_id] = player
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(remotes)


class CleveroomRemote(KLWEntity,RemoteEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):

        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self._full_name = f"{self._full_name} - RC".strip()
        self._object_id = generate_object_id(self._oid + "_RC")
        self.entity_id = f"remote.{self._object_id}"
        detail = device["detail"]

        self._name = self._full_name
        # 存储学习到的命令,0-23
        self._commands = COMMANDS
        self._current_activity = None
        self._activity_list = list(LANGUANG_RC.keys())
        self._target_entity = detail.get(CONF_TARGET_ENTITY)

    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]


    @property
    def current_activity(self):
        return self._current_activity

    async def async_turn_on(self, **kwargs):
        self._client.controller.control("DeviceOn", [{"oid": self._oid}])

    async def async_turn_off(self, **kwargs):
        self._client.controller.control("DeviceOff", [{"oid": self._oid}])

    async def async_send_command(self, command: list[str], **kwargs):
        for single_command in command:
            if single_command in self._commands:
                try:
                    ir_code = self._commands[single_command]
                    self._client.controller.control(
                        "SendRCKey", [{"oid": self._oid, "value": int(ir_code)}])
                    _LOGGER.info(f"发送命令: {single_command}")
                except Exception as e:
                    _LOGGER.error(f"发送命令失败: {e}")
            else:
                _LOGGER.warning(f"未知的命令: {single_command}")

    async def async_learn_command(
            self,
            command: str | None = None,
            alternative: str | None = None,
            timeout: int | None = None,
            device: str | None = None,
            **kwargs,
    ) -> None:
        _LOGGER.info(f"learn command: {command}")
