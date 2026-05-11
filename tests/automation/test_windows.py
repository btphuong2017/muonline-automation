"""Unit tests for automation.windows — no live game window required."""

import re
import pytest
from varka_auto.automation.windows import GameWindowInfo, _DEFAULT_TITLE_RE


# ---------------------------------------------------------------------------
# Title regex tests
# ---------------------------------------------------------------------------

VALID_TITLE = (
    "Asteria MU - Powered by IGCN"
    " - Name: [PPMG]"
    " Level: [400]"
    " Master Level: [1350]"
    " Resets: [3]"
)


def test_regex_matches_valid_title():
    m = _DEFAULT_TITLE_RE.match(VALID_TITLE)
    assert m is not None
    assert m.group("name") == "PPMG"
    assert m.group("level") == "400"
    assert m.group("master") == "1350"
    assert m.group("resets") == "3"


def test_regex_rejects_unrelated_window():
    assert _DEFAULT_TITLE_RE.match("Notepad") is None
    assert _DEFAULT_TITLE_RE.match("") is None
    assert _DEFAULT_TITLE_RE.match("Asteria MU - Powered by IGCN") is None


def test_regex_matches_title_without_resets():
    """Clients with 0 resets may omit the Resets field entirely."""
    title = (
        "Asteria MU - Powered by IGCN"
        " - Name: [PPDW]"
        " Level: [51]"
        " Master Level: [1350]"
    )
    m = _DEFAULT_TITLE_RE.match(title)
    assert m is not None
    assert m.group("name") == "PPDW"
    assert m.group("resets") is None  # group present but not captured


def test_regex_name_with_spaces():
    title = (
        "Asteria MU - Powered by IGCN"
        " - Name: [Dark Wizard]"
        " Level: [200]"
        " Master Level: [0]"
        " Resets: [0]"
    )
    m = _DEFAULT_TITLE_RE.match(title)
    assert m is not None
    assert m.group("name") == "Dark Wizard"


# ---------------------------------------------------------------------------
# GameWindowInfo dataclass tests
# ---------------------------------------------------------------------------

def _make_window(**kwargs) -> GameWindowInfo:
    defaults = dict(
        hwnd=12345,
        pid=9999,
        title=VALID_TITLE,
        name="PPMG",
        level=400,
        master_level=1350,
        resets=3,
        rect=(0, 0, 1024, 768),
        visible=True,
        minimised=False,
    )
    defaults.update(kwargs)
    return GameWindowInfo(**defaults)


def test_gamewindowinfo_to_dict():
    w = _make_window()
    d = w.to_dict()
    assert d["hwnd"] == 12345
    assert d["name"] == "PPMG"
    assert d["rect"] == [0, 0, 1024, 768]
    assert d["visible"] is True
    assert d["minimised"] is False


def test_gamewindowinfo_minimised_flag():
    w = _make_window(minimised=True, visible=False)
    d = w.to_dict()
    assert d["minimised"] is True
    assert d["visible"] is False
