"""
Support for Cleveroom lights.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import colorsys
import logging
from typing import cast

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    LightEntity,
    ColorMode,
    ATTR_HS_COLOR,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import device_registry as dr
from . import ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, is_light, \
    generate_object_id
from .const import DOMAIN
from .base import KLWEntity

_LOGGER = logging.getLogger(__name__)
# Cleveroom system support min and max color temperature
MIN_COLOR_TEMP_K = 2732
MAX_COLOR_TEMP_K = 6024
# Cleveroom system support color temperature list, 0-100 value means 2732-6024K color temperature
COLOR_TEMP_LIST = [2732, 2747, 2762, 2778, 2793, 2809, 2825, 2841, 2857,
                   2874, 2890, 2907, 2924, 2941, 2959, 2976, 2994,
                   3012, 3030, 3049, 3067, 3086, 3106, 3125, 3145, 3165,
                   3185, 3205, 3226, 3247, 3268, 3289, 3311, 3333,
                   3356, 3378, 3401, 3425, 3448, 3472, 3497, 3521, 3546,
                   3571, 3597, 3623, 3650, 3676, 3704, 3731, 3759,
                   3788, 3817, 3846, 3876, 3906, 3937, 3968, 4000, 4032,
                   4065, 4098, 4132, 4167, 4202, 4237, 4274, 4310,
                   4348, 4386, 4425, 4464, 4505, 4545, 4587, 4630, 4673,
                   4717, 4762, 4808, 4854, 4902, 4950, 5000, 5051,
                   5102, 5155, 5208, 5263, 5319, 5376, 5435, 5495, 5556,
                   5618, 5682, 5747, 5814, 5882, 5952, 6024]


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    gateway_data = hass.data[DOMAIN][entry.entry_id]
    devices = gateway_data["devices"]
    client = gateway_data["client"]
    gateway_id = gateway_data["gateway_id"]
    auto_area = gateway_data["auto_area"]
    predictive_feedback = gateway_data["predictive_feedback"]
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    lights = []
    for device in devices:
        try:
            if is_light(device):

                if auto_area == 1:
                    await device_registry_area_update(floor_registry, area_registry, device_registry, entry, device)
                light = CleveroomLight(hass, device, client, gateway_id,auto_area,predictive_feedback)
                lights.append(light)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][light.unique_id] = light
                _LOGGER.info(f"restore light: {device['oid']}  unique_id:{light.unique_id} ")
        except KeyError as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}"
            )
    async_add_entities(lights)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_light(device):
                    _LOGGER.info(f"add light new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    light = CleveroomLight(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [light], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][light.unique_id] = light
                    _LOGGER.info(f"new light: {device['oid']}  unique_id:{light.unique_id} ")
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')},"
                                f" error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomLight(KLWEntity,LightEntity):

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self.entity_id = f"light.{self._object_id}"

        self._is_on = False
        self._brightness = 0
        self._color_temp = None
        self._rgb_color = None
        self._hs_color = None
        self._category = device["detail"].get("category")

        self.init_or_update_entity_state(device)

        if self._category == DeviceType.ADJUST_LIGHT:  # just support light brightness
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

        elif self._category == DeviceType.WARM_LIGHT:  # support light brightness and color temperature
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_min_color_temp_kelvin = MIN_COLOR_TEMP_K
            self._attr_max_color_temp_kelvin = MAX_COLOR_TEMP_K

        elif self._category == DeviceType.RGB_LIGHT:  # support light brightness and color temperature
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS

        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    def init_or_update_entity_state(self, device):

        self._device = device
        detail = device["detail"]

        self._is_on = detail.get("on", self._is_on)

        if detail['category'] == DeviceType.RGB_LIGHT:
            if "rgb" in detail:
                self._rgb_color = (
                    self._hex_to_rgb(detail.get("rgb", "#FFFFFF"))
                    if detail.get("rgb")
                    else self._rgb_color
                )
                # 将rgb转换成 hsb 得到亮度
                hsb = self.color_rgb_to_hsb(self._rgb_color)
                self._brightness = hsb[2] / 255 * 100
                self._hs_color = (hsb[0], hsb[1])
        else:
            if "gear" in detail:
                # print(f'{self._full_name} 亮度 from {self._brightness} => {detail.get("gear")}')
                self._brightness = detail.get("gear")
            if "warm" in detail:
                # print(f'{self._full_name} 色温 from {self._color_temp} ==> {detail.get("warm")}')
                self._color_temp = 100 - detail.get("warm")


    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def min_color_temp_kelvin(self):
        return MIN_COLOR_TEMP_K

    @property
    def max_color_temp_kelvin(self):
        return MAX_COLOR_TEMP_K

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self._hs_color

    @property
    def brightness(self) -> int:
        return int(self._brightness / 100 * 255) if self._brightness is not None else None

    @property
    def color_temp_kelvin(self) -> int:
        if self._color_temp is None:
            return None
        kelvin = COLOR_TEMP_LIST[self._color_temp]
        return kelvin

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._rgb_color

    @property
    def supported_color_modes(self):
        """Return the supported color modes."""
        return self._attr_supported_color_modes

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return self._attr_color_mode

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug(f"Turn on: {self._oid}, params: {kwargs}")
        # if not self._is_on:



        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            if self._category == DeviceType.RGB_LIGHT and self._rgb_color:
                hsb = self._hs_color
                brightness_hsb = brightness * 255 / 100
                new_rgb_color = self.color_hsb_to_RGB(hsb[0], hsb[1], brightness_hsb)
                rgb = {"r": new_rgb_color[0], "g": new_rgb_color[1], "b": new_rgb_color[2]}
                _LOGGER.debug(f"hsb=>rgb: {self.rgb_to_hex(new_rgb_color)}")
                self._client.controller.control("SetColor", [{"oid": self._oid, "value": rgb}])
            else:
                self._brightness = brightness
                self._client.controller.control(
                    "SetBrightness", [{"oid": self._oid, "value": brightness}]
                )

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            min_kelvin = MIN_COLOR_TEMP_K
            max_kelvin = MAX_COLOR_TEMP_K
            step = (max_kelvin - min_kelvin) / 100
            warm = int((kelvin - min_kelvin) / step)
            self._client.controller.control(
                "SetColorTemperature", [{"oid": self._oid, "value": warm}]
            )

        if ATTR_RGB_COLOR in kwargs:
            new_rgb_color = kwargs[ATTR_RGB_COLOR]
            rgb = {"r": new_rgb_color[0], "g": new_rgb_color[1], "b": new_rgb_color[2]}
            self._client.controller.control(
                "SetColor", [{"oid": self._oid, "value": rgb}]
            )

        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            brightness_hsb = self._brightness * 255 / 100
            new_rgb_color = self.color_hsb_to_RGB(hs_color[0], hs_color[1], brightness_hsb)
            rgb = {"r": new_rgb_color[0], "g": new_rgb_color[1], "b": new_rgb_color[2]}
            _LOGGER.debug(f"hsb=>rgb: {self.rgb_to_hex(new_rgb_color)}")
            self._client.controller.control(
                "SetColor", [{"oid": self._oid, "value": rgb}]
            )

        if not self._is_on:
            self._client.controller.control("DeviceOn", [{"oid": self._oid}])
        self._is_on = True
        self.set_device_detail_field("on", True)
        self.async_write_ha_state()
        self._client.controller.control("DeviceOn", [{"oid": self._oid}])


    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"Turn off: {self._oid}")
        self._is_on = False
        self.set_device_detail_field("on", False)
        self.async_write_ha_state()
        self._client.controller.control("DeviceOff", [{"oid": self._oid}])


    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i: i + 2], 16) for i in (0, 2, 4))

    def rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % rgb

    def color_hs_to_RGB(self, hue: float, saturation: float) -> tuple[int, int, int]:
        """Converts hue saturation to rgb."""
        r, g, b = colorsys.hsv_to_rgb(hue / 360, saturation / 100, 1)
        return (int(r * 255), int(g * 255), int(b * 255))

    def color_hsb_to_RGB(self, hue: float, saturation: float, brightness: float) -> tuple[int, int, int]:
        h = hue / 360.0
        s = saturation / 100.0
        b = brightness / 255.0

        # Use colorsys.hsv_to_rgb to convert HSB to RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, b)

        # Scale the RGB values to the range 0-255 and convert to integers
        return (int(r * 255), int(g * 255), int(b * 255))

    def color_rgb_to_hsb(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        """Converts rgb to hue saturation brightness."""
        r, g, b = rgb
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        return (h * 360, s * 100, v * 255)
