"""Logging layer — per-character file loggers, session summary, screenshot-on-error."""

from __future__ import annotations

import logging
import time
from pathlib import Path


def get_character_logger(char_name: str, session_id: str | None = None) -> logging.Logger:
    """Return a file logger scoped to a single character."""
    sid = session_id or time.strftime("%Y%m%d-%H%M%S")
    log_dir = Path("logs") / char_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{sid}.log"

    logger = logging.getLogger(f"varka.{char_name}")
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger


def save_error_screenshot(char_name: str, frame: object, label: str = "error") -> Path | None:
    """Save a numpy frame as PNG into logs/<char>/screenshots/. Returns path or None."""
    try:
        import cv2
        import numpy as np

        assert isinstance(frame, np.ndarray)
        ts = time.strftime("%Y%m%d-%H%M%S")
        out = Path("logs") / char_name / "screenshots" / f"{ts}_{label}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), frame)
        return out
    except Exception:
        return None
