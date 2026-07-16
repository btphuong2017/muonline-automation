"""Capture backends — grab pixel data from a game window."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np

_ROI = Tuple[int, int, int, int]  # x, y, w, h relative to client area


class CaptureBackend(ABC):
    """Abstract interface for window capture."""

    @abstractmethod
    def grab(self, hwnd: int, roi: _ROI) -> np.ndarray:
        """Return a BGR uint8 ndarray of shape (h, w, 3) for the given ROI.

        roi is (x, y, w, h) in client-area coordinates.
        Raises RuntimeError if capture fails (e.g. black frame, bad hwnd).
        """

    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name, used in logs."""


def _client_to_screen(hwnd: int, x: int, y: int) -> tuple[int, int]:
    """Convert client-area (x, y) to screen coordinates."""
    import win32gui
    return win32gui.ClientToScreen(hwnd, (x, y))


def _win32_error(backend: str, hwnd: int, exc: Exception) -> RuntimeError:
    """Normalise a raw Win32 failure (pywintypes.error) into RuntimeError.

    Callers throughout the codebase only handle RuntimeError from capture,
    so raw pywintypes errors (e.g. from a destroyed hwnd) must not escape.
    """
    import win32gui
    if not win32gui.IsWindow(hwnd):
        return RuntimeError(f"{backend}: window hwnd={hwnd} no longer exists.")
    return RuntimeError(f"{backend}: Win32 call failed for hwnd={hwnd}: {exc}")


class MssBackend(CaptureBackend):
    """Capture via mss (screen grab). Requires window visible and unobscured."""

    def name(self) -> str:
        return "mss"

    def grab(self, hwnd: int, roi: _ROI) -> np.ndarray:
        if sys.platform != "win32":
            raise RuntimeError("MssBackend requires Windows.")

        import mss

        x, y, w, h = roi
        try:
            sx, sy = _client_to_screen(hwnd, x, y)
        except RuntimeError:
            raise
        except Exception as exc:
            raise _win32_error("MssBackend", hwnd, exc) from exc
        mon = {"left": sx, "top": sy, "width": w, "height": h}

        with mss.mss() as sct:
            raw = sct.grab(mon)

        frame = np.array(raw)[:, :, :3]  # BGRA → BGR
        if _is_black(frame):
            raise RuntimeError(
                f"MssBackend: black frame for hwnd={hwnd}. "
                "Window may be minimised or obscured."
            )
        return frame


class PrintWindowBackend(CaptureBackend):
    """Capture via Win32 PrintWindow. Works on overlapped/background windows.

    May return a black frame for DirectX-rendered game clients.
    """

    def name(self) -> str:
        return "PrintWindow"

    def grab(self, hwnd: int, roi: _ROI) -> np.ndarray:
        if sys.platform != "win32":
            raise RuntimeError("PrintWindowBackend requires Windows.")

        import win32gui
        import win32ui
        import win32con

        # Get full client-area size
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
        except Exception as exc:
            raise _win32_error("PrintWindowBackend", hwnd, exc) from exc
        cw, ch = right - left, bottom - top
        if cw <= 0 or ch <= 0:
            raise RuntimeError(f"PrintWindowBackend: zero-size client area for hwnd={hwnd}.")

        # Render the window into a DC
        try:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
        except Exception as exc:
            raise _win32_error("PrintWindowBackend", hwnd, exc) from exc
        try:
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            mem_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, cw, ch)
            mem_dc.SelectObject(bitmap)

            # PW_RENDERFULLCONTENT (0x00000002) captures DirectX content on Win8+
            import ctypes
            ctypes.windll.user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 0x00000002)

            bmp_info = bitmap.GetInfo()
            bmp_data = bitmap.GetBitmapBits(True)
            full = np.frombuffer(bmp_data, dtype=np.uint8).reshape(
                (bmp_info["bmHeight"], bmp_info["bmWidth"], 4)
            )
            full_bgr = full[:, :, :3].copy()

            mem_dc.DeleteDC()
            win32gui.DeleteObject(bitmap.GetHandle())
            mfc_dc.DeleteDC()
        finally:
            win32gui.ReleaseDC(hwnd, hwnd_dc)

        if _is_black(full_bgr):
            raise RuntimeError(
                f"PrintWindowBackend: black frame for hwnd={hwnd}. "
                "Game may use unsupported DirectX mode."
            )

        x, y, w, h = roi
        cropped = full_bgr[y : y + h, x : x + w]
        if cropped.size == 0:
            raise RuntimeError(
                f"PrintWindowBackend: ROI {roi} out of bounds for "
                f"client size ({cw}x{ch})."
            )
        return cropped


def _is_black(frame: np.ndarray, threshold: int = 5) -> bool:
    """Return True if the frame is entirely or nearly black (mean < threshold)."""
    return bool(frame.mean() < threshold)
