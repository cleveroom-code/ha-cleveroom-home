"""
Cleveroom Media Player Platform.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerDeviceClass,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    MediaPlayerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr

from .base import KLWEntity
from . import ( ENTITY_REGISTRY, KLWIOTClient, DeviceType,
               device_registry_area_update, is_media_player,
    generate_object_id)
from .const import DOMAIN
_LOGGER = logging.getLogger(__name__)

SUPPORTED_SOURCES = ["AU1", "TF", "AU2", "FM"]
SOURCE_MAP = {1: "AU1", 2: "TF", 3: "AU2", 4: "FM"}

SUPPORTED_TF_FOLDERS = ["Root", "1#Folder", "2#Folder", "3#Folder",
                        "4#Folder", "5#Folder", "6#Folder"]


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

    media_players = []
    for device in devices:
        try:
            if is_media_player(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                player = CleveroomMediaPlayer(hass, device, client, gateway_id,auto_area,predictive_feedback)
                media_players.append(player)

                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][player.unique_id] = player
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(media_players)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_media_player(device):
                    _LOGGER.info(f"add music player new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    player = CleveroomMediaPlayer(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [player], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][player.unique_id] = player
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')},"
                                f" error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomMediaPlayer(KLWEntity,MediaPlayerEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self.entity_id = f"media_player.{self._object_id}"

        self._state = MediaPlayerState.OFF  #
        self._volume = 0.5  # default volume (0.0 - 1.0)
        self._muted = False
        self._source = None
        self._sound_mode = None
        self._tf_folder = None
        self._attr_current_sound_mode = None

        self.init_or_update_entity_state(device)

        # 支持的功能
        self._attr_supported_features = (
                MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER  # 设备类型为扬声器

    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]

        self._state = MediaPlayerState.PLAYING if detail.get("on", False) else MediaPlayerState.OFF

        # cleveroom support gears：0~18 => 0.0~1.0
        self._volume = detail.get("vol", 0) / 18.0

        # channel source
        chl = detail.get("chl")
        self._source = SOURCE_MAP.get(chl, None)

        self._muted = False
        self._tf_folder = None

    @property
    def state(self) -> MediaPlayerState | None:
        return self._state

    @property
    def volume_level(self) -> float | None:
        return self._volume

    @property
    def is_volume_muted(self) -> bool | None:
        return self._muted

    @property
    def source(self) -> str | None:
        return self._source

    @property
    def source_list(self) -> list[str] | None:
        return SUPPORTED_SOURCES

    @property
    def sound_mode_list(self) -> list[str] | None:
        return SUPPORTED_TF_FOLDERS

    @property
    def media_content_type(self):
        return MediaType.MUSIC

    async def async_set_volume_level(self, volume: float) -> None:
        """set volume level."""
        vol = int(volume * 100)
        try:
            self._client.controller.control(
                "SetVolume", [{"oid": self._oid, "value": vol}])
            self._volume = volume
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"set volume failure: {e}")

    async def async_mute_volume(self, mute: bool) -> None:
        # cleveroom system not support music player mute,so just turn off the player
        await self.async_turn_off()
        self._muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        if source in SUPPORTED_SOURCES:
            chl = list(SOURCE_MAP.keys())[list(SOURCE_MAP.values()).index(source)]
            try:
                self._client.controller.control(
                    "SetSource", [{"oid": self._oid, "value": chl}])
                self._source = source
                self.async_write_ha_state()
            except Exception as e:
                _LOGGER.error(f"select source error: {e}")
        else:
            _LOGGER.warning(f"unsupported source: {source}")

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """ It is used to select the sound mode of the media player.just for TF source"""
        if self._source == "TF" and sound_mode in SUPPORTED_TF_FOLDERS:
            try:
                idx = SUPPORTED_TF_FOLDERS.index(sound_mode)
                self._client.controller.control(
                    "SetSongFolder", [{"oid": self._oid, "value": idx}])
                self._attr_current_sound_mode = sound_mode
                self.async_write_ha_state()
            except Exception as e:
                _LOGGER.error(f"Failed to select the music folder: {e}")
        else:
            _LOGGER.warning(f"Unsupported sound mode: {sound_mode}")

    async def async_media_play(self) -> None:
        try:
            await self.async_turn_on()
        except Exception as e:
            _LOGGER.error(f"play media failure: {e}")

    async def async_media_stop(self) -> None:
        try:
            await self.async_turn_off()
        except Exception as e:
            _LOGGER.error(f"stop media failure: {e}")

    async def async_media_next_track(self) -> None:
        try:
            self._client.controller.control("SetNextSong", [{"oid": self._oid}])
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"next track failure: {e}")

    async def async_media_previous_track(self) -> None:
        try:
            self._client.controller.control("SetPrevSong", [{"oid": self._oid}])
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"previous track failure: {e}")

    async def async_turn_on(self) -> None:
        try:
            self._client.controller.control("DeviceOn", [{"oid": self._oid}])
            self._state = MediaPlayerState.PLAYING
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to open the media player: {e}")

    async def async_turn_off(self) -> None:
        try:
            self._client.controller.control("DeviceOff", [{"oid": self._oid}])
            self._state = MediaPlayerState.OFF
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to close the media player. Procedure: {e}")

    @property
    def supported_features(self) -> int:
        return self._attr_supported_features

