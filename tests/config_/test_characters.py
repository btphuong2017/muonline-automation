"""Unit tests for config_.characters loader and saver."""

import textwrap
from pathlib import Path
import pytest

from varka_auto.config_.characters import (
    CharacterConfig,
    CharactersConfigError,
    load_characters,
    merge_detected_characters,
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


# ---------------------------------------------------------------------------
# merge_detected_characters
# ---------------------------------------------------------------------------

def test_merge_force_updates_disabled_and_wrong_max_runs():
    existing = [CharacterConfig(display_name="A", enabled=False, max_runs=5)]
    merged, actions = merge_detected_characters(existing, ["A"], max_runs=10, force=True)

    assert merged == [CharacterConfig(display_name="A", enabled=True, max_runs=10)]
    assert len(actions) == 1
    assert actions[0].tag == "UPDATED"
    assert actions[0].display_name == "A"
    assert "enabled false->true" in actions[0].note
    assert "max_runs 5->10" in actions[0].note


def test_merge_force_already_correct_is_kept_not_updated():
    existing = [CharacterConfig(display_name="A", enabled=True, max_runs=10)]
    merged, actions = merge_detected_characters(existing, ["A"], max_runs=10, force=True)

    assert merged == [CharacterConfig(display_name="A", enabled=True, max_runs=10)]
    assert actions[0].tag == "KEPT"


def test_merge_no_force_preserves_existing_settings():
    existing = [CharacterConfig(display_name="A", enabled=False, max_runs=5)]
    merged, actions = merge_detected_characters(existing, ["A"], max_runs=10, force=False)

    assert merged == [CharacterConfig(display_name="A", enabled=False, max_runs=5)]
    assert actions[0].tag == "KEPT"


def test_merge_adds_new_character():
    merged, actions = merge_detected_characters([], ["NewChar"], max_runs=10, force=True)

    assert merged == [CharacterConfig(display_name="NewChar", enabled=True, max_runs=10)]
    assert actions[0].tag == "ADDED"


def test_merge_removes_character_with_no_window():
    existing = [CharacterConfig(display_name="Gone", enabled=True, max_runs=10)]
    merged, actions = merge_detected_characters(existing, [], max_runs=10, force=True)

    assert merged == []
    assert len(actions) == 1
    assert actions[0].tag == "REMOVED"
    assert actions[0].display_name == "Gone"


def test_merge_force_preserves_level():
    existing = [CharacterConfig(display_name="A", enabled=False, max_runs=5, level=400)]
    merged, actions = merge_detected_characters(existing, ["A"], max_runs=10, force=True)

    assert merged[0].level == 400


def test_merge_output_order_matches_detected_names():
    existing = [CharacterConfig(display_name="B", enabled=True, max_runs=10)]
    merged, actions = merge_detected_characters(
        existing, ["C", "B", "A"], max_runs=10, force=True
    )

    assert [c.display_name for c in merged] == ["C", "B", "A"]
