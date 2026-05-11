"""Load and access template configuration from templates.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class TemplateEntry:
    key: str
    path: Path
    roi: Optional[tuple[int, int, int, int]] = None  # x, y, w, h in client coords
    threshold: float = 0.85


class TemplatesConfigError(Exception):
    pass


def load_templates(
    path: Path = Path("config/templates.yaml"),
) -> dict[str, TemplateEntry]:
    """Return all template entries keyed by name, or empty dict if file missing."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TemplatesConfigError(f"Invalid templates.yaml: {exc}") from exc
    if not data or "templates" not in data:
        return {}
    result: dict[str, TemplateEntry] = {}
    for key, entry in (data.get("templates") or {}).items():
        if not isinstance(entry, dict):
            continue
        roi_raw = entry.get("roi")
        roi: Optional[tuple[int, int, int, int]] = (
            tuple(int(v) for v in roi_raw) if roi_raw else None  # type: ignore[assignment]
        )
        result[key] = TemplateEntry(
            key=key,
            path=Path(str(entry.get("path", ""))),
            roi=roi,
            threshold=float(entry.get("threshold", 0.85)),
        )
    return result
