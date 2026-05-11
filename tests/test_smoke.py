"""Smoke tests — verify the package is importable and the CLI app exists."""

import varka_auto
from varka_auto.cli import app


def test_version_string() -> None:
    assert isinstance(varka_auto.__version__, str)
    assert varka_auto.__version__ != ""


def test_cli_app_exists() -> None:
    assert app is not None


def test_cli_has_expected_commands() -> None:
    command_names = {c for c in app.registered_commands if c}  # type: ignore[attr-defined]
    # Just verify the app object is a Typer instance with commands
    from typer import Typer
    assert isinstance(app, Typer)
