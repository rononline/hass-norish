"""Tests: unique-id migration, config flow, media player."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.util import dt as dt_util
import custom_components.norish.todo as todo_mod
import custom_components.norish.config_flow as cf
from custom_components.norish.media_player import NorishVideoPlayer

# --- todo unique id migration
def test_migrate_unique_ids():
    reg = MagicMock()
    ids = {("todo", "norish", "e1_shopping_albert_heijn"): "todo.norish_albert_heijn"}
    reg.async_get_entity_id = lambda d, p, uid: ids.get((d, p, uid))
    coord = SimpleNamespace(data={"stores": {"s-uuid": "Albert Heijn", "s2": "Lidl"}})
    with patch.object(todo_mod.er, "async_get", return_value=reg):
        todo_mod._migrate_unique_ids(MagicMock(), SimpleNamespace(entry_id="e1"), coord)
    reg.async_update_entity.assert_called_once_with("todo.norish_albert_heijn", new_unique_id="e1_shopping_s-uuid")

def test_migrate_skips_when_new_exists():
    reg = MagicMock()
    ids = {("todo", "norish", "e1_shopping_lidl"): "todo.old", ("todo", "norish", "e1_shopping_s2"): "todo.new"}
    reg.async_get_entity_id = lambda d, p, uid: ids.get((d, p, uid))
    with patch.object(todo_mod.er, "async_get", return_value=reg):
        todo_mod._migrate_unique_ids(MagicMock(), SimpleNamespace(entry_id="e1"), SimpleNamespace(data={"stores": {"s2": "Lidl"}}))
    reg.async_update_entity.assert_not_called()

def test_store_entity_unique_id_uses_store_id():
    c = SimpleNamespace(data={}, base_url="https://n", config_entry=None, async_add_listener=lambda *a: None)
    e = todo_mod.NorishStoreList(c, SimpleNamespace(entry_id="e1", title="Norish"), store_id="s-uuid", store_name="Albert Heijn")
    assert e.unique_id == "e1_shopping_s-uuid"

# --- config flow
def flow(entries=()):
    f = cf.NorishConfigFlow()
    f.hass = MagicMock()
    f.context = {}
    f._async_current_entries = lambda include_ignore=True: list(entries)
    f.async_set_unique_id = AsyncMock()
    return f

def test_user_step_rejects_duplicate_url():
    existing = SimpleNamespace(data={"url": "https://Norish.example.nl/"})
    f = flow([existing])
    with patch.object(cf, "_test_api_key", AsyncMock(return_value=None)) as t:
        res = asyncio.run(f.async_step_user({"url": "https://norish.example.nl", "api_key": "k"}))
    assert res["type"] == "abort" and res["reason"] == "already_configured" and not t.called

def test_user_step_sets_unique_id():
    f = flow()
    with patch.object(cf, "_test_api_key", AsyncMock(return_value=None)):
        res = asyncio.run(f.async_step_user({"url": "https://norish.example.nl/", "api_key": "k"}))
    f.async_set_unique_id.assert_awaited_with("https://norish.example.nl")
    assert res["type"] == "create_entry"

def test_reconfigure_keeps_key_and_password():
    entry = SimpleNamespace(data={"url": "https://n", "api_key": "OLD", "norish_email": "a@b", "norish_password": "pw"})
    f = flow(); f.context = {"entry_id": "e1"}
    f.hass.config_entries.async_get_entry = lambda eid: entry
    captured = {}
    f.async_update_reload_and_abort = lambda e, data, reason: captured.update(data) or {"type": "abort", "reason": reason}
    with patch.object(cf, "_test_api_key", AsyncMock(return_value=None)) as t:
        asyncio.run(f.async_step_reconfigure({"url": "https://n2", "api_key": "", "norish_email": "a@b", "norish_password": ""}))
    assert captured["api_key"] == "OLD" and captured["norish_password"] == "pw" and captured["url"] == "https://n2"
    assert t.call_args.args[2] == "OLD"

def test_reconfigure_new_key_replaces():
    entry = SimpleNamespace(data={"url": "https://n", "api_key": "OLD"})
    f = flow(); f.context = {"entry_id": "e1"}
    f.hass.config_entries.async_get_entry = lambda eid: entry
    captured = {}
    f.async_update_reload_and_abort = lambda e, data, reason: captured.update(data) or {"type": "abort"}
    with patch.object(cf, "_test_api_key", AsyncMock(return_value=None)):
        asyncio.run(f.async_step_reconfigure({"url": "https://n", "api_key": "NEW"}))
    assert captured["api_key"] == "NEW"

def test_timeout_is_cannot_connect():
    session = MagicMock(); session.get = MagicMock(side_effect=TimeoutError())
    with patch.object(cf, "async_get_clientsession", return_value=session):
        assert asyncio.run(cf._test_api_key(MagicMock(), "https://n", "k")) == cf.ERROR_CANNOT_CONNECT

# --- media player
def test_media_player_title_and_gallery_video():
    today = dt_util.now().strftime("%Y-%m-%d")
    ev = {"date": today, "slot": "Dinner", "recipeId": "r1",
          "_recipe": {"name": "Wraps", "videos": [{"video": "/recipes/r1/b.mp4", "order": 2}, {"video": "/recipes/r1/a.mp4", "order": 1}]}}
    c = SimpleNamespace(data={"calendar": [ev]}, base_url="https://n", config_entry=None, async_add_listener=lambda *a: None)
    p = NorishVideoPlayer(c, SimpleNamespace(entry_id="e1", title="Norish"), "dinner", "Dinner")
    assert p.media_title == "Wraps"
    assert p._get_video_url() == "https://n/recipes/r1/a.mp4"
