"""Windows platform layer for GUI automation using ctypes.

Adapted from CUE (Computer Use Enhancer) platform/windows.py.
Standalone implementation with no external dependencies beyond Pillow and ctypes.
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import time
from io import BytesIO
from typing import Any

from PIL import Image

# ─── ctypes constants ──────────────────────────────────────

_INPUT_KEYBOARD = 1
_INPUT_MOUSE = 0

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040
_MOUSEEVENTF_WHEEL = 0x0800
_MOUSEEVENTF_HWHEEL = 0x1000

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004

_CF_UNICODETEXT = 13

# GetSystemMetrics indices
_SM_CXSCREEN = 0
_SM_CYSCREEN = 1
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

_VK_CODE_MAP: dict[str, int] = {
    "return": 0x0D, "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "insert": 0x2D,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "super": 0x5B, "win": 0x5B,
    "printscreen": 0x2C,
    "capslock": 0x14,
    "numlock": 0x90,
}


# ─── ctypes structures ──────────────────────────────────────

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT_UNION),
    ]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


# ─── Helper functions ─────────────────────────────────────


def _button_flags(button: str) -> tuple[int, int]:
    mapping = {
        "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
        "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
        "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
    }
    return mapping.get(button, (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP))


# ─── WindowsPlatform ──────────────────────────────────────


class WindowsPlatform:
    """Windows GUI automation using ctypes (user32/gdi32).

    Provides screenshot capture (multi-monitor), mouse/keyboard input,
    clipboard access, and window management.
    """

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._gdi32 = ctypes.windll.gdi32
        self._kernel32 = ctypes.windll.kernel32

    # ── Screenshot ──────────────────────────────────────────

    def capture_screen(self, monitor: str | int = "primary") -> Image.Image:
        """Capture screen. monitor='primary', 'all', or monitor index (0, 1, ...)."""
        if monitor == "all":
            return self._capture_virtual_screen()
        elif isinstance(monitor, int):
            return self._capture_monitor_by_index(monitor)
        else:
            return self._capture_primary()

    def _capture_primary(self) -> Image.Image:
        """Capture primary monitor via GDI BitBlt."""
        try:
            w = self._user32.GetSystemMetrics(_SM_CXSCREEN)
            h = self._user32.GetSystemMetrics(_SM_CYSCREEN)
            return self._bitblt_capture(0, 0, w, h)
        except Exception:
            from PIL import ImageGrab
            return ImageGrab.grab()

    def _capture_virtual_screen(self) -> Image.Image:
        """Capture entire virtual screen (all monitors)."""
        try:
            x = self._user32.GetSystemMetrics(_SM_XVIRTUALSCREEN)
            y = self._user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)
            w = self._user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN)
            h = self._user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)
            return self._bitblt_capture(x, y, w, h)
        except Exception:
            from PIL import ImageGrab
            return ImageGrab.grab(all_screens=True)

    def _capture_monitor_by_index(self, index: int) -> Image.Image:
        """Capture a specific monitor by index."""
        monitors = self.get_monitors()
        if index < 0 or index >= len(monitors):
            return self._capture_primary()
        m = monitors[index]
        return self._bitblt_capture(m["x"], m["y"], m["width"], m["height"])

    def _bitblt_capture(self, x: int, y: int, w: int, h: int) -> Image.Image:
        """Low-level GDI BitBlt screen capture."""
        hdesktop = self._user32.GetDesktopWindow()
        hdc = self._user32.GetWindowDC(hdesktop)
        hdc_mem = self._gdi32.CreateCompatibleDC(hdc)
        hbmp = self._gdi32.CreateCompatibleBitmap(hdc, w, h)
        self._gdi32.SelectObject(hdc_mem, hbmp)
        self._gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc, x, y, 0x00CC0020)  # SRCCOPY

        bmp_info_header = (ctypes.c_byte * 40)(
            40, 0, 0, 0,
            w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF,
            h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF, (h >> 24) & 0xFF,
            1, 0,
            24, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
        )
        stride = ((w * 3 + 3) & ~3)
        buf = (ctypes.c_byte * (stride * h))()
        self._gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, bmp_info_header, 0)

        self._gdi32.DeleteObject(hbmp)
        self._gdi32.DeleteDC(hdc_mem)
        self._user32.ReleaseDC(hdesktop, hdc)

        img = Image.frombuffer("RGB", (w, h), bytes(buf), "raw", "BGR", stride, -1)
        return img

    def get_monitors(self) -> list[dict[str, Any]]:
        """Enumerate all monitors with their positions and sizes."""
        monitors: list[dict[str, Any]] = []

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                            ctypes.POINTER(_RECT), ctypes.c_double)
        def callback(hmonitor, hdc, lprect, lparam):
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            self._user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
            r = info.rcMonitor
            monitors.append({
                "x": r.left,
                "y": r.top,
                "width": r.right - r.left,
                "height": r.bottom - r.top,
                "is_primary": bool(info.dwFlags & 1),
            })
            return 1

        self._user32.EnumDisplayMonitors(None, None, callback, 0)
        return monitors

    # ── Mouse ──────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left", click_count: int = 1) -> None:
        self._user32.SetCursorPos(x, y)
        down_flag, up_flag = _button_flags(button)
        for _ in range(click_count):
            self._user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            self._user32.mouse_event(up_flag, 0, 0, 0, 0)
            if click_count > 1:
                time.sleep(0.05)

    def mouse_move(self, x: int, y: int) -> None:
        self._user32.SetCursorPos(x, y)

    def mouse_down(self, x: int, y: int, button: str = "left") -> None:
        self._user32.SetCursorPos(x, y)
        down_flag, _ = _button_flags(button)
        self._user32.mouse_event(down_flag, 0, 0, 0, 0)

    def mouse_up(self, x: int, y: int, button: str = "left") -> None:
        self._user32.SetCursorPos(x, y)
        _, up_flag = _button_flags(button)
        self._user32.mouse_event(up_flag, 0, 0, 0, 0)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
             button: str = "left", duration: float = 0.5) -> None:
        self._user32.SetCursorPos(start_x, start_y)
        down_flag, up_flag = _button_flags(button)
        self._user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.05)

        steps = max(int(duration * 60), 10)
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(start_x + (end_x - start_x) * t)
            cy = int(start_y + (end_y - start_y) * t)
            self._user32.SetCursorPos(cx, cy)
            time.sleep(duration / steps)

        self._user32.mouse_event(up_flag, 0, 0, 0, 0)

    def scroll(self, x: int, y: int, clicks: int = 3, direction: str = "down") -> None:
        self._user32.SetCursorPos(x, y)
        if direction in ("up", "down"):
            amount = clicks * 120 * (1 if direction == "up" else -1)
            self._user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0,
                                     ctypes.c_int(amount).value, 0)
        elif direction in ("left", "right"):
            amount = clicks * 120 * (1 if direction == "right" else -1)
            self._user32.mouse_event(_MOUSEEVENTF_HWHEEL, 0, 0,
                                     ctypes.c_int(amount).value, 0)

    # ── Keyboard ───────────────────────────────────────────

    def type_text(self, text: str) -> None:
        """Type text character by character using SendInput with KEYEVENTF_UNICODE."""
        inputs: list[_INPUT] = []
        for ch in text:
            scan = ord(ch)
            ki_down = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=_KEYEVENTF_UNICODE,
                                  time=0, dwExtraInfo=None)
            inputs.append(_INPUT(type=_INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki_down)))
            ki_up = _KEYBDINPUT(wVk=0, wScan=scan,
                                dwFlags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP,
                                time=0, dwExtraInfo=None)
            inputs.append(_INPUT(type=_INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki_up)))
        self._send_input_batch(inputs)

    def press_key(self, key: str) -> None:
        """Send a single key or key combo like 'ctrl+s', 'alt+f4'."""
        if "+" in key:
            parts = [p.strip().lower() for p in key.split("+")]
        else:
            parts = [key.strip().lower()]

        vk_codes = [self._vk_for_key(p) for p in parts]

        inputs: list[_INPUT] = []
        for vk in vk_codes:
            ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
            inputs.append(_INPUT(type=_INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki)))
        for vk in reversed(vk_codes):
            ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=_KEYEVENTF_KEYUP,
                             time=0, dwExtraInfo=None)
            inputs.append(_INPUT(type=_INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki)))
        self._send_input_batch(inputs)

    # ── Clipboard ──────────────────────────────────────────

    def get_clipboard(self) -> str:
        try:
            if not self._user32.OpenClipboard(None):
                return ""
            h_data = self._user32.GetClipboardData(_CF_UNICODETEXT)
            if not h_data:
                self._user32.CloseClipboard()
                return ""
            ptr = self._kernel32.GlobalLock(h_data)
            if not ptr:
                self._user32.CloseClipboard()
                return ""
            text = ctypes.wstring_at(ptr)
            self._kernel32.GlobalUnlock(h_data)
            self._user32.CloseClipboard()
            return text
        except Exception:
            return ""

    def set_clipboard(self, text: str) -> None:
        try:
            encoded = (text + "\x00").encode("utf-16-le")
            h_mem = self._kernel32.GlobalAlloc(0x0042, len(encoded))
            if not h_mem:
                return
            ptr = self._kernel32.GlobalLock(h_mem)
            ctypes.memmove(ptr, encoded, len(encoded))
            self._kernel32.GlobalUnlock(h_mem)

            if not self._user32.OpenClipboard(None):
                self._kernel32.GlobalFree(h_mem)
                return
            self._user32.EmptyClipboard()
            self._user32.SetClipboardData(_CF_UNICODETEXT, h_mem)
            self._user32.CloseClipboard()
        except Exception:
            pass

    # ── Window management ──────────────────────────────────

    def get_active_window(self) -> dict[str, Any]:
        try:
            hwnd = self._user32.GetForegroundWindow()
            length = self._user32.GetWindowTextLengthW(hwnd) + 1
            title_buf = ctypes.create_unicode_buffer(length)
            self._user32.GetWindowTextW(hwnd, title_buf, length)

            class_buf = ctypes.create_unicode_buffer(256)
            self._user32.GetClassNameW(hwnd, class_buf, 256)

            rect = _RECT()
            self._user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return {
                "title": title_buf.value,
                "class_name": class_buf.value,
                "hwnd": hwnd,
                "x": rect.left,
                "y": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }
        except Exception:
            return {"title": "", "class_name": "", "hwnd": 0,
                    "x": 0, "y": 0, "width": 0, "height": 0}

    def list_windows(self) -> list[dict[str, Any]]:
        """List all visible windows with titles."""
        windows: list[dict[str, Any]] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        def enum_callback(hwnd, lparam):
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    title_buf = ctypes.create_unicode_buffer(length + 1)
                    self._user32.GetWindowTextW(hwnd, title_buf, length + 1)
                    title = title_buf.value.strip()
                    if title:
                        class_buf = ctypes.create_unicode_buffer(256)
                        self._user32.GetClassNameW(hwnd, class_buf, 256)
                        rect = _RECT()
                        self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        windows.append({
                            "title": title,
                            "class_name": class_buf.value,
                            "hwnd": hwnd,
                            "x": rect.left,
                            "y": rect.top,
                            "width": rect.right - rect.left,
                            "height": rect.bottom - rect.top,
                        })
            return True

        self._user32.EnumWindows(enum_callback, 0)
        return windows

    def focus_window(self, title: str) -> bool:
        """Bring a window to foreground by partial title match."""
        for w in self.list_windows():
            if title.lower() in w["title"].lower():
                hwnd = w["hwnd"]
                self._user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                self._user32.SetForegroundWindow(hwnd)
                return True
        return False

    def minimize_window(self, title: str) -> bool:
        for w in self.list_windows():
            if title.lower() in w["title"].lower():
                self._user32.ShowWindow(w["hwnd"], 6)  # SW_MINIMIZE
                return True
        return False

    def maximize_window(self, title: str) -> bool:
        for w in self.list_windows():
            if title.lower() in w["title"].lower():
                self._user32.ShowWindow(w["hwnd"], 3)  # SW_MAXIMIZE
                return True
        return False

    # ── Screen info ────────────────────────────────────────

    def get_screen_info(self) -> dict[str, Any]:
        monitors = self.get_monitors()
        primary_w = self._user32.GetSystemMetrics(_SM_CXSCREEN)
        primary_h = self._user32.GetSystemMetrics(_SM_CYSCREEN)
        virtual_w = self._user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN)
        virtual_h = self._user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)
        return {
            "primary_width": primary_w,
            "primary_height": primary_h,
            "virtual_width": virtual_w,
            "virtual_height": virtual_h,
            "monitor_count": len(monitors),
            "monitors": monitors,
        }

    def get_cursor_position(self) -> tuple[int, int]:
        point = ctypes.wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    # ── Internal helpers ───────────────────────────────────

    def _vk_for_key(self, key: str) -> int:
        key_lower = key.lower()
        if key_lower in _VK_CODE_MAP:
            return _VK_CODE_MAP[key_lower]
        if len(key) == 1:
            vk = self._user32.VkKeyScanW(ord(key)) & 0xFF
            return vk if vk != 0xFF else 0
        return 0

    def _send_input_batch(self, inputs: list[_INPUT]) -> None:
        if not inputs:
            return
        arr = (_INPUT * len(inputs))(*inputs)
        self._user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))
