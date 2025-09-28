"""
Support for Cleveroom climate devices.
For more detailed information, please refer to: https://www.cleveroom.com
"""
import asyncio
import logging
from typing import cast

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    SWING_ON,
    SWING_OFF,
    ATTR_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_SWING_MODE,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.const import (
    UnitOfTemperature,  # Import UnitOfTemperature
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry  # Import ConfigEntry
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from . import  ENTITY_REGISTRY, KLWIOTClient, DeviceType, device_registry_area_update, is_climate, is_heater, \
    generate_object_id
from .base import KLWEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map Cleveroom modes to HA HVAC modes
CLEVEROOM_TO_HA_HVAC_MODE = {
    0: HVACMode.HEAT,
    1: HVACMode.COOL,
    2: HVACMode.DRY,
    3: HVACMode.FAN_ONLY,
    4: HVACMode.OFF,
    5: HVACMode.AUTO,
}

HA_TO_CLEVEROOM_HVAC_MODE = {
    HVACMode.HEAT: 0,
    HVACMode.COOL: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.OFF: 4,
    HVACMode.AUTO: 5,
}

# Map Cleveroom fan speeds to HA fan speeds
CLEVEROOM_TO_HA_FAN_SPEED = {
    0: FAN_LOW,
    1: FAN_MEDIUM,
    2: FAN_HIGH,
}

# Map HA fan speeds to Cleveroom fan speeds
HA_TO_CLEVEROOM_FAN_SPEED = {
    FAN_LOW: 0,
    FAN_MEDIUM: 1,
    FAN_HIGH: 2,
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

    climates = []
    for device in devices:
        try:
            if is_climate(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                climate = CleveroomClimate(hass, device, client, gateway_id,auto_area,predictive_feedback)
                climates.append(climate)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][climate.unique_id] = climate
            elif is_heater(device):
                if auto_area == 1:
                    await device_registry_area_update(
                        floor_registry, area_registry, device_registry, entry, device)
                climate = CleveroomFloorHeating(hass, device, client, gateway_id,auto_area,predictive_feedback)
                climates.append(climate)
                ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                ENTITY_REGISTRY[entry.entry_id][climate.unique_id] = climate
        except Exception as e:
            _LOGGER.warning(
                f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, error message: {e}")

    async_add_entities(climates)

    def async_device_discovered(device, is_new):
        if is_new:
            try:
                if is_climate(device):
                    _LOGGER.info(f"add light new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    climate = CleveroomClimate(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [climate], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][climate.unique_id] = climate
                elif is_heater(device):
                    _LOGGER.info(f"add light new devices: {device['oid']}")
                    if auto_area == 1:
                        asyncio.run_coroutine_threadsafe(
                            device_registry_area_update(
                                floor_registry, area_registry, device_registry, entry, device),
                            hass.loop)
                    climate = CleveroomFloorHeating(hass, device, client, gateway_id,auto_area,predictive_feedback)
                    asyncio.run_coroutine_threadsafe(
                        async_add_entities_wrapper(hass, async_add_entities, [climate], False), hass.loop)
                    ENTITY_REGISTRY.setdefault(entry.entry_id, {})
                    ENTITY_REGISTRY[entry.entry_id][climate.unique_id] = climate
            except KeyError as e:
                _LOGGER.warning(f"Device data is incomplete, skip: {device.get('oid', 'unknow')}, "
                                f"error message: {e}")

    async def async_add_entities_wrapper(hass: HomeAssistant,
                                         async_add_entities: AddEntitiesCallback,
                                         entities: list,
                                         update_before_add: bool = False):
        async_add_entities(entities, update_before_add)

    client.on("on_device_change", async_device_discovered)


class CleveroomClimate(KLWEntity,ClimateEntity):
    """Representation of a Cleveroom climate device."""

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):
        """Initialize the climate device."""
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)
        self.entity_id = f"climate.{self._object_id}"

        # self._temperature = 0
        self._hvac_mode = HVACMode.OFF
        self._fan_mode = FAN_LOW
        self._swing_mode = SWING_OFF
        self._target_temperature = 20
        self._current_temperature = 0
        self._current_humidity = 0
        self._min_temp = 15
        self._max_temp = 30

        self._attr_min_temp = self._min_temp
        self._attr_max_temp = self._max_temp

        self.init_or_update_entity_state(device)

        # Define supported features
        self._supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE |
                ClimateEntityFeature.FAN_MODE |
                ClimateEntityFeature.SWING_MODE |
                ClimateEntityFeature.TURN_ON |
                ClimateEntityFeature.TURN_OFF
        )

        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT,
                                 HVACMode.DRY, HVACMode.FAN_ONLY,
                                 HVACMode.AUTO]
        self._attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_swing_modes = [SWING_ON, SWING_OFF]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_high = 30
        self._attr_target_temperature_low = 15

    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]
        mode = detail.get("model", 4)
        if mode == 4:
            self._hvac_mode = HVACMode.OFF
        else:
            self._hvac_mode = CLEVEROOM_TO_HA_HVAC_MODE.get(mode, HVACMode.OFF)

        if not detail.get("on"):
            self._hvac_mode = HVACMode.OFF

        self._fan_mode = CLEVEROOM_TO_HA_FAN_SPEED.get(detail.get("speed", 0), FAN_LOW)

        self._swing_mode = SWING_ON if detail.get("model", 3) == 3 else SWING_OFF

        self._target_temperature = detail.get("temp")

        if detail.get("ambient_temp") is not None:
            self._current_temperature = detail.get("ambient_temp")
        else:
            self._current_temperature = self._target_temperature
        if detail.get("ambient_hum") is not None:
            self._current_humidity = detail.get("ambient_hum", 0)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._attr_temperature_unit == UnitOfTemperature.CELSIUS:
            return "°C"
        return "°C"  # Default to Celsius

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_humidity(self) -> float | None:
        return self._current_humidity

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction | None:
        if self._hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        elif self._hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        elif self._hvac_mode == HVACMode.DRY:
            return HVACAction.DRYING
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self._swing_mode

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return self._attr_hvac_modes

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._attr_fan_modes

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return self._attr_swing_modes

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    @property
    def device_info(self) -> DeviceInfo:
        """返回设备信息."""
        return self._attr_device_info

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_turn_on(self):
        """Turn the entity on."""
        _LOGGER.debug(f"Turning on {self._oid}")
        pass

    async def async_turn_off(self):
        """Turn the entity off."""
        _LOGGER.debug(f"Turning off {self._oid}")
        pass

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            # self._target_temperature = kwargs[ATTR_TEMPERATURE]

            value = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug(f"Setting target temperature to {value} for {self._oid}")
            self._client.controller.control("SetTemperature", [{"oid": self._oid, "value": int(value)}])
            # self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set new HVAC Mode."""
        self._hvac_mode = hvac_mode
        _LOGGER.debug(f"Setting HVAC mode to {self._hvac_mode} for {self._oid}")
        mode = HA_TO_CLEVEROOM_HVAC_MODE[hvac_mode]
        if mode == 4:
            self._client.controller.control("DeviceOff", [{"oid": self._oid}])
            self.set_device_detail_field("on", False)
        else:
            if not self._device["detail"]["on"]:
                self._client.controller.control("DeviceOn", [{"oid": self._oid}])
                self.set_device_detail_field("on", True)
            if mode == 5:
                self._client.controller.control("SetAuto", [{"oid": self._oid, "value": 1}])
            else:
                self._client.controller.control("SetMode", [{"oid": self._oid, "value": mode}])
                # 等待230ms再设置手动模式
                await asyncio.sleep(0.3)
                self._client.controller.control("SetAuto", [{"oid": self._oid, "value": 0}])

        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str):
        """Set new fan mode."""
        self._fan_mode = fan_mode
        _LOGGER.debug(f"Setting fan mode to {self._fan_mode} for {self._oid}")
        speed = HA_TO_CLEVEROOM_FAN_SPEED[fan_mode]
        self._client.controller.control("SetSpeed", [{"oid": self._oid, "value": speed}])
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str):
        """Set new swing mode."""
        self._swing_mode = swing_mode
        _LOGGER.debug(f"Setting swing mode to {self._swing_mode} for {self._oid}")
        mode = 3 if swing_mode == SWING_ON else 0
        self._client.controller.control("SetMode", [{"oid": self._oid, "value": mode}])
        self.async_write_ha_state()



class CleveroomFloorHeating(KLWEntity,ClimateEntity):
    """Representation of a Cleveroom floor heating device."""

    def __init__(self, hass, device, client, gateway_id, auto_area,predictive_feedback):
        """Initialize the floor heating device."""
        super().__init__(hass, device, client, gateway_id, auto_area,predictive_feedback)

        self._current_humidity = None

        self.entity_id = f"climate.{self._object_id}"

        self._hvac_mode = HVACMode.OFF
        self._target_temperature = 20
        self._current_temperature = 0
        self._auto_mode = 0
        self._min_temp = 15
        self._max_temp = 30
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

        self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
        )
        self._attr_min_temp = self._min_temp
        self._attr_max_temp = self._max_temp
        self.init_or_update_entity_state(device)

    def init_or_update_entity_state(self, device):
        self._device = device
        detail = device["detail"]
        # 读取设备状态
        self._target_temperature = detail.get("temp") or self._target_temperature
        if detail.get("ambient_temp") is not None:
            self._current_temperature = detail.get("ambient_temp")
        else:
            self._current_temperature = self._target_temperature
        if detail.get("ambient_hum") is not None:
            self._current_humidity = detail.get("ambient_hum", 0)
        self._auto_mode = detail.get("auto", 0)
        # 根据状态设置 HVAC 模式
        if detail.get("on"):
            if self._auto_mode == 1:
                self._hvac_mode = HVACMode.AUTO
            else:
                self._hvac_mode = HVACMode.HEAT
        else:
            self._hvac_mode = HVACMode.OFF

    @property
    def temperature_unit(self) -> str:
        return str(UnitOfTemperature.CELSIUS)

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def current_humidity(self) -> float | None:
        return self._current_humidity

    @property
    def target_temperature(self) -> float:
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @property
    def hvac_modes(self):
        return self._attr_hvac_modes

    @property
    def supported_features(self) -> int:
        return self._attr_supported_features

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    @property
    def min_temp(self) -> float:
        return self._min_temp

    @property
    def max_temp(self) -> float:
        return self._max_temp

    @property
    def target_temperature_step(self):
        return 1

    async def async_turn_on(self):
        """Turn the entity on."""
        _LOGGER.debug(f"Turning on floor heating {self._oid}")
        try:
            self._client.controller.control("DeviceOn", [{"oid": self._oid}])
            self._hvac_mode = HVACMode.HEAT  #
            self.set_device_detail_field("on", True)
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn on floor heating {self._oid}: {e}")

    async def async_turn_off(self):
        """Turn the entity off."""
        _LOGGER.debug(f"Turning off floor heating {self._oid}")
        try:
            self._client.controller.control("DeviceOff", [{"oid": self._oid}])
            self._hvac_mode = HVACMode.OFF
            self.set_device_detail_field("on", False)
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off floor heating {self._oid}: {e}")

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temperature = kwargs[ATTR_TEMPERATURE]
            self._client.controller.control(
                "SetTemperature", [{"oid": self._oid, "value": int(temperature)}]
            )
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set new HVAC Mode."""
        _LOGGER.debug(f"Setting HVAC mode to {hvac_mode} for {self._oid}")
        try:
            if hvac_mode == HVACMode.OFF:
                await self.async_turn_off()
            elif hvac_mode == HVACMode.HEAT:
                await self.async_turn_on()
                await asyncio.sleep(0.3)
                self._client.controller.control("SetAuto", [{"oid": self._oid, "value": 0}])
                self._auto_mode = 0
            elif hvac_mode == HVACMode.AUTO:
                await self.async_turn_on()
                # 等待300ms
                await asyncio.sleep(0.3)
                self._client.controller.control("SetAuto", [{"oid": self._oid, "value": 1}])
                self._auto_mode = 1
            self._hvac_mode = hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to set HVAC mode for {self._oid}: {e}")

