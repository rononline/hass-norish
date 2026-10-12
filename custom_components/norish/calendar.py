"""Calendar platform for Norish."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import NorishCoordinator
from .entity import norish_device_info

_LOGGER = logging.getLogger(__name__)

# Keep in sync with MEAL_SLOT_TIMES in sensor.py
SLOT_TIMES: dict[str, tuple[int, int]] = {
    "Breakfast": (8, 0),
    "Lunch": (12, 0),
    "Dinner": (18, 0),
    "Snack": (15, 0),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Norish calendar."""
    coordinator: NorishCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NorishCalendar(coordinator, entry)])


class NorishCalendar(CoordinatorEntity, CalendarEntity):
    """Norish Meal Calendar entity."""

    def __init__(
        self,
        coordinator: NorishCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = norish_device_info(entry, coordinator.base_url)
        self._attr_name = "Norish Meal Calendar"
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        now = dt_util.now()
        events = self._get_events_for_range(now, now + timedelta(days=1))
        return next((e for e in events if e.end > now), None)

    async def async_create_event(self, **kwargs: Any) -> None:
        """Plan a meal in Norish: a recipe when the title matches one exactly,
        otherwise a note ("Eating out"). The slot comes from a "Dinner: …"
        prefix, else from the start time (date-only events become dinner)."""
        summary = str(kwargs.get("summary") or "").strip()
        start = kwargs.get("dtstart")
        slot, title = _split_slot(summary)
        if slot is None:
            slot = _slot_for_time(start) if isinstance(start, datetime) else "Dinner"
        if not title:
            raise HomeAssistantError("A meal needs a title")
        day = start.date() if isinstance(start, datetime) else start
        if not isinstance(day, date):
            raise HomeAssistantError("A meal needs a date")
        if not await self.coordinator.async_create_calendar_item(day, slot, title):
            raise HomeAssistantError("Could not plan the meal in Norish")

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Remove a planned meal or note from Norish."""
        if not await self.coordinator.async_delete_calendar_item(uid):
            raise HomeAssistantError("Could not remove the meal from Norish")

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self._get_events_for_range(start_date, end_date)

    def _get_events_for_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get events for a date range, returning timezone-aware CalendarEvents."""
        events: list[CalendarEvent] = []

        if not self.coordinator.data:
            return events

        # Use HA's local timezone for all datetime operations
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)

        calendar_data: list[dict] = self.coordinator.data.get("calendar", [])

        # Normalise boundaries to dates for comparison
        start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
        end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

        for item in calendar_data:
            try:
                event_date_str: str = item.get("date", "")
                if not event_date_str:
                    continue

                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()

                if not (start_date_only <= event_date <= end_date_only):
                    continue

                # Resolve display name
                # itemType "note" items carry the text in "title"; "recipe" items use recipeName
                item_type: str = item.get("itemType") or "recipe"
                note_title: str = item.get("title") or ""
                recipe_details: dict = item.get("_recipe") or {}
                recipe_name: str = (
                    recipe_details.get("name")
                    or item.get("recipeName")
                    or ""
                )

                slot_raw = item.get("slot") or item.get("type") or "Meal"
                # API may send "DINNER" or "Dinner" – normalise to "Dinner"
                slot: str = slot_raw.capitalize() if isinstance(slot_raw, str) else "Meal"
                hour, minute = SLOT_TIMES.get(slot, (12, 0))

                # Summary: use recipe name for recipes, note title for notes
                if item_type == "note" and note_title:
                    summary = f"{slot}: {note_title}"
                elif recipe_name:
                    summary = f"{slot}: {recipe_name}"
                else:
                    summary = f"{slot}: Meal"

                # Description: include note title when present
                description = f"Norish – {slot}"
                if item_type == "note" and note_title:
                    description = f"Norish – {slot} (note): {note_title}"

                # Build timezone-aware start/end datetimes
                start_dt = datetime(
                    event_date.year,
                    event_date.month,
                    event_date.day,
                    hour,
                    minute,
                    0,
                    tzinfo=local_tz,
                )
                end_dt = start_dt + timedelta(hours=1)

                # Only return events that overlap the requested time window
                if not (start_dt < end_date and end_dt > start_date):
                    continue

                events.append(
                    CalendarEvent(
                        start=start_dt,
                        end=end_dt,
                        summary=summary,
                        description=description,
                        uid=item.get("id"),
                    )
                )

            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed to parse calendar event: %s", err)
                continue

        return sorted(events, key=lambda x: x.start)


# "Diner: Pasta" / "Dinner - Pasta" → ("Dinner", "Pasta"), in NL/EN/DE
_SLOT_WORDS = {
    "breakfast": "Breakfast", "ontbijt": "Breakfast", "frühstück": "Breakfast",
    "lunch": "Lunch", "mittagessen": "Lunch",
    "dinner": "Dinner", "diner": "Dinner", "avondeten": "Dinner", "abendessen": "Dinner",
    "snack": "Snack", "tussendoortje": "Snack",
}


def _split_slot(summary: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*([^\W\d_]+)\s*[:\-–]\s*(.+)$", summary)
    if match and match.group(1).casefold() in _SLOT_WORDS:
        return _SLOT_WORDS[match.group(1).casefold()], match.group(2).strip()
    return None, summary


def _slot_for_time(start: datetime) -> str:
    hour = dt_util.as_local(start).hour if start.tzinfo else start.hour
    if hour < 11:
        return "Breakfast"
    if hour < 15:
        return "Lunch"
    if hour < 17:
        return "Snack"
    return "Dinner"
