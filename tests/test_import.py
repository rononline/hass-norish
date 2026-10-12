"""Tests: importing recipes from a URL (action, realtime events, share blueprint)."""
import asyncio
import json
import os
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import jinja2
import pytest
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util.yaml import load_yaml

import custom_components.norish.realtime as rt
import custom_components.norish.services as svc
from custom_components.norish.coordinator import NorishCoordinator


class FakeResp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def json(self, content_type=None):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def coord(status=200, body=None, error=None):
    c = object.__new__(NorishCoordinator)
    c.hass = MagicMock()
    c.base_url = "https://norish.example"
    c._get_headers = lambda: {"x-api-key": "k"}
    session = MagicMock()
    if error:
        session.post = MagicMock(side_effect=error)
    else:
        session.post = MagicMock(return_value=FakeResp(status, body))
    return c, session


def _run(c, session, url="https://www.ah.nl/recept", force_ai=False):
    with patch("custom_components.norish.coordinator.async_get_clientsession", return_value=session):
        return asyncio.run(c.async_import_recipe(url, force_ai))


def test_import_queued_and_payload():
    c, session = coord(200, [{"result": {"data": {"json": {"recipeId": "r1", "status": "queued"}}}}])
    assert _run(c, session, force_ai=True) == {"recipe_id": "r1", "status": "queued"}
    url = session.post.call_args.args[0]
    body = json.loads(session.post.call_args.kwargs["data"])
    assert url == "https://norish.example/api/trpc/recipes.importFromUrl?batch=1"
    assert body == {"0": {"json": {"url": "https://www.ah.nl/recept", "forceAI": True}}}


def test_import_exists():
    c, session = coord(200, [{"result": {"data": {"json": {"recipeId": "r9", "status": "exists"}}}}])
    assert _run(c, session) == {"recipe_id": "r9", "status": "exists"}
    assert "forceAI" not in json.loads(session.post.call_args.kwargs["data"])["0"]["json"]


def test_import_refused_shows_norish_message():
    c, session = coord(409, [{"error": {"json": {"message": "An import of this recipe is already in flight",
                                                   "code": -32009, "data": {"httpStatus": 409}}}}])
    with pytest.raises(HomeAssistantError, match="already in flight"):
        _run(c, session)


@pytest.mark.parametrize("status,body", [(500, ValueError("no json")), (200, [{"result": {"data": {"json": {}}}}])])
def test_import_unexpected_answer(status, body):
    c, session = coord(status, body)
    with pytest.raises(HomeAssistantError):
        _run(c, session)


def test_import_unreachable():
    c, session = coord(error=aiohttp.ClientConnectionError("down"))
    with pytest.raises(HomeAssistantError, match="not reachable"):
        _run(c, session)


def test_service_import_and_validation():
    c = SimpleNamespace(async_import_recipe=AsyncMock(return_value={"recipe_id": "r1", "status": "queued"}))
    hass = MagicMock(); hass.data = {"norish": {"e1": c}}
    data = svc.IMPORT_RECIPE_SCHEMA({"url": "https://x.nl/r"})
    assert asyncio.run(svc._import_recipe(SimpleNamespace(hass=hass, data=data))) == {"recipe_id": "r1", "status": "queued"}
    c.async_import_recipe.assert_awaited_once_with("https://x.nl/r", False)
    with pytest.raises(Exception):
        svc.IMPORT_RECIPE_SCHEMA({"url": "geen url"})
    hass.data = {"norish": {}}
    with pytest.raises(ServiceValidationError):
        asyncio.run(svc._import_recipe(SimpleNamespace(hass=hass, data=data)))


@pytest.mark.parametrize("path,envelope,expected", [
    ("recipes.onImported",
     {"payload": {"recipe": {"id": "r2", "name": "Wraps"}, "pendingRecipeId": "r1", "toast": "imported"}},
     {"kind": "recipes.imported", "recipe_id": "r2", "title": "Wraps", "import_id": "r1"}),
    ("recipes.onFailed",
     {"payload": {"reason": "No recipe found", "recipeId": "r1", "url": "https://x.nl"}},
     {"kind": "recipes.failed", "import_id": "r1", "url": "https://x.nl", "reason": "No recipe found"}),
])
def test_recipe_event_data(path, envelope, expected):
    assert rt.event_data(path, envelope) == expected


def test_recipe_events_do_not_refresh():
    async def go():
        refresh = AsyncMock()
        c = SimpleNamespace(api_key="k", base_url="https://n", set_realtime=lambda x: None,
                            async_request_refresh=refresh)
        fired = []
        client = rt.NorishRealtime(SimpleNamespace(bus=SimpleNamespace(async_fire=lambda t, d: fired.append(d))), c)
        imported = rt.SUBSCRIPTIONS.index("recipes.onImported") + 1
        groceries = rt.SUBSCRIPTIONS.index("groceries.onCreated") + 1
        msg = lambda i: json.dumps({"id": i, "result": {"type": "data", "data": {"json": {"payload": {}}}}})
        await client._handle(msg(imported), True)
        assert fired[-1]["kind"] == "recipes.imported" and not refresh.called
        await client._handle(msg(groceries), True)
        assert refresh.await_count == 1
    asyncio.run(go())


PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blueprints", "automation", "norish", "share_to_norish.yaml")


def test_share_blueprint_valid():
    bp = Blueprint(load_yaml(PATH), expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    config = BlueprintInputs(bp, {"use_blueprint": {"path": "norish/share_to_norish.yaml", "input": {}}}).async_substitute()
    assert config["triggers"][0]["event_type"] == "mobile_app.share"
    assert config["actions"][0]["action"] == "norish.import_recipe"


@pytest.mark.parametrize("data,expected", [
    ({"caller": "com.android.chrome", "subject": "Wraps", "url": "https://www.ah.nl/r/1"}, "https://www.ah.nl/r/1"),
    ({"text": "Kijk dit recept https://www.leukerecepten.nl/recepten/soep/ lekker"}, "https://www.leukerecepten.nl/recepten/soep/"),
    ({"text": "geen link"}, ""),
])
def test_share_url_extraction(data, expected):
    template = load_yaml(PATH)["variables"]["shared"]
    env = jinja2.Environment()
    env.filters["regex_findall"] = lambda v, p: re.findall(p, v)
    env.tests["regex_search"] = lambda v, p: re.search(p, v) is not None
    env.filters["regex_search"] = lambda v, p: re.search(p, v) is not None
    out = env.from_string(template).render(trigger={"event": {"data": data}})
    assert out.strip() == expected
