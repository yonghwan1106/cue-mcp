"""CUE-MCP Server — Computer Use Enhanced MCP Server for Claude Code.

Provides GUI automation tools with intelligent augmentation.
Run: python -m cue_mcp.server
"""

from __future__ import annotations

import base64
import io
import logging
import sys
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ImageContent

# Route logging to stderr to avoid polluting stdio JSON-RPC
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="[CUE-MCP] %(levelname)s: %(message)s")
logger = logging.getLogger("cue-mcp")

from cue_mcp.platform import WindowsPlatform

# ─── Server init ───────────────────────────────────────────

mcp = FastMCP(
    name="cue-mcp",
    instructions=(
        "Windows GUI 자동화 MCP 서버. "
        "스크린샷 캡처, 마우스/키보드 제어, 창 관리 기능을 제공합니다. "
        "Claude Code에서 컴퓨터 화면을 보고 GUI를 조작할 수 있게 합니다."
    ),
)

platform = WindowsPlatform()

# ─── Screenshot tools ──────────────────────────────────────


@mcp.tool()
def screenshot(monitor: str = "primary") -> list[TextContent | ImageContent]:
    """현재 화면을 캡처합니다.

    Args:
        monitor: 캡처 대상. 'primary'=주 모니터, 'all'=전체 가상 화면,
                 '0','1'=특정 모니터 인덱스
    """
    try:
        mon = int(monitor) if monitor.isdigit() else monitor
    except (ValueError, AttributeError):
        mon = "primary"

    img = platform.capture_screen(monitor=mon)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    # Save fallback file for clients that can't render ImageContent
    fallback_path = _save_screenshot_fallback(buf.getvalue())

    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(
            type="text",
            text=f"스크린샷 캡처 완료: {img.width}x{img.height} (파일: {fallback_path})",
        ),
    ]


@mcp.tool()
def screenshot_region(x: int, y: int, width: int, height: int) -> list[TextContent | ImageContent]:
    """화면의 특정 영역을 캡처합니다.

    Args:
        x: 시작 X 좌표
        y: 시작 Y 좌표
        width: 캡처 너비
        height: 캡처 높이
    """
    img = platform.capture_screen(monitor="all")
    region = img.crop((x, y, x + width, y + height))

    buf = io.BytesIO()
    region.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    fallback_path = _save_screenshot_fallback(buf.getvalue())

    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(
            type="text",
            text=f"영역 캡처 완료: ({x},{y}) {width}x{height} (파일: {fallback_path})",
        ),
    ]


# ─── Mouse tools ───────────────────────────────────────────


@mcp.tool()
def click(x: int, y: int, button: str = "left") -> str:
    """지정한 화면 좌표를 클릭합니다.

    Args:
        x: X 좌표
        y: Y 좌표
        button: 'left', 'right', 또는 'middle'
    """
    platform.click(x, y, button=button)
    return f"클릭 완료: ({x}, {y}) [{button}]"


@mcp.tool()
def double_click(x: int, y: int) -> str:
    """지정한 좌표를 더블클릭합니다."""
    platform.click(x, y, click_count=2)
    return f"더블클릭 완료: ({x}, {y})"


@mcp.tool()
def right_click(x: int, y: int) -> str:
    """지정한 좌표를 우클릭합니다."""
    platform.click(x, y, button="right")
    return f"우클릭 완료: ({x}, {y})"


@mcp.tool()
def drag(start_x: int, start_y: int, end_x: int, end_y: int,
         button: str = "left", duration: float = 0.5) -> str:
    """시작점에서 끝점까지 드래그합니다.

    Args:
        start_x: 시작 X
        start_y: 시작 Y
        end_x: 끝 X
        end_y: 끝 Y
        button: 마우스 버튼
        duration: 드래그 소요 시간(초)
    """
    platform.drag(start_x, start_y, end_x, end_y, button=button, duration=duration)
    return f"드래그 완료: ({start_x},{start_y}) → ({end_x},{end_y})"


@mcp.tool()
def scroll(x: int, y: int, clicks: int = 3, direction: str = "down") -> str:
    """지정 위치에서 스크롤합니다.

    Args:
        x: X 좌표
        y: Y 좌표
        clicks: 스크롤 양 (노치 수)
        direction: 'up', 'down', 'left', 'right'
    """
    platform.scroll(x, y, clicks=clicks, direction=direction)
    return f"스크롤 완료: ({x},{y}) {direction} {clicks}칸"


@mcp.tool()
def move_mouse(x: int, y: int) -> str:
    """마우스 커서를 지정 좌표로 이동합니다."""
    platform.mouse_move(x, y)
    return f"커서 이동: ({x}, {y})"


# ─── Keyboard tools ────────────────────────────────────────


@mcp.tool()
def type_text(text: str) -> str:
    """현재 포커스된 위치에 텍스트를 입력합니다. 한글/유니코드 지원.

    Args:
        text: 입력할 텍스트
    """
    platform.type_text(text)
    display = text[:50] + "..." if len(text) > 50 else text
    return f"입력 완료: '{display}'"


@mcp.tool()
def press_key(key: str) -> str:
    """키 또는 키 조합을 누릅니다.

    Args:
        key: 키 이름 또는 조합. 예: 'enter', 'ctrl+s', 'alt+f4', 'ctrl+shift+t'
    """
    platform.press_key(key)
    return f"키 입력: {key}"


@mcp.tool()
def hotkey(keys: str) -> str:
    """단축키를 실행합니다. press_key의 별칭입니다.

    Args:
        keys: 키 조합. 예: 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d'
    """
    platform.press_key(keys)
    return f"단축키 실행: {keys}"


# ─── Window management tools ──────────────────────────────


@mcp.tool()
def list_windows() -> str:
    """현재 열려 있는 모든 창 목록을 반환합니다."""
    windows = platform.list_windows()
    if not windows:
        return "열린 창이 없습니다."

    lines = []
    for i, w in enumerate(windows):
        lines.append(
            f"[{i}] {w['title']} ({w['class_name']}) "
            f"- 위치: ({w['x']},{w['y']}) 크기: {w['width']}x{w['height']}"
        )
    return f"열린 창 {len(windows)}개:\n" + "\n".join(lines)


@mcp.tool()
def get_active_window() -> str:
    """현재 활성(포커스된) 창 정보를 반환합니다."""
    w = platform.get_active_window()
    return (
        f"활성 창: {w['title']}\n"
        f"클래스: {w['class_name']}\n"
        f"위치: ({w['x']},{w['y']}) 크기: {w['width']}x{w['height']}"
    )


@mcp.tool()
def focus_window(title: str) -> str:
    """창 제목으로 해당 창을 포커스(전면으로 가져오기)합니다.

    Args:
        title: 창 제목의 일부 (부분 일치)
    """
    if platform.focus_window(title):
        return f"창 포커스 완료: '{title}'"
    return f"창을 찾을 수 없습니다: '{title}'"


@mcp.tool()
def minimize_window(title: str) -> str:
    """창을 최소화합니다."""
    if platform.minimize_window(title):
        return f"최소화 완료: '{title}'"
    return f"창을 찾을 수 없습니다: '{title}'"


@mcp.tool()
def maximize_window(title: str) -> str:
    """창을 최대화합니다."""
    if platform.maximize_window(title):
        return f"최대화 완료: '{title}'"
    return f"창을 찾을 수 없습니다: '{title}'"


# ─── Clipboard tools ──────────────────────────────────────


@mcp.tool()
def get_clipboard() -> str:
    """클립보드의 텍스트 내용을 가져옵니다."""
    text = platform.get_clipboard()
    if not text:
        return "(클립보드 비어 있음)"
    return f"클립보드 내용:\n{text}"


@mcp.tool()
def set_clipboard(text: str) -> str:
    """클립보드에 텍스트를 설정합니다.

    Args:
        text: 설정할 텍스트
    """
    platform.set_clipboard(text)
    display = text[:50] + "..." if len(text) > 50 else text
    return f"클립보드 설정 완료: '{display}'"


# ─── System info tools ────────────────────────────────────


@mcp.tool()
def get_screen_info() -> str:
    """화면/모니터 정보를 반환합니다 (해상도, 모니터 수, 각 모니터 위치)."""
    info = platform.get_screen_info()
    lines = [
        f"주 모니터: {info['primary_width']}x{info['primary_height']}",
        f"가상 화면: {info['virtual_width']}x{info['virtual_height']}",
        f"모니터 수: {info['monitor_count']}",
    ]
    for i, m in enumerate(info["monitors"]):
        primary = " (주)" if m["is_primary"] else ""
        lines.append(
            f"  모니터 {i}{primary}: {m['width']}x{m['height']} "
            f"위치: ({m['x']},{m['y']})"
        )
    return "\n".join(lines)


@mcp.tool()
def get_cursor_position() -> str:
    """현재 마우스 커서 위치를 반환합니다."""
    x, y = platform.get_cursor_position()
    return f"커서 위치: ({x}, {y})"


# ─── Helpers ───────────────────────────────────────────────


def _save_screenshot_fallback(png_bytes: bytes) -> str:
    """Save screenshot to temp file as fallback for clients that can't render ImageContent."""
    import tempfile
    import os
    fallback_dir = os.path.join(tempfile.gettempdir(), "cue-mcp")
    os.makedirs(fallback_dir, exist_ok=True)

    import time as _time
    filename = f"screenshot_{int(_time.time() * 1000)}.png"
    filepath = os.path.join(fallback_dir, filename)

    with open(filepath, "wb") as f:
        f.write(png_bytes)

    return filepath


# ─── Entry point ───────────────────────────────────────────

def main():
    logger.info("CUE-MCP Server starting (stdio transport)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
