"""Tests: add-recipe-to-groceries action and planning meals from the calendar."""
import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

import custom_components.norish.calendar as cal_mod
import custom_components.norish.services as svc
from custom_components.norish.coordinator import NorishCoordinator

RECIPE = {"id": "r1", "name": "Wraps", "systemUsed": "metric", "recipeIngredients": [
    {"id": "11111111-1111-4111-8111-111111111111", "ingredientName": "Kipfilet", "amount": 400, "unit": "gram", "order": 1, "systemUsed": "metric"},
    {"id": "22222222-2222-4222-8222-222222222222", "ingredientName": "# Saus", "amount": None, "unit": "", "order": 2, "systemUsed": "metric"},
    {"id": "33333333-3333-4333-8333-333333333333", "ingredientName": "Passata", "amount": 6, "unit": "tablespoon", "order": 3, "systemUsed": "metric"},
    {"id": "44444444-4444-4444-8444-444444444444", "ingredientName": "Chicken", "amount": 14, "unit": "ounce", "order": 1, "systemUsed": "us"},
]}


def coord(calendar=()):
    c = object.__new__(NorishCoordinator)
    c.data = {"calendar": list(calendar), "groceries": []}
    c._cached_recipes = {"r1": RECIPE}
    c._post_trpc = AsyncMock(return_value=[{"result": {"data": {"json": {}}}}])
    c._fetch_trpc = AsyncMock()
    c._fetch_recipe_details = AsyncMock(return_value=None)
    c.async_request_refresh = AsyncMock()
    return c


def test_ingredients_payload():
    payload = svc.ingredients_for_groceries(RECIPE)
    assert [p["name"] for p in payload] == ["Kipfilet", "Passata"]  # own system, no headings
    assert payload[0] == {"name": "Kipfilet", "unit": "gram", "amount": 400, "isDone": False,
                          "recipeIngredientId": "11111111-1111-4111-8111-111111111111", "storeId": None}


def test_add_recipe_ingredients():
    c = coord()
    assert asyncio.run(c.async_add_recipe_ingredients("r1")) == (2, "Wraps")
    proc, payload = c._post_trpc.call_args.args
    assert proc == "groceries.create" and len(payload) == 2
    c.async_request_refresh.assert_awaited()


def test_add_unknown_recipe_fails():
    c = coord()
    assert asyncio.run(c.async_add_recipe_ingredients("nope")) == (0, "")
    assert not c._post_trpc.called


def _call(c, **data):
    hass = MagicMock(); hass.data = {"norish": {"e1": c}}
    return asyncio.run(svc._add_recipe_to_groceries(SimpleNamespace(hass=hass, data=data)))


def test_service_today_dinner():
    today = dt_util.now().date().isoformat()
    c = coord([{"date": today, "slot": "Dinner", "recipeId": "r1"}, {"date": today, "slot": "Lunch", "recipeId": "r2"}])
    c.async_add_recipe_ingredients = AsyncMock(return_value=(2, "Wraps"))
    assert _call(c, slot="dinner") == {"added": 2, "recipes": ["Wraps"]}
    c.async_add_recipe_ingredients.assert_awaited_once_with("r1")


def test_service_days_and_recipe_id():
    c = coord([{"date": "2026-10-12", "slot": "Dinner", "recipeId": "r1"},
               {"date": "2026-10-13", "slot": "Dinner", "recipeId": "r1"},
               {"date": "2026-10-14", "slot": "Lunch", "recipeId": "r3"}])
    c.async_add_recipe_ingredients = AsyncMock(return_value=(1, "x"))
    _call(c, date=date(2026, 10, 12), days=3)
    assert [a.args[0] for a in c.async_add_recipe_ingredients.await_args_list] == ["r1", "r3"]  # no duplicates
    c.async_add_recipe_ingredients.reset_mock()
    _call(c, recipe_id="r9")
    c.async_add_recipe_ingredients.assert_awaited_once_with("r9")


def test_service_nothing_planned():
    c = coord([])
    with pytest.raises(ServiceValidationError):
        _call(c)


def test_service_add_failure():
    today = dt_util.now().date().isoformat()
    c = coord([{"date": today, "slot": "Dinner", "recipeId": "r1"}])
    c.async_add_recipe_ingredients = AsyncMock(return_value=(0, ""))
    with pytest.raises(HomeAssistantError):
        _call(c)


# --- calendar planning
@pytest.mark.parametrize("summary,expected", [
    ("Diner: Pasta pesto", ("Dinner", "Pasta pesto")), ("Lunch - Soep", ("Lunch", "Soep")),
    ("Ontbijt: Eieren", ("Breakfast", "Eieren")), ("Uit eten", (None, "Uit eten")),
    ("Pasta: met saus", (None, "Pasta: met saus")),
])
def test_split_slot(summary, expected):
    assert cal_mod._split_slot(summary) == expected


def test_slot_for_time():
    tz = dt_util.get_default_time_zone()
    assert cal_mod._slot_for_time(datetime(2026, 10, 12, 8, 0, tzinfo=tz)) == "Breakfast"
    assert cal_mod._slot_for_time(datetime(2026, 10, 12, 12, 30, tzinfo=tz)) == "Lunch"
    assert cal_mod._slot_for_time(datetime(2026, 10, 12, 18, 0, tzinfo=tz)) == "Dinner"


def test_create_note_when_no_recipe_matches():
    c = coord()
    c._fetch_trpc = AsyncMock(return_value=[{"result": {"data": {"json": {"recipes": [{"id": "r5", "name": "Pasta pesto met kip"}]}}}}])
    assert asyncio.run(c.async_create_calendar_item(date(2026, 10, 12), "Dinner", "Uit eten")) is True
    assert c._post_trpc.call_args.args == ("calendar.createItem",
        {"date": "2026-10-12", "slot": "Dinner", "itemType": "note", "title": "Uit eten"})


def test_create_recipe_on_exact_title():
    c = coord()
    c._fetch_trpc = AsyncMock(return_value=[{"result": {"data": {"json": {"recipes": [{"id": "r5", "name": "Pasta Pesto"}]}}}}])
    asyncio.run(c.async_create_calendar_item(date(2026, 10, 12), "Lunch", "pasta pesto"))
    assert c._post_trpc.call_args.args[1] == {"date": "2026-10-12", "slot": "Lunch", "itemType": "recipe", "recipeId": "r5"}
    assert c._fetch_trpc.call_args.args == ("recipes.list", {"search": "pasta pesto", "searchFields": ["title"], "limit": 10})


def test_delete_calendar_item_uses_version():
    c = coord([{"id": "i1", "version": 4, "date": "2026-10-12"}])
    assert asyncio.run(c.async_delete_calendar_item("i1")) is True
    assert c._post_trpc.call_args.args == ("calendar.deleteItem", {"itemId": "i1", "version": 4})
    assert asyncio.run(c.async_delete_calendar_item("missing")) is False


def _calendar(c):
    e = cal_mod.NorishCalendar(SimpleNamespace(data=c.data, base_url="https://n", config_entry=None,
        async_add_listener=lambda *a: None, async_create_calendar_item=c.async_create_calendar_item,
        async_delete_calendar_item=c.async_delete_calendar_item), SimpleNamespace(entry_id="e1", title="Norish"))
    return e


def test_calendar_entity_create_and_delete():
    c = coord(); c.async_create_calendar_item = AsyncMock(return_value=True); c.async_delete_calendar_item = AsyncMock(return_value=False)
    e = _calendar(c)
    asyncio.run(e.async_create_event(summary="Diner: Wraps", dtstart=date(2026, 10, 12), dtend=date(2026, 10, 13)))
    c.async_create_calendar_item.assert_awaited_with(date(2026, 10, 12), "Dinner", "Wraps")
    tz = dt_util.get_default_time_zone()
    asyncio.run(e.async_create_event(summary="Soep", dtstart=datetime(2026, 10, 12, 12, 0, tzinfo=tz), dtend=datetime(2026, 10, 12, 13, 0, tzinfo=tz)))
    c.async_create_calendar_item.assert_awaited_with(date(2026, 10, 12), "Lunch", "Soep")
    with pytest.raises(HomeAssistantError):
        asyncio.run(e.async_delete_event("i1"))


def test_events_carry_uid():
    today = dt_util.now().date()
    c = coord([{"id": "i1", "date": today.isoformat(), "slot": "Dinner", "recipeName": "Wraps"}])
    e = _calendar(c); e.hass = SimpleNamespace(config=SimpleNamespace(time_zone=str(dt_util.get_default_time_zone())))
    start = dt_util.start_of_local_day()
    from datetime import timedelta
    evs = e._get_events_for_range(start, start + timedelta(days=1))
    assert evs[0].uid == "i1"
