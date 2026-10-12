"""Tests: realtime/last-update status entities and diagnostics."""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.util import dt as dt_util

from custom_components.norish.binary_sensor import NorishRealtimeSensor
from custom_components.norish.coordinator import NorishCoordinator
from custom_components.norish.diagnostics import async_get_config_entry_diagnostics
from custom_components.norish.sensor import NorishLastUpdateSensor

ENTRY = SimpleNamespace(entry_id="e1", title="Norish",
                        data={"url": "https://n", "api_key": "SECRET", "norish_email": "a@b.nl", "norish_password": "pw"},
                        options={"poll_interval": 900})


def coord():
    c = object.__new__(NorishCoordinator)
    c.data = {"calendar": [1, 2], "groceries": [1], "stores": {"s": "AH"}, "units": {}}
    c.base_url = "https://n"; c.config_entry = None
    c.last_success = datetime(2026, 10, 12, 8, 0, tzinfo=dt_util.UTC); c.stale = False
    c.realtime_connected = True; c._rate_limited_until = None
    c._consecutive_failures = 0; c._consecutive_auth_failures = 0; c._cached_recipes = {"r": {}}
    c.last_update_success = True; c.update_interval = timedelta(minutes=30)
    c.async_add_listener = lambda *a: None
    return c


def test_realtime_and_last_update_entities():
    c = coord()
    rt = NorishRealtimeSensor(c, ENTRY)
    assert rt.is_on is True and rt.available and rt.unique_id == "e1_realtime"
    c.realtime_connected = False
    assert rt.is_on is False
    lu = NorishLastUpdateSensor(c, ENTRY)
    assert lu.native_value == c.last_success and lu.entity_category == "diagnostic"


def test_set_realtime_notifies_listeners():
    c = coord(); c._configured_update_interval = timedelta(minutes=15)
    c._normal_update_interval = timedelta(minutes=15); c.async_update_listeners = MagicMock()
    c.set_realtime(False)
    assert c.realtime_connected is False and c.async_update_listeners.called


def test_diagnostics_redacts_secrets():
    hass = SimpleNamespace(data={"norish": {"e1": coord()}})
    diag = asyncio.run(async_get_config_entry_diagnostics(hass, ENTRY))
    flat = str(diag)
    assert "SECRET" not in flat and "pw" not in flat.replace("poll", "") and "a@b.nl" not in flat
    assert diag["entry"]["data"]["url"] == "https://n"
    assert diag["coordinator"]["realtime_connected"] is True
    assert diag["counts"] == {"calendar_items": 2, "groceries": 1, "stores": 1, "units": 0, "cached_recipes": 1}
