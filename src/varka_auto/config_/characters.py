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
