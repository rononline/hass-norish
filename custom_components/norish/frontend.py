"""Serve and auto-register the bundled Norish Lovelace card."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/norish_static"
CARD_FILE = "norish-card.js"
_DATA_REGISTERED = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Make custom:norish-card available in every dashboard (once per HA run)."""
    if hass.data.get(_DATA_REGISTERED) or hass.http is None:
        return
    hass.data[_DATA_REGISTERED] = True

    www = Path(__file__).parent / "www"

    def _file_hash() -> str:
        return hashlib.sha256((www / CARD_FILE).read_bytes()).hexdigest()[:8]

    # Version query so browsers pick up a new card after a HACS update
    version = await hass.async_add_executor_job(_file_hash)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(www), False)]
    )
    add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILE}?v={version}")
    _LOGGER.debug("Norish: registered card %s/%s?v=%s", URL_BASE, CARD_FILE, version)
