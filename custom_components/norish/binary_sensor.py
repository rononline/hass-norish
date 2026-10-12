"""Binary sensor platform for Norish: realtime connection status."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorishCoordinator
from .entity import norish_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Norish realtime status sensor."""
    coordinator: NorishCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NorishRealtimeSensor(coordinator, entry)])


class NorishRealtimeSensor(CoordinatorEntity, BinarySensorEntity):
    """On while Norish pushes changes over the WebSocket (diagnostic)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NorishCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_name = "Norish Realtime"
        self._attr_unique_id = f"{entry.entry_id}_realtime"
        self._attr_device_info = norish_device_info(entry, coordinator.base_url)

    @property
    def available(self) -> bool:
        # The connection status is meaningful even while polling fails
        return True

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.coordinator, "realtime_connected", False))
