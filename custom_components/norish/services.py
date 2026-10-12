"""Actions (services) of the Norish integration."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import NorishCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_ADD_RECIPE_TO_GROCERIES = "add_recipe_to_groceries"

SLOTS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snack": "Snack"}

ADD_RECIPE_SCHEMA = vol.Schema(
    {
        vol.Optional("recipe_id"): cv.string,
        vol.Optional("date"): cv.date,
        vol.Optional("slot"): vol.In(list(SLOTS)),
        vol.Optional("days"): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
    }
)


def _coordinators(hass: HomeAssistant) -> list[NorishCoordinator]:
    return list(hass.data.get(DOMAIN, {}).values())


def _planned_recipe_ids(
    coordinator: NorishCoordinator, start: date, days: int, slot: str | None
) -> list[str]:
    """Recipe IDs planned in the calendar from start for days (optionally one slot)."""
    wanted = {(start + timedelta(days=offset)).isoformat() for offset in range(days)}
    ids: list[str] = []
    for item in (coordinator.data or {}).get("calendar", []):
        if item.get("date") not in wanted or not item.get("recipeId"):
            continue
        if slot and str(item.get("slot") or "").lower() != slot:
            continue
        if item["recipeId"] not in ids:
            ids.append(item["recipeId"])
    return ids


async def _add_recipe_to_groceries(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    coordinators = _coordinators(hass)
    if not coordinators:
        raise ServiceValidationError("Norish is not set up")
    coordinator = coordinators[0]

    if recipe_id := call.data.get("recipe_id"):
        recipe_ids = [recipe_id]
    else:
        start: date = call.data.get("date") or dt_util.now().date()
        recipe_ids = _planned_recipe_ids(
            coordinator, start, call.data.get("days", 1), call.data.get("slot")
        )
        if not recipe_ids:
            raise ServiceValidationError("No recipe planned for that day/slot")

    added = 0
    names: list[str] = []
    for rid in recipe_ids:
        count, name = await coordinator.async_add_recipe_ingredients(rid)
        added += count
        if name:
            names.append(name)
    if not added:
        raise HomeAssistantError("Could not add the ingredients to Norish")
    return {"added": added, "recipes": names}


def async_register_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_RECIPE_TO_GROCERIES):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_RECIPE_TO_GROCERIES,
        _add_recipe_to_groceries,
        schema=ADD_RECIPE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the actions when the last Norish entry is unloaded."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_ADD_RECIPE_TO_GROCERIES)


def ingredients_for_groceries(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    """Grocery create payload for a recipe's ingredients (its own measurement system)."""
    system = recipe.get("systemUsed") or "metric"
    rows = sorted(
        (
            i for i in recipe.get("recipeIngredients") or []
            if isinstance(i, dict)
            and (i.get("systemUsed") or "metric") == system
            and (i.get("ingredientName") or "").strip()
            and not str(i.get("ingredientName")).strip().startswith("#")
        ),
        key=lambda i: float(i.get("order") or 0),
    )
    return [
        {
            "name": row["ingredientName"].strip(),
            "unit": row.get("unit") or None,
            "amount": row.get("amount"),
            "isDone": False,
            # Links the grocery to the recipe, so Norish merges repeats
            "recipeIngredientId": row.get("id"),
            "storeId": None,
        }
        for row in rows
    ]
