"""Unit tests for vision.template_match — decode/glob caching behaviour.

Uses real files on disk (tmp_path) since the caching is keyed on path + mtime,
which only means something against a real filesystem.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from varka_auto.vision import template_match as tm


@pytest.fixture(autouse=True)
def _clear_cache():
    """Every test starts and ends with an empty cache — caches are module-level
    globals, so state must not leak between tests."""
    tm.clear_cache()
    yield
    tm.clear_cache()


def _write_png(path: Path, fill: int = 100, size: int = 8) -> None:
    img = np.full((size, size, 3), fill, dtype=np.uint8)
    cv2.imwrite(str(path), img)


def test_load_template_reads_disk_once_for_same_mtime(tmp_path, monkeypatch):
    p = tmp_path / "tpl.png"
    _write_png(p)

    calls = {"n": 0}
    real_imread = cv2.imread

    def _counting_imread(path):
        calls["n"] += 1
        return real_imread(path)

    monkeypatch.setattr(cv2, "imread", _counting_imread)

    first = tm._load_template(p)
    second = tm._load_template(p)

    assert calls["n"] == 1
    assert first is second  # same cached ndarray object, not just equal


def test_load_template_rereads_after_mtime_change(tmp_path, monkeypatch):
    p = tmp_path / "tpl.png"
    _write_png(p, fill=100)

    calls = {"n": 0}
    real_imread = cv2.imread

    def _counting_imread(path):
        calls["n"] += 1
        return real_imread(path)

    monkeypatch.setattr(cv2, "imread", _counting_imread)

    tm._load_template(p)
    assert calls["n"] == 1

    # Force a distinct mtime — some filesystems have 1s+ mtime resolution.
    new_time = p.stat().st_mtime + 5
    _write_png(p, fill=200)
    import os
    os.utime(p, (new_time, new_time))

    tm._load_template(p)
    assert calls["n"] == 2


def test_load_template_missing_file_returns_none():
    assert tm._load_template(Path("does/not/exist.png")) is None


def test_siblings_globs_once(tmp_path, monkeypatch):
    base = tmp_path / "hover_indicator.png"
    _write_png(base)
    _write_png(tmp_path / "hover_indicator_A.png")
    _write_png(tmp_path / "hover_indicator_B.png")

    calls = {"n": 0}
    real_glob = Path.glob

    def _counting_glob(self, pattern):
        calls["n"] += 1
        return real_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _counting_glob)

    first = tm._siblings(base)
    second = tm._siblings(base)

    assert calls["n"] == 1
    assert first == second
    assert len(first) == 2


def test_clear_cache_forces_reread(tmp_path, monkeypatch):
    p = tmp_path / "tpl.png"
    _write_png(p)

    calls = {"n": 0}
    real_imread = cv2.imread

    def _counting_imread(path):
        calls["n"] += 1
        return real_imread(path)

    monkeypatch.setattr(cv2, "imread", _counting_imread)

    tm._load_template(p)
    tm.clear_cache()
    tm._load_template(p)

    assert calls["n"] == 2


def test_match_template_still_matches_correctly_with_cache(tmp_path):
    """End-to-end sanity: caching must not change match results."""
    tpl_path = tmp_path / "target.png"
    _write_png(tpl_path, fill=200, size=4)

    frame = np.full((20, 20, 3), 50, dtype=np.uint8)
    frame[10:14, 10:14] = 200  # plant the template inside the frame

    matched1, conf1, loc1 = tm.match_template(frame, tpl_path, threshold=0.9)
    matched2, conf2, loc2 = tm.match_template(frame, tpl_path, threshold=0.9)

    assert matched1 is True
    assert matched1 == matched2
    assert conf1 == pytest.approx(conf2)
    assert loc1 == loc2


def test_match_template_missing_file_returns_false():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    matched, conf, loc = tm.match_template(frame, Path("nope.png"))
    assert matched is False
    assert conf == 0.0
    assert loc == (0, 0)
