"""Tests for the fork bugfixes (not committed)."""
import asyncio, os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import UpdateFailed
from custom_components.norish.coordinator import NorishCoordinator
from custom_components.norish.calendar import NorishCalendar
from custom_components.norish.camera import NorishRecipeCamera
from custom_components.norish.media_player import NorishVideoPlayer

TZ = "Europe/Amsterdam"
dt_util.set_default_time_zone(dt_util.get_time_zone(TZ))

def fake_coord(calendar):
    return SimpleNamespace(data={"calendar": calendar}, base_url="http://n",
                           _get_headers=lambda: {}, async_add_listener=lambda *a: None)

def entry():
    return SimpleNamespace(entry_id="e1")

def bare_coordinator():
    c = object.__new__(NorishCoordinator)
    return c

# 1. failed calendar fetch must raise UpdateFailed (keep last data)
def test_calendar_fetch_failure_raises():
    c = bare_coordinator()
    c._fetch_trpc = AsyncMock(return_value=None)
    with pytest.raises(UpdateFailed):
        asyncio.run(c._fetch_calendar({"calendar": []}))

def test_groceries_fetch_failure_raises():
    c = bare_coordinator()
    c._fetch_trpc = AsyncMock(return_value=None)
    with pytest.raises(UpdateFailed):
        asyncio.run(c._fetch_groceries({"groceries": []}))

def test_calendar_fetch_empty_ok():
    c = bare_coordinator()
    c._fetch_trpc = AsyncMock(return_value=[{"result": {"data": {"json": []}}}])
    d = {"calendar": ["old"]}
    asyncio.run(c._fetch_calendar(d))
    assert d["calendar"] == []

# 1b. calendar range uses HA timezone date
def test_calendar_fetch_uses_ha_date():
    c = bare_coordinator()
    c._fetch_trpc = AsyncMock(return_value=[{"result": {"data": {"json": []}}}])
    fixed = datetime(2026, 10, 7, 0, 30, tzinfo=dt_util.get_time_zone(TZ))  # 22:30 UTC on 6th
    with patch("custom_components.norish.coordinator.dt_util.now", return_value=fixed):
        asyncio.run(c._fetch_calendar({}))
    payload = c._fetch_trpc.call_args.args[1]
    assert payload["startISO"] == "2026-10-06"

# 2. camera falls back to remote when local cache file is missing
def test_camera_remote_fallback():
    today = dt_util.now().strftime("%Y-%m-%d")
    ev = {"date": today, "slot": "Dinner", "recipeId": "r1",
          "_local_image": "/local/norish_images/missing.jpg",
          "_recipe": {"image": "/img/r1.jpg"}}
    cam = NorishRecipeCamera(fake_coord([ev]), entry(), "dinner", "Dinner")
    cam.hass = MagicMock()
    cam.hass.config.path = lambda *p: "/nonexistent/" + "/".join(p)
    async def run_exec(f, *a): return f(*a)
    cam.hass.async_add_executor_job = run_exec
    resp = MagicMock(status=200); resp.read = AsyncMock(return_value=b"IMG")
    ctx = MagicMock(); ctx.__aenter__ = AsyncMock(return_value=resp); ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock(); session.get = MagicMock(return_value=ctx)
    with patch("homeassistant.helpers.aiohttp_client.async_get_clientsession", return_value=session):
        data = asyncio.run(cam.async_camera_image())
    assert data == b"IMG"
    assert session.get.call_args.args[0] == "http://n/img/r1.jpg"

# 3. upper-case slots map to the right calendar times / camera / player
def make_cal(events):
    cal = NorishCalendar(fake_coord(events), entry())
    cal.hass = SimpleNamespace(config=SimpleNamespace(time_zone=TZ))
    return cal

def test_calendar_uppercase_slot_time():
    today = dt_util.now().date()
    cal = make_cal([{"date": today.isoformat(), "slot": "DINNER", "recipeName": "Pasta"}])
    s = dt_util.start_of_local_day()
    evs = cal._get_events_for_range(s, s + timedelta(days=1))
    assert len(evs) == 1 and evs[0].start.hour == 18
    assert evs[0].summary == "Dinner: Pasta"

def test_camera_and_player_type_field():
    today = dt_util.now().strftime("%Y-%m-%d")
    ev = {"date": today, "type": "LUNCH", "recipeId": "r1", "_recipe": {"video": "/v.mp4"}}
    cam = NorishRecipeCamera(fake_coord([ev]), entry(), "lunch", "Lunch")
    assert cam._get_current_image_url() is None  # no guessed URL → no wasted API request
    pl = NorishVideoPlayer(fake_coord([ev]), entry(), "lunch", "Lunch")
    assert pl._get_video_url() == "http://n/v.mp4"

# 4. calendar.event skips meals that already ended
def test_event_skips_past():
    today = dt_util.now().date().isoformat()
    tomorrow = (dt_util.now().date() + timedelta(days=1)).isoformat()
    cal = make_cal([{"date": today, "slot": "Breakfast", "recipeName": "Eggs"},
                    {"date": tomorrow, "slot": "Lunch", "recipeName": "Soup"}])
    late = dt_util.start_of_local_day() + timedelta(hours=21)
    with patch("custom_components.norish.calendar.dt_util.now", return_value=late):
        ev = cal.event
    assert ev is not None and ev.summary == "Lunch: Soup"

# 4b. async_get_events respects datetime bounds (no events past end)
def test_range_exclusive_end():
    tomorrow = (dt_util.now().date() + timedelta(days=1)).isoformat()
    cal = make_cal([{"date": tomorrow, "slot": "Dinner", "recipeName": "X"}])
    s = dt_util.start_of_local_day()
    evs = cal._get_events_for_range(s, s + timedelta(days=1))  # ends at tomorrow 00:00
    assert evs == []

# 5. images: gallery / recipeImage are used, non-image responses are not cached
def _resp(status, ctype, body=b"IMG"):
    r = MagicMock(status=status, content_type=ctype); r.read = AsyncMock(return_value=body)
    ctx = MagicMock(); ctx.__aenter__ = AsyncMock(return_value=r); ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx

def test_primary_image_path_variants():
    P = NorishCoordinator._primary_image_path
    assert P({"recipeImage": "/recipes/a/1.webp", "_recipe": {"image": None}}) == "/recipes/a/1.webp"
    assert P({"_recipe": {"image": None, "images": [{"image": "/b.webp", "order": 2}, {"image": "/a.webp", "order": 0}]}}) == "/a.webp"
    assert P({"_recipe": {"image": "/legacy.jpg", "images": []}}) == "/legacy.jpg"
    assert P({}) is None

def _coord_for_images(tmp_path, ctype):
    c = bare_coordinator()
    c.base_url = "https://n"; c._api_key = "k"; c._image_cache_path = str(tmp_path)
    c.hass = MagicMock()
    async def run_exec(f, *a): return f(*a)
    c.hass.async_add_executor_job = run_exec
    session = MagicMock(); session.get = MagicMock(return_value=_resp(200, ctype))
    return c, session

def test_download_uses_recipe_image(tmp_path):
    c, session = _coord_for_images(tmp_path, "image/webp")
    ev = {"recipeId": "r1", "recipeImage": "/recipes/r1/x.webp"}
    with patch("custom_components.norish.coordinator.async_get_clientsession", return_value=session):
        asyncio.run(c._download_and_cache_images({"calendar": [ev]}))
    assert session.get.call_args.args[0] == "https://n/recipes/r1/x.webp"
    assert session.get.call_args.kwargs["headers"]["x-api-key"] == "k"
    assert ev["_local_image"].startswith("/local/norish_images/r1_")
    assert ev["_recipe"]["image"] == "/recipes/r1/x.webp"
    assert len(list(tmp_path.iterdir())) == 1

def test_download_skips_html(tmp_path):
    c, session = _coord_for_images(tmp_path, "text/html")
    ev = {"recipeId": "r1", "recipeImage": "/recipes/r1/x.webp"}
    with patch("custom_components.norish.coordinator.async_get_clientsession", return_value=session):
        asyncio.run(c._download_and_cache_images({"calendar": [ev]}))
    assert "_local_image" not in ev and list(tmp_path.iterdir()) == []

def test_note_items_without_image_untouched(tmp_path):
    c, session = _coord_for_images(tmp_path, "image/webp")
    ev = {"itemType": "note", "title": "Uit eten"}
    asyncio.run(c._download_and_cache_images({"calendar": [ev]}))
    assert "_recipe" not in ev and not session.get.called

# 6. recipe details for the card
from custom_components.norish.sensor import _recipe_extras, NorishWeekPlannerSensor, NorishMealSensor

RECIPE = {"name": "Wraps", "systemUsed": "metric", "servings": 4, "prepMinutes": 15, "totalMinutes": 30,
    "description": "Lekker", "recipeIngredients": [
        {"ingredientName": "Wraps", "amount": 4, "unit": "stuks", "order": "2", "systemUsed": "metric"},
        {"ingredientName": "Kipfilet", "amount": 200.0, "unit": "g", "order": "1", "systemUsed": "metric"},
        {"ingredientName": "Chicken", "amount": 7, "unit": "oz", "order": "1", "systemUsed": "us"}],
    "steps": [{"step": "Bak de kip", "order": 2, "systemUsed": "metric"},
              {"step": "# Saus", "order": 1, "systemUsed": "metric"},
              {"step": "Fry chicken", "order": 1, "systemUsed": "us"}]}

def test_recipe_extras():
    x = _recipe_extras(RECIPE)
    assert [i["name"] for i in x["ingredients"]] == ["Kipfilet", "Wraps"]
    assert x["steps"] == ["# Saus", "Bak de kip"]
    assert x["prep_minutes"] == 15 and x["total_minutes"] == 30 and x["cook_minutes"] is None
    assert x["servings"] == 4 and x["description"] == "Lekker"
    assert _recipe_extras({}) == {}

def test_week_data_contains_details():
    today = dt_util.now().strftime("%Y-%m-%d")
    ev = {"date": today, "slot": "Snack", "recipeId": "r1", "_recipe": RECIPE}
    late = dt_util.start_of_local_day() + timedelta(hours=9)
    s = NorishWeekPlannerSensor(fake_coord([ev]), entry())
    with patch("custom_components.norish.sensor.dt_util.now", return_value=late):
        meal = s._get_week_data()[0]["meals"][0]
    assert meal["name"] == "Wraps" and meal["steps"] == ["# Saus", "Bak de kip"]
    assert "week_data" in s._unrecorded_attributes and "raw_data" in NorishMealSensor._unrecorded_attributes

# 7. units are translated like Norish does
import json as _json
from custom_components.norish.sensor import _localize_unit
UNITS = _json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "units.json")))

def test_localize_units_nl():
    L = lambda u, a, lang="nl": _localize_unit(u, a, UNITS, lang)
    print({u: (L(u, 1), L(u, 4)) for u in ["gram", "tablespoon", "piece", "chunk", "bunch", "teaspoon"]})
    assert L("tablespoon", 6) in ("el", "eetlepels") and L("piece", 1) == "stuk" and L("piece", 8) == "stuks"
    assert L("onbekend", 2) == "onbekend" and L("", None) == ""
    assert L("piece", 1, "xx") == "piece" and L("piece", 1, "de-formal") == "Stk."

def test_units_in_week_data():
    today = dt_util.now().strftime("%Y-%m-%d")
    r = dict(RECIPE, recipeIngredients=[{"ingredientName": "Passata", "amount": 6, "unit": "tablespoon", "order": 1, "systemUsed": "metric"}])
    c = fake_coord([{"date": today, "slot": "Snack", "recipeId": "r1", "_recipe": r}])
    c.data["units"] = UNITS; c.hass = SimpleNamespace(config=SimpleNamespace(language="nl"))
    s = NorishWeekPlannerSensor(c, entry())
    with patch("custom_components.norish.sensor.dt_util.now", return_value=dt_util.start_of_local_day() + timedelta(hours=9)):
        ing = s._get_week_data()[0]["meals"][0]["ingredients"][0]
    assert ing["unit"] != "tablespoon", ing

def test_fetch_units_cached():
    c = bare_coordinator(); c._cached_units = {}; c._units_last_fetched = None
    c._fetch_trpc = AsyncMock(return_value=[{"result": {"data": {"json": {"gram": {"short": []}}}}}])
    d = {}; asyncio.run(c._fetch_units_cached(d)); asyncio.run(c._fetch_units_cached(d))
    assert "gram" in d["units"] and c._fetch_trpc.call_count == 1
    c2 = bare_coordinator(); c2._cached_units = {}; c2._units_last_fetched = None
    c2._fetch_trpc = AsyncMock(return_value=None)
    d = {}; asyncio.run(c2._fetch_units_cached(d)); asyncio.run(c2._fetch_units_cached(d))
    assert d["units"] == {} and c2._fetch_trpc.call_count == 1  # retried later, not every poll

def test_ingredient_unit_forms_for_rescaling():
    r = dict(RECIPE, recipeIngredients=[
        {"ingredientName": "Komkommer", "amount": 1, "unit": "piece", "order": 1, "systemUsed": "metric"},
        {"ingredientName": "Zout", "amount": None, "unit": "", "order": 2, "systemUsed": "metric"}])
    piece, salt = _recipe_extras(r, UNITS, "nl")["ingredients"]
    assert (piece["unit"], piece["unit_one"], piece["unit_other"]) == ("stuk", "stuk", "stuks")
    assert "unit_one" not in salt  # no unit: no extra forms
