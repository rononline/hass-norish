"""Tests: grocery create/toggle/delete against current Norish API."""
import asyncio, json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntityFeature
from homeassistant.exceptions import HomeAssistantError
from custom_components.norish.coordinator import NorishCoordinator
from custom_components.norish.todo import NorishStoreList, _parse_summary

def coord(groceries):
    c = object.__new__(NorishCoordinator)
    c.data = {"groceries": groceries, "stores": {}}; c.base_url = "https://n"; c.config_entry = None
    c._post_trpc = AsyncMock(return_value=[{"result": {"data": {"json": {"success": True}}}}])
    c.async_request_refresh = AsyncMock()
    return c

G = [{"id": "11111111-1111-4111-8111-111111111111", "name": "melk", "version": 3, "storeId": "s1"}]

def test_toggle_sends_id_and_version():
    c = coord(G)
    assert asyncio.run(c.async_toggle_grocery(G[0]["id"], True)) is True
    proc, payload = c._post_trpc.call_args.args
    assert proc == "groceries.toggle" and payload == {"groceries": [{"id": G[0]["id"], "version": 3}], "isDone": True}

def test_delete_sends_id_and_version():
    c = coord(G)
    assert asyncio.run(c.async_delete_groceries([G[0]["id"]])) is True
    assert c._post_trpc.call_args.args[1] == {"groceries": [{"id": G[0]["id"], "version": 3}]}

def test_falls_back_to_old_format():
    c = coord(G)
    c._post_trpc = AsyncMock(side_effect=[None, [{"ok": 1}]])  # new format rejected (older Norish)
    assert asyncio.run(c.async_toggle_grocery(G[0]["id"], False)) is True
    assert c._post_trpc.call_args.args[1] == {"groceryIds": [G[0]["id"]], "isDone": False}

def test_old_norish_without_version_uses_old_format_directly():
    c = coord([{"id": "x", "name": "a"}])
    asyncio.run(c.async_delete_groceries(["x"]))
    assert c._post_trpc.call_count == 1 and c._post_trpc.call_args.args[1] == {"groceryIds": ["x"]}

def test_toggle_failure_returns_false():
    c = coord(G); c._post_trpc = AsyncMock(return_value=None)
    assert asyncio.run(c.async_toggle_grocery(G[0]["id"], True)) is False

def test_create_payload():
    c = coord(G)
    assert asyncio.run(c.async_create_grocery("melk", 2.0, "s1")) is True
    proc, payload = c._post_trpc.call_args.args
    assert proc == "groceries.create"
    assert payload == [{"name": "melk", "unit": None, "amount": 2.0, "isDone": False, "storeId": "s1"}]
    json.dumps(payload)  # serialisable
    c.async_request_refresh.assert_awaited()

@pytest.mark.parametrize("text,expected", [
    ("melk", ("melk", None)), ("2 melk", ("melk", 2.0)), ("1,5 kg bloem", ("kg bloem", 1.5)),
    ("3x eieren", ("eieren", 3.0)), ("  brood  ", ("brood", None)), ("7up", ("7up", None)), ("2", ("2", None)),
])
def test_parse_summary(text, expected):
    assert _parse_summary(text) == expected

def _entity(c, store_id):
    e = NorishStoreList(c, SimpleNamespace(entry_id="e1", title="Norish"), store_id=store_id, store_name="AH" if store_id else "Unsorted")
    e.hass = MagicMock()
    return e

def test_entity_supports_create_and_files_under_store():
    c = coord(G); c.async_create_grocery = AsyncMock(return_value=True)
    e = _entity(c, "s1")
    assert e.supported_features & TodoListEntityFeature.CREATE_TODO_ITEM
    asyncio.run(e.async_create_todo_item(TodoItem(summary="2 melk", status=TodoItemStatus.NEEDS_ACTION)))
    c.async_create_grocery.assert_awaited_with("melk", 2.0, "s1")
    u = _entity(c, None)
    asyncio.run(u.async_create_todo_item(TodoItem(summary="brood", status=TodoItemStatus.NEEDS_ACTION)))
    c.async_create_grocery.assert_awaited_with("brood", None, None)

def test_entity_raises_on_failure():
    c = coord(G)
    c.async_toggle_grocery = AsyncMock(return_value=False); c.async_delete_groceries = AsyncMock(return_value=False)
    c.async_create_grocery = AsyncMock(return_value=False)
    e = _entity(c, "s1")
    with pytest.raises(HomeAssistantError):
        asyncio.run(e.async_update_todo_item(TodoItem(uid=G[0]["id"], summary="melk", status=TodoItemStatus.COMPLETED)))
    with pytest.raises(HomeAssistantError):
        asyncio.run(e.async_delete_todo_items([G[0]["id"]]))
    with pytest.raises(HomeAssistantError):
        asyncio.run(e.async_create_todo_item(TodoItem(summary="x", status=TodoItemStatus.NEEDS_ACTION)))


def test_item_summary_uses_translated_units():
    from custom_components.norish.todo import _grocery_to_todo_item
    units = {"tablespoon": {"short": [{"locale": "nl", "name": "el"}], "plural": [{"locale": "nl", "name": "eetlepels"}]}}
    s = lambda g: _grocery_to_todo_item(g, units, "nl").summary
    assert s({"id": "1", "name": "passata", "amount": 6, "unit": "tablespoon"}) == "6 eetlepels passata"
    assert s({"id": "2", "name": "kipfilet", "amount": 400.0, "unit": "gram"}) == "400 gram kipfilet"
    assert s({"id": "3", "name": "melk", "amount": 2.0, "unit": ""}) == "2× melk"
    assert s({"id": "4", "name": "bloem", "amount": 0.5, "unit": None}) == "0.5× bloem"
    assert s({"id": "5", "name": "zout"}) == "zout"
