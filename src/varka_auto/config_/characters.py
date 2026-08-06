"""Load and validate config/characters.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


@dataclass
class CharacterConfig:
    display_name: str
    enabled: bool = True
    level: int | None = None
    max_runs: int = 10


class CharactersConfigError(ValueError):
    pass


def load_characters(path: Path) -> list[CharacterConfig]:
    """Load characters.yaml and return a list of CharacterConfig.

    Raises CharactersConfigError on missing file or bad schema.
    """
    if not path.exists():
        raise CharactersConfigError(
            f"Characters config not found: {path}\n"
            f"Copy config/characters.yaml.example to {path} and fill in your display names."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "characters" not in raw or not isinstance(raw["characters"], list):
        raise CharactersConfigError(
            f"{path}: expected a 'characters' list at the top level."
        )

    result: list[CharacterConfig] = []
    for i, entry in enumerate(raw["characters"]):
        if not isinstance(entry, dict) or "display_name" not in entry:
            raise CharactersConfigError(
                f"{path}: entry #{i} missing 'display_name'."
            )
        result.append(
            CharacterConfig(
                display_name=str(entry["display_name"]),
                enabled=bool(entry.get("enabled", True)),
                level=entry.get("level"),
                max_runs=int(entry.get("max_runs", 10)),
            )
        )

    return result


def save_characters(path: Path, chars: list[CharacterConfig]) -> None:
    """Write a list of CharacterConfig to a YAML file, creating parent dirs if needed."""
    entries = []
    for c in chars:
        entry: dict = {
            "display_name": c.display_name,
            "enabled": c.enabled,
            "max_runs": c.max_runs,
        }
        if c.level is not None:
            entry["level"] = c.level
        entries.append(entry)

    data = {"characters": entries}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


@dataclass
class SyncAction:
    tag: str  # "ADDED" | "UPDATED" | "KEPT" | "REMOVED"
    display_name: str
    note: str


def merge_detected_characters(
    existing: list[CharacterConfig],
    detected_names: list[str],
    max_runs: int = 10,
    force: bool = False,
) -> tuple[list[CharacterConfig], list[SyncAction]]:
    """Merge freshly-detected game-window names into an existing character list.

    - A detected name with no existing entry is ADDED with enabled=True,
      max_runs=max_runs.
    - A detected name that already has an entry is either KEPT as-is
      (force=False — settings are the user's to manage) or, with force=True,
      UPDATED so enabled=True and max_runs=max_runs (existing `level` is left
      untouched either way; it isn't part of what force is meant to enforce).
      If forcing wouldn't actually change anything, the action is KEPT rather
      than a no-op UPDATED.
    - An existing entry with no matching detected name is REMOVED — dropped
      from the returned list entirely.

    Returns (merged, actions) with merged in the same order as detected_names.
    Pure function — no I/O, no Win32 — so it's fully unit-testable.
    """
    by_name = {c.display_name: c for c in existing}
    detected_set = set(detected_names)

    merged: list[CharacterConfig] = []
    actions: list[SyncAction] = []

    for name in detected_names:
        current = by_name.get(name)
        if current is None:
            merged.append(CharacterConfig(display_name=name, enabled=True, max_runs=max_runs))
            actions.append(SyncAction("ADDED", name, f"added with max_runs={max_runs}"))
            continue

        if not force:
            merged.append(current)
            actions.append(SyncAction("KEPT", name, "settings preserved"))
            continue

        changes = []
        if not current.enabled:
            changes.append("enabled false->true")
        if current.max_runs != max_runs:
            changes.append(f"max_runs {current.max_runs}->{max_runs}")

        if not changes:
            merged.append(current)
            actions.append(SyncAction("KEPT", name, "already enabled=true, max_runs matches"))
        else:
            merged.append(CharacterConfig(
                display_name=name, enabled=True, level=current.level, max_runs=max_runs,
            ))
            actions.append(SyncAction("UPDATED", name, ", ".join(changes)))

    for name, current in by_name.items():
        if name not in detected_set:
            actions.append(SyncAction("REMOVED", name, "window not found — removed from config"))

    return merged, actions
