"""Tests: realtime client against a mock tRPC 11 WebSocket server."""
import asyncio, json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import aiohttp
from aiohttp import web
import pytest
import custom_components.norish.realtime as rt

class MockNorish:
    """Mimics Norish's /trpc upgrade + tRPC applyWSSHandler behaviour."""
    def __init__(self, key="good"):
        self.key = key; self.connections = 0; self.subscriptions = []; self.pongs = 0
        self.sockets = []
    async def handler(self, request):
        ws = web.WebSocketResponse(); await ws.prepare(request)
        self.connections += 1
        if request.headers.get("x-api-key") != self.key:
            await ws.close(code=4401, message=b"Unauthorized"); return ws
        self.sockets.append(ws)
        await ws.send_str("PING")
        async for msg in ws:
            if msg.data == "PONG":
                self.pongs += 1; continue
            m = json.loads(msg.data)
            assert m["method"] == "subscription" and isinstance(m["id"], int)
            assert m["params"]["input"] == {"json": {}}  # superjson-wrapped, schema-valid
            self.subscriptions.append(m["params"]["path"])
            await ws.send_str(json.dumps({"id": m["id"], "result": {"type": "started"}}))
            await ws.send_str(json.dumps({"id": m["id"], "result": {"type": "data", "id": "c0", "data": {"json": {"mark": "cursor"}}}}))
        return ws

def make_coord(port, key="good"):
    return SimpleNamespace(base_url=f"http://127.0.0.1:{port}", api_key=key,
                           async_request_refresh=AsyncMock(), set_realtime=lambda c: states.append(c),
                           seconds_until_requests_allowed=lambda: 0.0)
states = []

async def start_server(mock):
    app = web.Application(); app.router.add_get("/trpc", mock.handler)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0); await site.start()
    return runner, site._server.sockets[0].getsockname()[1]

async def wait_for(cond, timeout=5):
    for _ in range(int(timeout / 0.02)):
        if cond(): return True
        await asyncio.sleep(0.02)
    return False

def test_full_flow():
    async def go():
        states.clear()
        mock = MockNorish(); runner, port = await start_server(mock)
        coord = make_coord(port)
        async with aiohttp.ClientSession() as session:
            with patch.object(rt, "async_get_clientsession", return_value=session), \
                 patch.object(rt, "RECONNECT_MIN", 0.05):
                fired = []
                hass = SimpleNamespace(bus=SimpleNamespace(async_fire=lambda t, d: fired.append((t, d))))
                client = rt.NorishRealtime(hass, coord)
                task = asyncio.create_task(client._run())
                assert await wait_for(lambda: len(mock.subscriptions) == len(rt.SUBSCRIPTIONS))
                assert mock.subscriptions == list(rt.SUBSCRIPTIONS)
                assert await wait_for(lambda: mock.pongs >= 1)          # answered PING
                assert await wait_for(lambda: True in states) and client.connected
                assert coord.async_request_refresh.await_count == 1        # one catch-up, cursors ignored
                # a real change on groceries.onUpdated
                sub_id = rt.SUBSCRIPTIONS.index("groceries.onUpdated") + 1
                await mock.sockets[0].send_str(json.dumps({"id": sub_id, "result": {"type": "data", "id": "e1",
                    "data": {"json": {"meta": {"channel": "x"}, "payload": {"groceries": [{"name": "melk"}]}}}}}))
                assert await wait_for(lambda: coord.async_request_refresh.await_count == 2)
                assert fired == [("norish_change", {"kind": "groceries.updated", "names": ["melk"]})]
                # unknown subscription error is skipped, socket stays
                await mock.sockets[0].send_str(json.dumps({"id": 3, "error": {"message": "No procedure found"}}))
                await asyncio.sleep(0.1); assert mock.connections == 1
                # server restart notice → reconnect and resubscribe
                await mock.sockets[0].send_str(json.dumps({"id": None, "method": "reconnect"}))
                assert await wait_for(lambda: mock.connections == 2 and len(mock.subscriptions) == 2 * len(rt.SUBSCRIPTIONS))
                assert False in states  # went disconnected in between
                # lagged subscription → refetch + reconnect
                n = coord.async_request_refresh.await_count
                await mock.sockets[1].send_str(json.dumps({"id": 1, "error": {"message": "REALTIME_LAGGED", "code": -32012}}))
                assert await wait_for(lambda: mock.connections == 3)
                assert coord.async_request_refresh.await_count > n
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        await runner.cleanup()
    asyncio.run(go())

def test_unauthorized_waits_long():
    async def go():
        mock = MockNorish(key="other"); runner, port = await start_server(mock)
        coord = make_coord(port, key="bad")
        sleeps = []
        real_sleep = asyncio.sleep
        async def fake_sleep(s):
            sleeps.append(s)
            if len(sleeps) >= 1: raise asyncio.CancelledError
            await real_sleep(0)
        async with aiohttp.ClientSession() as session:
            with patch.object(rt, "async_get_clientsession", return_value=session), \
                 patch.object(rt.asyncio, "sleep", fake_sleep):
                client = rt.NorishRealtime(SimpleNamespace(), coord)
                with pytest.raises(asyncio.CancelledError):
                    await client._run()
        assert mock.connections == 1 and sleeps == [rt.RECONNECT_MAX] and not client.connected
        await runner.cleanup()
    asyncio.run(go())

def test_waits_during_quiet_window():
    async def go():
        coord = SimpleNamespace(base_url="http://127.0.0.1:9", api_key="k", set_realtime=lambda c: None,
                                seconds_until_requests_allowed=lambda: 1800.0, async_request_refresh=AsyncMock())
        sleeps = []
        async def fake_sleep(s):
            sleeps.append(s); raise asyncio.CancelledError
        with patch.object(rt.asyncio, "sleep", fake_sleep), patch.object(rt, "async_get_clientsession") as gs:
            with pytest.raises(asyncio.CancelledError):
                await rt.NorishRealtime(SimpleNamespace(), coord)._run()
            assert not gs.called and sleeps == [1800.0]
    asyncio.run(go())

def test_ws_url():
    c = rt.NorishRealtime(SimpleNamespace(), SimpleNamespace(base_url="https://norish.example.nl"))
    assert c._ws_url() == "wss://norish.example.nl/trpc"
    c = rt.NorishRealtime(SimpleNamespace(), SimpleNamespace(base_url="http://10.0.0.2:3000"))
    assert c._ws_url() == "ws://10.0.0.2:3000/trpc"


def test_flapping_connection_backs_off():
    # Connections that drop quickly must not reconnect at the minimum delay
    async def go():
        coord = SimpleNamespace(base_url="http://127.0.0.1:9", api_key="k", set_realtime=lambda c: None,
                                seconds_until_requests_allowed=lambda: 0.0, async_request_refresh=AsyncMock())
        client = rt.NorishRealtime(SimpleNamespace(), coord)
        client._connect_once = AsyncMock(return_value=1006)  # dropped right away
        sleeps = []
        async def fake_sleep(s):
            sleeps.append(s)
            if len(sleeps) >= 8:
                raise asyncio.CancelledError
        with patch.object(rt.asyncio, "sleep", fake_sleep), patch.object(rt.ir, "async_create_issue") as issue:
            with pytest.raises(asyncio.CancelledError):
                await client._run()
        assert sleeps[:4] == [10, 20, 40, 80] and sleeps[-1] == rt.RECONNECT_MAX
        # after 5 failed attempts a repair issue explains the fallback (once)
        assert issue.call_count == 1 and issue.call_args.args[1:3] == ("norish", "realtime_unavailable")
    asyncio.run(go())


@pytest.mark.parametrize("path,envelope,expected", [
    ("groceries.onCreated", {"payload": {"groceries": [{"name": "melk"}, {"name": "brood"}]}},
     {"kind": "groceries.created", "names": ["melk", "brood"]}),
    ("calendar.onItemCreated", {"payload": {"item": {"date": "2026-10-12", "slot": "Dinner", "recipeName": "Wraps"}}},
     {"kind": "calendar.item_created", "date": "2026-10-12", "slot": "Dinner", "title": "Wraps"}),
    ("calendar.onItemDeleted", {"payload": {"itemId": "i1", "date": "2026-10-12", "slot": "Lunch"}},
     {"kind": "calendar.item_deleted", "date": "2026-10-12", "slot": "Lunch"}),
    ("stores.onUpdated", {"payload": {"x": 1}}, {"kind": "stores.updated"}),
    ("groceries.onDeleted", None, {"kind": "groceries.deleted"}),
])
def test_event_data(path, envelope, expected):
    assert rt.event_data(path, envelope) == expected


def test_issue_cleared_on_connect():
    async def go():
        coord = SimpleNamespace(api_key="k", base_url="https://n", set_realtime=lambda c: None,
                                async_request_refresh=AsyncMock())
        client = rt.NorishRealtime(SimpleNamespace(), coord)
        client._issue_raised = True; client._failed_attempts = 7
        with patch.object(rt.ir, "async_delete_issue") as delete:
            await client._handle(json.dumps({"id": 1, "result": {"type": "started"}}), False)
        delete.assert_called_once()
        assert client._failed_attempts == 0 and not client._issue_raised and client._started
    asyncio.run(go())
