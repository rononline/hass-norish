import asyncio, os, inspect
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.components import frontend as fe
from homeassistant.components.http import StaticPathConfig
from custom_components.norish import frontend as nf

def test_api_signatures():
    assert list(inspect.signature(fe.add_extra_js_url).parameters)[:2] == ["hass", "url"]
    assert {"url_path", "path", "cache_headers"} <= set(inspect.signature(StaticPathConfig).parameters)

def test_register_once():
    hass = MagicMock(); hass.data = {}
    hass.http.async_register_static_paths = AsyncMock()
    async def run_exec(f, *a): return f(*a)
    hass.async_add_executor_job = run_exec
    with patch.object(nf, "add_extra_js_url") as add:
        asyncio.run(nf.async_register_card(hass))
        asyncio.run(nf.async_register_card(hass))
    assert add.call_count == 1
    url = add.call_args.args[1]
    assert url.startswith("/norish_static/norish-card.js?v=") and len(url.split("v=")[1]) == 8
    cfg = hass.http.async_register_static_paths.call_args.args[0][0]
    assert cfg.url_path == "/norish_static" and os.path.isfile(os.path.join(cfg.path, "norish-card.js"))

def test_no_http():
    hass = MagicMock(); hass.data = {}; hass.http = None
    with patch.object(nf, "add_extra_js_url") as add:
        asyncio.run(nf.async_register_card(hass))
    assert not add.called
