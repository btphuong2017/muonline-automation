"""Capability test result types and matrix output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


class RV(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    SKIP = "SKIP"
    NOT_TESTED = "—"


@dataclass
class CapabilityResult:
    test_id: int
    name: str
    foreground: RV = RV.NOT_TESTED
    background: RV = RV.NOT_TESTED
    minimized: RV = RV.NOT_TESTED
    recommended: str = "—"
    notes: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "foreground": self.foreground.value,
            "background": self.background.value,
            "minimized": self.minimized.value,
            "recommended": self.recommended,
            "notes": self.notes,
            "evidence": self.evidence,
        }


def save_matrix_json(results: list[CapabilityResult], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_matrix_md(results: list[CapabilityResult], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Capability Matrix\n",
        "| # | Capability | Foreground | Background | Minimized | Recommended | Notes |",
        "|---|------------|-----------|-----------|-----------|-------------|-------|",
    ]
    for r in results:
        lines.append(
            f"| {r.test_id} | {r.name} | {r.foreground.value} "
            f"| {r.background.value} | {r.minimized.value} "
            f"| {r.recommended} | {r.notes} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide_recommended(r: CapabilityResult) -> str:
    """Derive a recommended execution mode from test results."""
    if r.background == RV.PASS:
        return "background"
    if r.background == RV.PARTIAL:
        return "hybrid"
    if r.foreground == RV.PASS:
        return "foreground"
    return "foreground"  # safest default
