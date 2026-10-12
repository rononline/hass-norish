"""Realtime updates from Norish over its tRPC WebSocket.

Norish pushes changes to calendar, groceries and stores over a WebSocket at
``/trpc`` (tRPC subscriptions, superjson payloads). Listening there makes
Home Assistant update within seconds of a change in the Norish app, instead
of on the next poll.

The connection is authenticated once with the API key (one request towards
Norish's per-key limit); while it is up, polling drops to a slow safety net.
Every failure falls back to normal polling and reconnects with backoff.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import NorishCoordinator

_LOGGER = logging.getLogger(__name__)

# Changes that affect what the integration shows
SUBSCRIPTIONS: tuple[str, ...] = (
    "calendar.onItemCreated",
    "calendar.onItemUpdated",
    "calendar.onItemMoved",
    "calendar.onItemDeleted",
    "groceries.onCreated",
    "groceries.onUpdated",
    "groceries.onDeleted",
    "stores.onCreated",
    "stores.onUpdated",
    "stores.onDeleted",
)

# Fired on the HA event bus for every change Norish pushes
EVENT_NORISH_CHANGE = "norish_change"

# Poll interval while the WebSocket is connected (safety net only)
REALTIME_POLL_INTERVAL = timedelta(minutes=30)

# Close code Norish uses for an unauthenticated socket
WS_CLOSE_UNAUTHORIZED = 4401
# Error message ending a subscription that fell behind (refetch + resubscribe)
REALTIME_LAGGED = "REALTIME_LAGGED"

# After this many failed connection attempts in a row, raise a repair issue
# (usually the reverse proxy does not forward WebSocket upgrades on /trpc)
REPAIR_AFTER_FAILURES = 5
ISSUE_REALTIME = "realtime_unavailable"

RECONNECT_MIN = 10  # seconds
RECONNECT_MAX = 900
# A connection that stayed up this long counts as healthy (resets backoff).
# Long on purpose: every connect costs one request towards Norish's limit, so
# a proxy that keeps dropping the socket must not cause a reconnect storm.
HEALTHY_AFTER = timedelta(minutes=30)


class NorishRealtime:
    """Keeps a WebSocket to Norish open and refreshes on every change."""

    def __init__(self, hass: HomeAssistant, coordinator: NorishCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._task: asyncio.Task | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self.connected = False
        self._failed_attempts = 0
        self._issue_raised = False
        self._started = False

    def start(self) -> None:
        """Start the background connection loop."""
        if self._task is None:
            self._task = self._hass.async_create_background_task(
                self._run(), "norish_realtime"
            )

    async def stop(self) -> None:
        """Stop the loop and close the socket."""
        task, self._task = self._task, None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._set_connected(False)

    # ------------------------------------------------------------------

    def _ws_url(self) -> str:
        base = self._coordinator.base_url
        if base.startswith("https://"):
            return "wss://" + base[len("https://"):] + "/trpc"
        if base.startswith("http://"):
            return "ws://" + base[len("http://"):] + "/trpc"
        return base + "/trpc"

    def _set_connected(self, connected: bool) -> None:
        if connected != self.connected:
            self.connected = connected
            self._coordinator.set_realtime(connected)

    def _seconds_until_allowed(self) -> float:
        """Wait out the nightly quiet window and request-limit pauses."""
        return self._coordinator.seconds_until_requests_allowed()

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while True:
            wait = self._seconds_until_allowed()
            if wait > 0:
                self._set_connected(False)
                await asyncio.sleep(wait)
                continue

            started = dt_util.utcnow()
            close_code: int | None = None
            self._started = False
            try:
                close_code = await self._connect_once()
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                _LOGGER.debug("Norish realtime: connection failed: %s", err)
            except Exception:  # noqa: BLE001 – never let the loop die
                _LOGGER.exception("Norish realtime: unexpected error")
            finally:
                self._set_connected(False)

            if not self._started:
                self._failed_attempts += 1
                if self._failed_attempts == REPAIR_AFTER_FAILURES:
                    self._raise_issue()
            if dt_util.utcnow() - started > HEALTHY_AFTER:
                delay = RECONNECT_MIN
            if close_code == WS_CLOSE_UNAUTHORIZED:
                # Key refused (e.g. request limit): polling handles recovery
                delay = RECONNECT_MAX
            _LOGGER.debug("Norish realtime: reconnecting in %d s", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _connect_once(self) -> int | None:
        """Connect, subscribe and listen until the socket closes."""
        session = async_get_clientsession(self._hass)
        async with session.ws_connect(
            self._ws_url(),
            headers={
                "x-api-key": self._coordinator.api_key,
                "User-Agent": "HomeAssistant/Norish",
            },
            heartbeat=None,  # Norish sends its own PING text frames
            timeout=aiohttp.ClientWSTimeout(ws_close=10),
        ) as ws:
            self._ws = ws
            for index, path in enumerate(SUBSCRIPTIONS, start=1):
                await ws.send_str(json.dumps({
                    "id": index,
                    "method": "subscription",
                    "params": {"path": path, "input": {"json": {}}},
                }))

            subscribed = False
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "PING":
                        await ws.send_str("PONG")
                        continue
                    if msg.data == "PONG":
                        continue
                    subscribed = await self._handle(msg.data, subscribed)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break
            self._ws = None
            _LOGGER.debug("Norish realtime: socket closed (code %s)", ws.close_code)
            return ws.close_code

    def _raise_issue(self) -> None:
        """Explain in Repairs why instant updates are not working."""
        _LOGGER.warning(
            "Norish realtime: %d connection attempts failed – falling back to "
            "polling. Check that the reverse proxy forwards WebSocket upgrades "
            "on /trpc.", self._failed_attempts,
        )
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_REALTIME,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_REALTIME,
            translation_placeholders={"url": self._ws_url()},
        )
        self._issue_raised = True

    def _fire_event(self, sub_id: Any, envelope: Any) -> None:
        """Fire norish_change on the HA event bus for automations."""
        if not isinstance(sub_id, int) or not 1 <= sub_id <= len(SUBSCRIPTIONS):
            return
        data = event_data(SUBSCRIPTIONS[sub_id - 1], envelope)
        self._hass.bus.async_fire(EVENT_NORISH_CHANGE, data)

    async def _handle(self, raw: str, subscribed: bool) -> bool:
        """Handle one tRPC message; return whether subscriptions are live."""
        try:
            message = json.loads(raw)
        except ValueError:
            return subscribed
        if not isinstance(message, dict):
            return subscribed

        if message.get("method") == "reconnect":
            # Server restarting: close and let the loop reconnect
            if self._ws is not None:
                await self._ws.close()
            return subscribed

        if "error" in message:
            error = message["error"] if isinstance(message["error"], dict) else {}
            if REALTIME_LAGGED in json.dumps(error):
                # Norish dropped events for this subscription: refetch and
                # resubscribe by reconnecting
                _LOGGER.debug("Norish realtime: subscription lagged – resyncing")
                await self._coordinator.async_request_refresh()
                if self._ws is not None:
                    await self._ws.close()
            else:
                # e.g. a subscription an older Norish does not have: skip it
                _LOGGER.debug(
                    "Norish realtime: subscription %s failed: %s",
                    message.get("id"), error.get("message", error),
                )
            return subscribed

        result = message.get("result")
        if not isinstance(result, dict):
            return subscribed

        if result.get("type") == "started" and not subscribed:
            _LOGGER.info("Norish realtime: connected – changes arrive instantly")
            self._started = True
            self._failed_attempts = 0
            if self._issue_raised:
                ir.async_delete_issue(self._hass, DOMAIN, ISSUE_REALTIME)
                self._issue_raised = False
            self._set_connected(True)
            # Catch up on anything that changed while disconnected
            await self._coordinator.async_request_refresh()
            return True

        if result.get("type") == "data":
            data = result.get("data")
            payload = data.get("json") if isinstance(data, dict) else None
            # Cursor marks keep a quiet subscription resumable – not a change
            if isinstance(payload, dict) and payload.get("mark") == "cursor":
                return subscribed
            _LOGGER.debug("Norish realtime: change on subscription %s", message.get("id"))
            self._fire_event(message.get("id"), payload)
            await self._coordinator.async_request_refresh()
        return subscribed



def event_data(path: str, envelope: Any) -> dict[str, Any]:
    """Compact event data: kind plus the fields automations need.

    "groceries.onCreated" → kind "groceries.created" with the item names;
    calendar events carry date, slot and title of the item.
    """
    domain, _, name = path.partition(".")
    event = name[2:] if name.startswith("on") else name
    snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in event).lstrip("_")
    data: dict[str, Any] = {"kind": f"{domain}.{snake}"}
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    if not isinstance(payload, dict):
        return data

    if domain == "groceries":
        groceries = payload.get("groceries")
        if isinstance(groceries, list):
            data["names"] = [
                g.get("name") for g in groceries if isinstance(g, dict) and g.get("name")
            ]
    elif domain == "calendar":
        item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
        for key in ("date", "slot"):
            if item.get(key):
                data[key] = item[key]
        title = item.get("recipeName") or item.get("title")
        if title:
            data["title"] = title
    return data
