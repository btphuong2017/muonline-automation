"""Unit tests for config_.characters loader and saver."""

import textwrap
from pathlib import Path
import pytest

from varka_auto.config_.characters import (
    CharacterConfig,
    CharactersConfigError,
    load_characters,
    save_characters,
)


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "characters.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_load_basic(tmp_path):
    p = _write_yaml(tmp_path, """
        characters:
          - display_name: Char1
            enabled: true
          - display_name: Char2
            enabled: false
    """)
    chars = load_characters(p)
    assert len(chars) == 2
    assert chars[0].display_name == "Char1"
    assert chars[0].enabled is True
    assert chars[1].display_name == "Char2"
    assert chars[1].enabled is False


def test_load_enabled_defaults_true(tmp_path):
    p = _write_yaml(tmp_path, """
        characters:
          - display_name: OnlyName
    """)
    chars = load_characters(p)
    assert chars[0].enabled is True


def test_missing_file_raises(tmp_path):
    with pytest.raises(CharactersConfigError, match="not found"):
        load_characters(tmp_path / "missing.yaml")


def test_missing_display_name_raises(tmp_path):
    p = _write_yaml(tmp_path, """
        characters:
          - enabled: true
    """)
    with pytest.raises(CharactersConfigError, match="display_name"):
        load_characters(p)


def test_no_characters_key_raises(tmp_path):
    p = _write_yaml(tmp_path, "foo: bar\n")
    with pytest.raises(CharactersConfigError, match="characters"):
        load_characters(p)


# ---------------------------------------------------------------------------
# save_characters
# ---------------------------------------------------------------------------

def test_save_characters_roundtrip(tmp_path):
    chars = [
        CharacterConfig(display_name="PPGL", enabled=True, max_runs=5),
        CharacterConfig(display_name="PPDK", enabled=False, max_runs=10),
    ]
    p = tmp_path / "characters.yaml"
    save_characters(p, chars)
    loaded = load_characters(p)
    assert len(loaded) == 2
    assert loaded[0].display_name == "PPGL"
    assert loaded[0].enabled is True
    assert loaded[0].max_runs == 5
    assert loaded[1].display_name == "PPDK"
    assert loaded[1].enabled is False
    assert loaded[1].max_runs == 10


def test_save_characters_omits_none_level(tmp_path):
    chars = [CharacterConfig(display_name="A", level=None)]
    p = tmp_path / "characters.yaml"
    save_characters(p, chars)
    content = p.read_text(encoding="utf-8")
    assert "level" not in content


def test_save_characters_includes_level_when_set(tmp_path):
    chars = [CharacterConfig(display_name="A", level=400)]
    p = tmp_path / "characters.yaml"
    save_characters(p, chars)
    loaded = load_characters(p)
    assert loaded[0].level == 400


def test_save_characters_creates_parent_dir(tmp_path):
    p = tmp_path / "nested" / "deep" / "characters.yaml"
    save_characters(p, [CharacterConfig(display_name="X")])
    assert p.exists()
    loaded = load_characters(p)
    assert loaded[0].display_name == "X"
