"""Recovery / triage checklist (Commit 27 Part 1.5, spec sections 7-8, 27).

不能"看起来好了"就恢复交易，必须:

    Checklist
        ↓
    全部通过
        ↓
    Recovery
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ChecklistItem:

    item_id: str

    description: str

    required: bool = True

    completed: bool = False


class Checklist:

    def __init__(
        self,
        items: tuple[ChecklistItem, ...] | list[ChecklistItem],
    ):

        self._items = {
            item.item_id: item
            for item in items
        }

    def complete(
        self,
        item_id: str,
    ) -> ChecklistItem:

        item = self._items[item_id]

        updated = replace(
            item,
            completed=True,
        )

        self._items[item_id] = updated

        return updated

    def get(self, item_id: str) -> ChecklistItem | None:

        return self._items.get(item_id)

    def is_completed(self, item_id: str) -> bool:

        item = self._items.get(item_id)

        return item.completed if item else False

    def all_required_completed(self) -> bool:

        return all(
            item.completed
            for item in self._items.values()
            if item.required
        )

    @property
    def items(self) -> tuple[ChecklistItem, ...]:

        return tuple(
            self._items.values()
        )

    @property
    def completed_items(self) -> tuple[ChecklistItem, ...]:

        return tuple(
            item
            for item in self._items.values()
            if item.completed
        )

    @property
    def pending_items(self) -> tuple[ChecklistItem, ...]:

        return tuple(
            item
            for item in self._items.values()
            if not item.completed
        )
