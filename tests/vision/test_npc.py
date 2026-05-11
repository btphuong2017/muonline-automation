"""Unit tests for vision.npc — no game window required."""

import sys
import numpy as np
import pytest

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.npc import Candidate, NpcFinder, _CACHE
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeCapture:
    def __init__(self, frame: np.ndarray | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((600, 800, 3), dtype=np.uint8)

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        return self._frame[y : y + h, x : x + w].copy()

    def name(self):
        return "fake"


@pytest.fixture(autouse=True)
def patch_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")


@pytest.fixture(autouse=True)
def reset_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


# ---------------------------------------------------------------------------
# get_candidates — grid fallback
# ---------------------------------------------------------------------------

def test_get_candidates_no_templates_returns_grid():
    finder = NpcFinder(_FakeCapture(), templates={}, grid_step=200)
    candidates = finder.get_candidates(1)
    assert len(candidates) > 0
    assert all(c.source == "grid" for c in candidates)


def test_get_candidates_grid_covers_search_region():
    finder = NpcFinder(
        _FakeCapture(),
        templates={},
        top_frac=0.0,
        left_frac=0.0,
        width_frac=1.0,
        height_frac=1.0,
        grid_step=100,
    )
    candidates = finder.get_candidates(1)
    xs = [c.x for c in candidates]
    ys = [c.y for c in candidates]
    assert min(xs) == 0
    assert min(ys) == 0


# ---------------------------------------------------------------------------
# get_candidates — cache priority
# ---------------------------------------------------------------------------

def test_get_candidates_returns_cache_first():
    cached = Candidate(x=300, y=200, confidence=0.9, source="cache", success_count=3)
    _CACHE[42] = [cached]
    finder = NpcFinder(_FakeCapture(), templates={}, grid_step=200)
    candidates = finder.get_candidates(42)
    assert candidates[0] is cached


def test_get_candidates_cache_sorted_by_success_count():
    c_low = Candidate(x=100, y=100, confidence=0.8, source="cache", success_count=1)
    c_high = Candidate(x=200, y=200, confidence=0.8, source="cache", success_count=5)
    _CACHE[7] = [c_low, c_high]
    finder = NpcFinder(_FakeCapture(), templates={}, grid_step=200)
    candidates = finder.get_candidates(7)
    # high success_count should come first
    assert candidates[0] is c_high
    assert candidates[1] is c_low


# ---------------------------------------------------------------------------
# record_success / record_failure
# ---------------------------------------------------------------------------

def test_record_success_increments_and_caches():
    finder = NpcFinder(_FakeCapture(), templates={})
    c = Candidate(x=10, y=20, confidence=0.5, source="grid")
    finder.record_success(99, c)
    assert c.success_count == 1
    assert c in _CACHE[99]


def test_record_success_twice_increments_only_once_in_cache():
    finder = NpcFinder(_FakeCapture(), templates={})
    c = Candidate(x=10, y=20, confidence=0.5, source="grid")
    finder.record_success(99, c)
    finder.record_success(99, c)
    assert c.success_count == 2
    assert _CACHE[99].count(c) == 1  # not duplicated


def test_record_failure_never_evicts_from_cache():
    finder = NpcFinder(_FakeCapture(), templates={})
    c = Candidate(x=10, y=20, confidence=0.5, source="cache", fail_count=2)
    _CACHE[88] = [c]
    finder.record_failure(88, c)
    # Cache positions are never removed — NPC may respawn here later.
    assert c in _CACHE[88]
    assert c.fail_count == 3


def test_record_failure_below_threshold_keeps_in_cache():
    finder = NpcFinder(_FakeCapture(), templates={})
    c = Candidate(x=10, y=20, confidence=0.5, source="cache", fail_count=0)
    _CACHE[88] = [c]
    finder.record_failure(88, c)
    assert c in _CACHE[88]  # only 1 failure, not evicted yet


# ---------------------------------------------------------------------------
# get_candidates — template matching path
# ---------------------------------------------------------------------------

def test_get_candidates_uses_template_when_match_found(monkeypatch, tmp_path):
    import cv2

    # Create a small real PNG so tpl_path.exists() passes and cv2.imread works
    tpl_path = tmp_path / "npc_partial_test.png"
    tpl_img = np.zeros((20, 15, 3), dtype=np.uint8)
    cv2.imwrite(str(tpl_path), tpl_img)

    monkeypatch.setattr(
        "varka_auto.vision.npc.match_template",
        lambda frame, path, threshold: (True, 0.91, (50, 60)),
    )

    entry = TemplateEntry(key="npc/npc_partial_body", path=tpl_path, threshold=0.85)
    finder = NpcFinder(_FakeCapture(), templates={"npc/npc_partial_body": entry})
    candidates = finder.get_candidates(1)

    template_cands = [c for c in candidates if c.source == "template"]
    grid_cands = [c for c in candidates if c.source == "grid"]

    assert len(template_cands) >= 1
    assert len(grid_cands) > 0  # grid always appended so post-respawn positions are found


def test_get_candidates_ignores_non_partial_npc_keys(monkeypatch):
    # Keys not starting with "npc/npc_partial_" must not be used for template search
    calls = []

    def fake_match(frame, path, threshold):
        calls.append(path)
        return False, 0.0, (0, 0)

    monkeypatch.setattr("varka_auto.vision.npc.match_template", fake_match)

    entry = TemplateEntry(key="npc/hover_indicator", path=Path("x.png"), threshold=0.85)
    finder = NpcFinder(_FakeCapture(), templates={"npc/hover_indicator": entry})
    finder.get_candidates(1)

    # match_template should not have been called for "npc/hover_indicator"
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------

def test_clear_cache_single_hwnd():
    _CACHE[1] = [Candidate(x=0, y=0, confidence=0, source="cache")]
    _CACHE[2] = [Candidate(x=0, y=0, confidence=0, source="cache")]
    NpcFinder.clear_cache(1)
    assert 1 not in _CACHE
    assert 2 in _CACHE


def test_clear_cache_all():
    _CACHE[1] = []
    _CACHE[2] = []
    NpcFinder.clear_cache()
    assert len(_CACHE) == 0
