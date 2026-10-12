"""Todo platform for Norish shopping list.

Creates one TodoListEntity per store (+ one for unsorted items).
Check/uncheck and delete are synced back to the Norish API in real time.
"""
from __future__ import annotations

import logging
import re

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NorishCoordinator
from .entity import norish_device_info

_LOGGER = logging.getLogger(__name__)

_UNSORTED_NAME = "Unsorted"


def _slugify(name: str) -> str:
    """Turn a store name into a safe entity-id component."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Norish todo lists — one per store + one for unsorted items."""
    coordinator: NorishCoordinator = hass.data[DOMAIN][entry.entry_id]

    _migrate_unique_ids(hass, entry, coordinator)

    # Build the initial set of entities from coordinator data
    entities = _build_entities(coordinator, entry)
    async_add_entities(entities)

    # When coordinator data updates (new stores added), add new entities
    known_store_ids: set[str | None] = {e.store_id for e in entities}

    def _on_coordinator_update() -> None:
        """Add new store entities discovered after initial setup."""
        _migrate_unique_ids(hass, entry, coordinator)
        new_entities = [
            e
            for e in _build_entities(coordinator, entry)
            if e.store_id not in known_store_ids
        ]
        if new_entities:
            for e in new_entities:
                known_store_ids.add(e.store_id)
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.async_add_listener(_on_coordinator_update)
    )


@callback
def _migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: NorishCoordinator
) -> None:
    """Move store lists from name-based to store-ID-based unique IDs.

    The unique ID used to contain the store name, so renaming a store in
    Norish created a new entity. The entity ID (and dashboards) are kept.
    """
    stores: dict[str, str] = (coordinator.data or {}).get("stores", {})
    registry = er.async_get(hass)
    for store_id, store_name in stores.items():
        old = f"{entry.entry_id}_shopping_{_slugify(store_name)}"
        new = f"{entry.entry_id}_shopping_{store_id}"
        entity_id = registry.async_get_entity_id("todo", DOMAIN, old)
        if entity_id and not registry.async_get_entity_id("todo", DOMAIN, new):
            registry.async_update_entity(entity_id, new_unique_id=new)


def _build_entities(
    coordinator: NorishCoordinator,
    entry: ConfigEntry,
) -> list[NorishStoreList]:
    """Build one entity per store from current coordinator data."""
    stores: dict[str, str] = coordinator.data.get("stores", {}) if coordinator.data else {}

    entities: list[NorishStoreList] = []

    # Always include the "Unsorted" list (items with storeId = None)
    entities.append(NorishStoreList(coordinator, entry, store_id=None, store_name=_UNSORTED_NAME))

    # One entity per known store
    for store_id, store_name in stores.items():
        entities.append(NorishStoreList(coordinator, entry, store_id=store_id, store_name=store_name))

    return entities


def _parse_summary(summary: str) -> tuple[str, float | None]:
    """Split a leading amount off an item: "2 milk" / "1,5x flour" → (name, amount)."""
    text = summary.strip()
    match = re.match(r"^(\d+(?:[.,]\d+)?)\s*[x×]?\s+(\S.*)$", text)
    if not match:
        return text, None
    return match.group(2).strip(), float(match.group(1).replace(",", "."))


def _grocery_to_todo_item(grocery: dict) -> TodoItem:
    """Convert a Norish grocery dict to a HA TodoItem."""
    item_id: str = grocery.get("id", "")
    name: str = grocery.get("name") or grocery.get("ingredient") or "Unknown"
    is_done: bool = (
        grocery.get("isDone", False)
        or grocery.get("checked", False)
        or grocery.get("completed", False)
    )
    amount = grocery.get("amount")
    unit: str = grocery.get("unit", "")

    if amount and unit:
        summary = f"{amount}{unit} {name}"
    elif amount:
        summary = f"{amount}× {name}"
    else:
        summary = name

    return TodoItem(
        uid=item_id,
        summary=summary,
        status=TodoItemStatus.COMPLETED if is_done else TodoItemStatus.NEEDS_ACTION,
    )


class NorishStoreList(CoordinatorEntity, TodoListEntity):
    """One Norish shopping list per store.

    store_id=None  → "Unsorted" (items with no store assigned)
    store_id=<id>  → items assigned to that store
    """

    def __init__(
        self,
        coordinator: NorishCoordinator,
        entry: ConfigEntry,
        store_id: str | None,
        store_name: str,
    ) -> None:
        """Initialize the store list entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = norish_device_info(entry, coordinator.base_url)
        self.store_id = store_id
        self._store_name = store_name

        if store_id is None:
            self._attr_name = f"Norish {store_name}"
            self._attr_unique_id = f"{entry.entry_id}_shopping_unsorted"
        else:
            self._attr_name = f"Norish {store_name}"
            # Store ID, not name: renaming a store keeps the same entity
            self._attr_unique_id = f"{entry.entry_id}_shopping_{store_id}"

        self._attr_supported_features = (
            TodoListEntityFeature.CREATE_TODO_ITEM
            | TodoListEntityFeature.UPDATE_TODO_ITEM
            | TodoListEntityFeature.DELETE_TODO_ITEM
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return items for this store (or unsorted items if store_id is None)."""
        if not self.coordinator.data:
            return []

        groceries: list[dict] = self.coordinator.data.get("groceries", [])

        if self.store_id is None:
            # Unsorted: items with no store assigned
            filtered = [g for g in groceries if not g.get("storeId")]
        else:
            filtered = [g for g in groceries if g.get("storeId") == self.store_id]

        return [_grocery_to_todo_item(g) for g in filtered]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Toggle item done/undone — syncs back to Norish immediately."""
        if not item.uid:
            return
        is_done = item.status == TodoItemStatus.COMPLETED
        _LOGGER.debug("Norish: toggle %s → isDone=%s", item.uid, is_done)
        if not await self.coordinator.async_toggle_grocery(item.uid, is_done):
            raise HomeAssistantError("Could not update the item in Norish")

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items — syncs back to Norish immediately."""
        _LOGGER.debug("Norish: delete items %s", uids)
        if not await self.coordinator.async_delete_groceries(list(uids)):
            raise HomeAssistantError("Could not delete the items in Norish")

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to this store's list in Norish ("2 milk" → 2 × milk)."""
        name, amount = _parse_summary(item.summary or "")
        if not name:
            raise HomeAssistantError("Item name is empty")
        if not await self.coordinator.async_create_grocery(name, amount, self.store_id):
            raise HomeAssistantError("Could not add the item to Norish")
