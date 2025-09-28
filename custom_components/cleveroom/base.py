from typing import cast

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import DeviceInfo
from . import KLWIOTClient, _LOGGER, generate_object_id
from .const import DOMAIN

class KLWEntity(Entity):
    """Base class for KLW entities."""

    def __init__(self, hass, device, client, gateway_id,auto_area,predictive_feedback):
        """Initialize the KLW entity."""
        self.hass = hass
        self._client = cast(KLWIOTClient, client)
        self._device = device
        self._oid = device["oid"]
        detail = device["detail"]
        self._full_name = f"{detail.get("fName", "")} {detail.get("rName", "")} {detail.get("dName", "")}".strip()
        self._object_id = generate_object_id( self._oid)
        self._name = self._full_name
        self.predictive_feedback = predictive_feedback

        if auto_area == 1:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._oid)},
                name=self._full_name,
                manufacturer="Cleveroom",
                model="Generic"
            )
        else:
            self._attr_device_info = None

    def init_or_update_entity_state(self, device):
        """Initialize or update the entity state."""
        _LOGGER.debug(f"Initializing entity {self._oid} {self.name},please override this method")
        pass
    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._oid
    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # 检查设备是否在线或可用
        device = self._client.devicebucket.get_device_from_database(self._oid)
        return device is not None

    def set_device_detail_field(self, field: str, value):
        """
        Dynamically set a field in the device's detail dictionary.
        Args:
            field (str): The field name to set, e.g. 'on', 'gear', etc.
            value: The value to set.
        """

        if self.predictive_feedback == 1:
            #support predictive feedback
            device = self._client.devicebucket.get_device_from_database(self._oid)
            if device is None:
                _LOGGER.error(f"Device not found: {self._oid}")
                return False

            detail = device.get("detail")
            if detail is None or not isinstance(detail, dict):
                _LOGGER.error(f"Device {self._oid} has no detail map")
                return False

            old_value = detail.get(field)
            detail[field] = value
            _LOGGER.info(f"Set device {self._oid} detail field '{field}' from {old_value} to {value}")

        return True

    async def async_update(self):
        """
        Update the entity state.
        """
        try:
            device = self._client.devicebucket.get_device_from_database(self._oid)
            if device is None:
                _LOGGER.error(f"Device not found: {self._oid}")
                return
            self.init_or_update_entity_state(device)
            if self.entity_id:
                self.async_write_ha_state()
            else:
                _LOGGER.warning(f"Entity {self._oid}{self.name} not yet registered, skipping async_write_ha_state")
        except Exception as e:
            _LOGGER.error(f"Failed to update entity {self._oid}  {self.name}  [{self.entity_id}] : {e}")

