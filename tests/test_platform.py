"""Basic tests for WindowsPlatform (Windows-only)."""

import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_import():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    assert p is not None


def test_capture_primary():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    img = p.capture_screen("primary")
    assert img.width > 0
    assert img.height > 0


def test_get_monitors():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    monitors = p.get_monitors()
    assert len(monitors) >= 1
    assert "width" in monitors[0]
    assert "is_primary" in monitors[0]


def test_screen_info():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    info = p.get_screen_info()
    assert info["primary_width"] > 0
    assert info["monitor_count"] >= 1


def test_cursor_position():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    x, y = p.get_cursor_position()
    assert isinstance(x, int)
    assert isinstance(y, int)


def test_list_windows():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    windows = p.list_windows()
    assert isinstance(windows, list)
    # At least one visible window should exist
    assert len(windows) > 0


def test_active_window():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    w = p.get_active_window()
    assert "title" in w
    assert "class_name" in w


def test_clipboard_roundtrip():
    from cue_mcp.platform import WindowsPlatform
    p = WindowsPlatform()
    test_text = "CUE-MCP 테스트 클립보드"
    p.set_clipboard(test_text)
    result = p.get_clipboard()
    assert result == test_text


def test_server_import():
    from cue_mcp.server import mcp
    assert mcp is not None
