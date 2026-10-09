"""Shared entity helpers for the Norish integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def norish_device_info(entry: ConfigEntry, base_url: str) -> DeviceInfo:
    """Return the device all Norish entities belong to.

    Without this every entity is a loose item in the registry.  Grouping them
    under one service device keeps the integration page readable and gives the
    entities a single place to be renamed or assigned to an area.

    The identifier is the config entry id, so a second Norish instance gets its
    own device instead of merging into this one.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        name="Norish",
        manufacturer="Norish",
        model="Recipes & Meal Planning",
        configuration_url=base_url,
    )
