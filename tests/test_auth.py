"""Tests: Norish request limit vs. invalid key handling."""
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp, pytest
from homeassistant.util import dt as dt_util
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import custom_components.norish.coordinator as co
from custom_components.norish.coordinator import NorishCoordinator, NorishRateLimited

dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Amsterdam"))

def resp(status, body=None, cookies=None):
    r = MagicMock(status=status, headers={}, content_type="application/json")
    r.json = AsyncMock(return_value=body)
    r.text = AsyncMock(return_value=str(body))
    r.cookies = cookies or {}
    ctx = MagicMock(); ctx.__aenter__ = AsyncMock(return_value=r); ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx

def coord():
    c = object.__new__(NorishCoordinator)
    c.base_url = "https://n"; c._api_key = "k"; c.hass = MagicMock()
    c._consecutive_auth_failures = 0; c._consecutive_failures = 0
    c._rate_limited_until = None; c._renewal_in_progress = False
    c.last_success = None; c.stale = False; c._prefetched = {}
    c._prefetch_trpc = AsyncMock()  # update-loop tests stub the batch request
    c._norish_email = ""; c._norish_password = ""
    c._normal_update_interval = timedelta(minutes=15); c.update_interval = timedelta(minutes=15)
    return c

def session_with(*responses):
    s = MagicMock(); s.get = MagicMock(side_effect=list(responses)); s.post = MagicMock(side_effect=list(responses))
    return s

def run(c, coro, session):
    with patch.object(co, "async_get_clientsession", return_value=session):
        return asyncio.run(coro)

RATE = {"code": "RATE_LIMITED", "message": "Rate limit exceeded.", "details": {"tryAgainIn": 1_800_000}}

def test_key_status_variants():
    c = coord()
    assert run(c, c._async_key_status(), session_with(resp(200, {"user": {}}))) == ("valid", 0)
    assert run(c, c._async_key_status(), session_with(resp(401, RATE))) == ("rate_limited", 1860)
    assert run(c, c._async_key_status(), session_with(resp(401, {"code": "RATE_LIMITED"}))) == ("rate_limited", 3660)
    assert run(c, c._async_key_status(), session_with(resp(401, {"code": "INVALID_API_KEY"}))) == ("invalid", 0)
    assert run(c, c._async_key_status(), session_with(resp(500, None))) == (None, 0)
    s = MagicMock(); s.get = MagicMock(side_effect=aiohttp.ClientConnectionError())
    assert run(c, c._async_key_status(), s) == (None, 0)

def test_rate_limit_never_asks_for_reauth():
    c = coord(); c._consecutive_auth_failures = 2  # would have been the 3rd strike before
    session = session_with(resp(401, None), resp(401, RATE))  # tRPC 401, then get-session reason
    with pytest.raises(NorishRateLimited):
        run(c, c._fetch_trpc("calendar.listItems", {}), session)
    assert c._consecutive_auth_failures == 0
    left = (c._rate_limited_until - dt_util.utcnow()).total_seconds()
    assert 1800 < left <= 1860

def test_invalid_key_reauth_after_three():
    c = coord()
    for i in range(1, 4):
        session = session_with(resp(401, None), resp(401, {"code": "INVALID_API_KEY"}))
        exc = ConfigEntryAuthFailed if i == 3 else UpdateFailed
        with pytest.raises(exc) as e:
            run(c, c._fetch_trpc("calendar.listItems", {}), session)
        assert not isinstance(e.value, NorishRateLimited)

def test_transient_401_key_valid():
    c = coord(); c._consecutive_auth_failures = 2
    with pytest.raises(UpdateFailed):
        run(c, c._fetch_trpc("groceries.list"), session_with(resp(401, None), resp(200, {})))
    assert c._consecutive_auth_failures == 0

def test_paused_keeps_data_without_requests():
    c = coord(); c.data = {"calendar": ["old"]}
    c._rate_limited_until = dt_util.utcnow() + timedelta(minutes=20)
    c._fetch_calendar = AsyncMock()
    assert asyncio.run(c._async_update_data()) == {"calendar": ["old"]}
    assert not c._fetch_calendar.called

def test_pause_without_data_fails():
    c = coord(); c.data = None
    c._rate_limited_until = dt_util.utcnow() + timedelta(minutes=20)
    with pytest.raises(UpdateFailed):
        asyncio.run(c._async_update_data())

def test_rate_limit_mid_update_returns_old_data():
    c = coord(); c.data = {"calendar": ["old"]}
    async def boom(data):
        c._rate_limited_until = dt_util.utcnow() + timedelta(minutes=30)
        raise NorishRateLimited("limit")
    c._fetch_calendar = boom
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon):
        assert asyncio.run(c._async_update_data()) == {"calendar": ["old"]}
    assert timedelta(minutes=29) < c.update_interval <= timedelta(minutes=30)

@pytest.mark.parametrize("hour,minute,skipped", [(2, 59, False), (3, 0, True), (3, 45, True), (4, 4, True), (4, 5, False)])
def test_quiet_window(hour, minute, skipped):
    c = coord(); c.data = {"calendar": ["old"]}
    c._fetch_calendar = AsyncMock(side_effect=UpdateFailed("reached network"))
    t = dt_util.start_of_local_day() + timedelta(hours=hour, minutes=minute)
    with patch.object(co.dt_util, "now", return_value=t):
        if skipped:
            assert asyncio.run(c._async_update_data()) == {"calendar": ["old"]}
            assert not c._fetch_calendar.called
        else:
            with pytest.raises(UpdateFailed):
                asyncio.run(c._async_update_data())

def test_quiet_window_gap_longer_than_an_hour():
    # Simulate polls at every interval/offset; the requests just before and just
    # after the quiet window must be more than an hour apart.
    day = datetime(2026, 10, 11)
    for interval in (1, 5, 10, 15, 30, 60):
        for offset in range(0, interval * 60, 37):
            t = day + timedelta(seconds=offset)
            requests = []
            while t < day + timedelta(hours=6):
                if not (co.QUIET_WINDOW_START <= t.time() < co.QUIET_WINDOW_END):
                    requests.append(t)
                t += timedelta(minutes=interval)
            gap = max(b - a for a, b in zip(requests, requests[1:]))
            assert gap > timedelta(hours=1), (interval, offset, gap)

def test_renewal_sends_session_cookie():
    c = coord(); c._norish_email = "a@b.nl"; c._norish_password = "pw"
    c.config_entry = SimpleNamespace(data={"api_key": "k"})
    c.hass.config_entries.async_update_entry = MagicMock()
    c._async_prune_old_keys = AsyncMock()
    cookies = {"__Secure-better-auth.session_token": SimpleNamespace(value="tok.sig")}
    session = MagicMock()
    session.post = MagicMock(side_effect=[resp(200, {"token": "tok"}, cookies), resp(200, {"key": "NEW"})])
    assert run(c, c._async_renew_api_key(), session) is True
    create_headers = session.post.call_args_list[1].kwargs["headers"]
    assert create_headers["Cookie"] == "__Secure-better-auth.session_token=tok.sig"
    assert c._api_key == "NEW" and c._async_prune_old_keys.call_args.kwargs["cookie"].endswith("tok.sig")

# --- stale data grace period
def test_failure_within_grace_keeps_data():
    c = coord(); c.data = {"calendar": ["old"]}; c.stale = False
    c.last_success = dt_util.utcnow() - timedelta(minutes=30)
    c._fetch_calendar = AsyncMock(side_effect=UpdateFailed("server down"))
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon):
        assert asyncio.run(c._async_update_data()) == {"calendar": ["old"]}
    assert c.stale is True and c._consecutive_failures == 1
    assert c.update_interval == timedelta(seconds=60)  # backoff still applies

def test_unexpected_error_within_grace_keeps_data():
    c = coord(); c.data = {"calendar": ["old"]}; c.stale = False
    c.last_success = dt_util.utcnow() - timedelta(minutes=30)
    c._fetch_calendar = AsyncMock(side_effect=ValueError("bad json"))
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon):
        assert asyncio.run(c._async_update_data()) == {"calendar": ["old"]}

def test_failure_after_grace_goes_unavailable():
    c = coord(); c.data = {"calendar": ["old"]}; c.stale = True
    c.last_success = dt_util.utcnow() - co.STALE_DATA_GRACE - timedelta(minutes=1)
    c._fetch_calendar = AsyncMock(side_effect=UpdateFailed("server down"))
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon), pytest.raises(UpdateFailed):
        asyncio.run(c._async_update_data())

def test_auth_failure_is_never_hidden():
    c = coord(); c.data = {"calendar": ["old"]}; c.stale = False
    c.last_success = dt_util.utcnow()
    c._fetch_calendar = AsyncMock(side_effect=ConfigEntryAuthFailed("bad key"))
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon), pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(c._async_update_data())

def test_week_sensor_exposes_stale():
    from custom_components.norish.sensor import NorishWeekPlannerSensor
    c = SimpleNamespace(data={"calendar": []}, base_url="https://n", stale=True,
                        last_success=datetime(2026, 10, 12, 12, 5, tzinfo=dt_util.UTC),
                        async_add_listener=lambda *a: None, config_entry=None)
    s = NorishWeekPlannerSensor(c, SimpleNamespace(entry_id="e1", title="Norish"))
    a = s.extra_state_attributes
    assert a["stale"] is True and a["last_success"].startswith("2026-10-12T12:05")

# --- batched core request
import json as _json, urllib.parse as _up

def _items(*jsons):
    return [{"result": {"data": {"json": j}}} for j in jsons]

def test_prefetch_one_request_for_both():
    c = coord()
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    session = session_with(resp(200, _items([{"date": "x"}], [{"id": "g1"}])))
    data = {}
    with patch.object(co.dt_util, "now", return_value=noon), patch.object(co, "async_get_clientsession", return_value=session):
        asyncio.run(NorishCoordinator._prefetch_trpc(c, [("calendar.listItems", c._calendar_payload()), ("groceries.list", None)]))
        asyncio.run(c._fetch_calendar(data)); asyncio.run(c._fetch_groceries(data))
    assert session.get.call_count == 1  # one HTTP request = one API-key hit
    url = session.get.call_args.args[0]
    assert "/api/trpc/calendar.listItems,groceries.list?batch=1&input=" in url
    sent = _json.loads(_up.unquote(url.split("input=")[1]))
    assert sent["1"] == {"json": None} and "startISO" in sent["0"]["json"]
    assert data["calendar"] == [{"date": "x"}] and data["groceries"] == [{"id": "g1"}]
    assert c._prefetched == {}  # consumed

def test_prefetch_partial_error_falls_back():
    c = coord()
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    batch = [{"result": {"data": {"json": [{"date": "x"}]}}}, {"error": {"message": "boom"}}]
    session = session_with(resp(207, batch), resp(200, _items([{"id": "g2"}])))
    data = {}
    with patch.object(co.dt_util, "now", return_value=noon), patch.object(co, "async_get_clientsession", return_value=session):
        asyncio.run(NorishCoordinator._prefetch_trpc(c, [("calendar.listItems", c._calendar_payload()), ("groceries.list", None)]))
        asyncio.run(c._fetch_calendar(data)); asyncio.run(c._fetch_groceries(data))
    assert session.get.call_count == 2 and data["groceries"] == [{"id": "g2"}]
    assert "/api/trpc/groceries.list?" in session.get.call_args.args[0]

def test_prefetch_failure_falls_back_to_single_calls():
    c = coord()
    session = session_with(resp(404, None), resp(200, _items([{"date": "y"}])))
    data = {}
    with patch.object(co, "async_get_clientsession", return_value=session):
        asyncio.run(NorishCoordinator._prefetch_trpc(c, [("calendar.listItems", c._calendar_payload()), ("groceries.list", None)]))
        asyncio.run(c._fetch_calendar(data))
    assert data["calendar"] == [{"date": "y"}]

def test_min_poll_interval():
    from custom_components.norish.const import POLL_INTERVAL_OPTIONS, MIN_POLL_INTERVAL
    assert 60 not in POLL_INTERVAL_OPTIONS and min(POLL_INTERVAL_OPTIONS) == MIN_POLL_INTERVAL == 300
    import inspect
    src = inspect.getsource(NorishCoordinator.__init__)
    assert "MIN_POLL_INTERVAL" in src

def test_update_uses_batch():
    c = coord(); c.data = None
    c._fetch_calendar = AsyncMock(side_effect=UpdateFailed("stop after prefetch"))
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon), pytest.raises(UpdateFailed):
        asyncio.run(c._async_update_data())
    procs = [p for p, _ in c._prefetch_trpc.call_args.args[0]]
    assert procs == ["calendar.listItems", "groceries.list"]

# --- realtime hooks
def test_set_realtime_slows_and_restores_polling():
    c = coord(); c._configured_update_interval = timedelta(minutes=15)
    c._normal_update_interval = timedelta(minutes=15)
    c.set_realtime(True)
    assert c.update_interval == timedelta(minutes=30) == c._normal_update_interval
    c.set_realtime(False)
    assert c.update_interval == timedelta(minutes=15)
    c._configured_update_interval = timedelta(minutes=60); c.set_realtime(True)
    assert c.update_interval == timedelta(minutes=60)  # never faster than the user's choice

def test_set_realtime_does_not_override_backoff():
    c = coord(); c._configured_update_interval = timedelta(minutes=15)
    c._consecutive_failures = 2; c.update_interval = timedelta(seconds=300)
    c.set_realtime(True)
    assert c.update_interval == timedelta(seconds=300)

def test_seconds_until_requests_allowed():
    c = coord()
    noon = dt_util.start_of_local_day() + timedelta(hours=12)
    with patch.object(co.dt_util, "now", return_value=noon):
        assert c.seconds_until_requests_allowed() == 0.0
        c._rate_limited_until = dt_util.utcnow() + timedelta(minutes=10)
        assert 590 < c.seconds_until_requests_allowed() <= 600
    c._rate_limited_until = None
    t = dt_util.start_of_local_day() + timedelta(hours=3, minutes=30)
    with patch.object(co.dt_util, "now", return_value=t):
        assert c.seconds_until_requests_allowed() == 35 * 60
