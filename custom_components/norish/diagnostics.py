"""Diagnostics download for the Norish integration (secrets redacted)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_NORISH_EMAIL, CONF_NORISH_PASSWORD, DOMAIN

TO_REDACT = {CONF_API_KEY, CONF_NORISH_EMAIL, CONF_NORISH_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return what helps troubleshooting, without credentials or recipes."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = (coordinator.data or {}) if coordinator else {}

    def _iso(value: Any) -> str | None:
        return value.isoformat() if value else None

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": None if coordinator is None else {
            "last_update_success": coordinator.last_update_success,
            "last_success": _iso(getattr(coordinator, "last_success", None)),
            "stale": getattr(coordinator, "stale", None),
            "update_interval_s": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval else None
            ),
            "rate_limited_until": _iso(getattr(coordinator, "_rate_limited_until", None)),
            "realtime_connected": getattr(coordinator, "realtime_connected", None),
            "consecutive_failures": getattr(coordinator, "_consecutive_failures", None),
            "consecutive_auth_failures": getattr(coordinator, "_consecutive_auth_failures", None),
        },
        "counts": {
            "calendar_items": len(data.get("calendar", [])),
            "groceries": len(data.get("groceries", [])),
            "stores": len(data.get("stores", {})),
            "units": len(data.get("units", {})),
            "cached_recipes": len(getattr(coordinator, "_cached_recipes", {}) or {}),
        },
    }
