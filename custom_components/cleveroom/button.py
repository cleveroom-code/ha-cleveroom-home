"""
Cleveroom Integration Button
For more detailed information, please refer to: https://www.cleveroom.com
"""
from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

import logging

from homeassistant.helpers.translation import async_get_translations

from . import ( ENTITY_REGISTRY, KLWIOTClient,
               DeviceType, get_translation)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    gateway_data = hass.data[DOMAIN][entry.entry_id]
    client = gateway_data["client"]
    gateway_id = gateway_data["gateway_id"]

    async_add_entities(
        [
            ReloadIntegrationButton(hass, client, entry, gateway_id),
            QueryStatusButton(hass, client, gateway_id),
            ClearCacheButton(hass, client, gateway_id),
        ],
    )




class ReloadIntegrationButton(ButtonEntity):

    def __init__(self, hass, client, entry, gateway_id) -> None:
        self._hass = hass
        self._gateway_id = gateway_id
        name = get_translation(hass,
                                          "reload_integration",
                                          "Reload Cleveroom Integration")
        self._attr_name = f"{name}({gateway_id})"
        self._attr_unique_id = f"cleveroom_rediscover.{gateway_id}"
        self.entity_id = f"button.cleveroom_rediscover.{gateway_id}"
        self._client = cast(KLWIOTClient, client)
        self._entry = entry

    async def async_press(self) -> None:
        _LOGGER.info("Reload Cleveroom Integration...")
        try:
            await self._hass.config_entries.async_reload(self._entry.entry_id)
            _LOGGER.info("Restart Load The Cleveroom Integration...")
        except Exception as e:
            _LOGGER.error(f"Failed to call Reload Cleveroom Integration service: {e}")


class QueryStatusButton(ButtonEntity):
    def __init__(self, hass, client, gateway_id) -> None:
        self._hass = hass

        name = get_translation(hass,
                                          "search_devices",
                                          "Search Cleveroom Gateway Devices")
        self._attr_name = f"{name}({gateway_id})"
        self._attr_unique_id = f"cleveroom_query.{gateway_id}"
        self.entity_id = f"button.cleveroom_query.{gateway_id}"
        self._client = cast(KLWIOTClient, client)

    async def async_press(self) -> None:
        _LOGGER.info("Clear all the buffers then query rediscover devices...")
        try:
            self._client.clear_all_buffers()
            self._client.query_all_devices()
        except Exception as e:
            _LOGGER.error(f"Failed to call Query Cleveroom Gateway Devices service: {e}")


class ClearCacheButton(ButtonEntity):
    def __init__(self, hass, client, gateway_id) -> None:
        self._hass = hass
        name = get_translation(hass,
                        "clear_cache",
                        "Clear Cleveroom Gateway Cache")
        self._attr_name = f"{name}({gateway_id})"
        self._attr_unique_id = f"cleveroom_cleancache.{gateway_id}"  # 按钮唯一ID
        self.entity_id = f"button.cleveroom_cleancache.{gateway_id}"
        self._client = cast(KLWIOTClient, client)

    async def async_press(self) -> None:
        try:
            self._client.devicebucket.clear_bucket()
            _LOGGER.info("Clear Cleveroom Gateway Cache service called successfully.")
        except Exception as e:
            _LOGGER.error(f"Failed to call Clear Cleveroom Gateway Cache service: {e}")
