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
import time
from typing import Any

from PIL import Image

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ImageContent

# Route logging to stderr to avoid polluting stdio JSON-RPC
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="[CUE-MCP] %(levelname)s: %(message)s")
logger = logging.getLogger("cue-mcp")

from cue_mcp.platform import WindowsPlatform
from cue_mcp.safety import SafetyGate
from cue_mcp.memory import MemoryStore

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
safety_gate = SafetyGate()
memory_store = MemoryStore()

# Screenshot cache: key -> (timestamp, Image)
_screenshot_cache: dict[str, tuple[float, Image.Image]] = {}
_CACHE_TTL = 0.5  # 500ms 캐시 유효시간

# ─── Screenshot tools ──────────────────────────────────────


@mcp.tool()
def screenshot(monitor: str = "primary", max_width: int = 800,
               quality: int = 40) -> list[TextContent | ImageContent]:
    """현재 화면을 캡처합니다.

    Args:
        monitor: 캡처 대상. 'primary'=주 모니터, 'all'=전체 가상 화면,
                 '0','1'=특정 모니터 인덱스
        max_width: 전송용 이미지 최대 너비 (기본 800). 원본은 파일로 저장됨.
        quality: JPEG 압축 품질 1-95 (기본 40)
    """
    try:
        mon = int(monitor) if monitor.isdigit() else monitor
    except (ValueError, AttributeError):
        mon = "primary"

    cache_key = str(mon)
    now = time.time()
    cache_hit = False
    if cache_key in _screenshot_cache:
        cached_time, cached_img = _screenshot_cache[cache_key]
        if now - cached_time < _CACHE_TTL:
            img = cached_img.copy()
            cache_hit = True
    if not cache_hit:
        img = platform.capture_screen(monitor=mon)
        _screenshot_cache[cache_key] = (now, img.copy())

    original_size = f"{img.width}x{img.height}"

    # Save full-resolution original as fallback
    fallback_buf = io.BytesIO()
    img.save(fallback_buf, format="PNG")
    fallback_path = _save_screenshot_fallback(fallback_buf.getvalue())

    # Resize for MCP transport (keep aspect ratio)
    if img.width > max_width:
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)

    # JPEG compression for smaller payload
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    cache_note = " (캐시)" if cache_hit else ""
    return [
        ImageContent(type="image", data=b64, mimeType="image/jpeg"),
        TextContent(
            type="text",
            text=(
                f"스크린샷 캡처 완료{cache_note}: 원본 {original_size}, "
                f"전송 {img.width}x{img.height} "
                f"(원본 파일: {fallback_path})"
            ),
        ),
    ]


@mcp.tool()
def screenshot_region(x: int, y: int, width: int, height: int,
                      quality: int = 70) -> list[TextContent | ImageContent]:
    """화면의 특정 영역을 캡처합니다.

    Args:
        x: 시작 X 좌표
        y: 시작 Y 좌표
        width: 캡처 너비
        height: 캡처 높이
        quality: JPEG 압축 품질 1-95 (기본 70)
    """
    img = platform.capture_screen(monitor="all")
    region = img.crop((x, y, x + width, y + height))

    # Save original
    fallback_buf = io.BytesIO()
    region.save(fallback_buf, format="PNG")
    fallback_path = _save_screenshot_fallback(fallback_buf.getvalue())

    # Compress for MCP transport
    buf = io.BytesIO()
    region.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return [
        ImageContent(type="image", data=b64, mimeType="image/jpeg"),
        TextContent(
            type="text",
            text=f"영역 캡처 완료: ({x},{y}) {width}x{height} (원본: {fallback_path})",
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
    decision = safety_gate.check("type", text)
    if decision.level.value == "blocked":
        return f"안전 차단: {decision.reason}"
    platform.type_text(text)
    display = text[:50] + "..." if len(text) > 50 else text
    return f"입력 완료: '{display}'"


@mcp.tool()
def press_key(key: str) -> str:
    """키 또는 키 조합을 누릅니다.

    Args:
        key: 키 이름 또는 조합. 예: 'enter', 'ctrl+s', 'alt+f4', 'ctrl+shift+t'
    """
    decision = safety_gate.check("key", "", key)
    if decision.level.value == "blocked":
        return f"안전 차단: {decision.reason}"
    platform.press_key(key)
    return f"키 입력: {key}"


@mcp.tool()
def hotkey(keys: str) -> str:
    """단축키를 실행합니다. press_key의 별칭입니다.

    Args:
        keys: 키 조합. 예: 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d'
    """
    decision = safety_gate.check("key", "", keys)
    if decision.level.value == "blocked":
        return f"안전 차단: {decision.reason}"
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


# ─── Grounding tools (Phase 2) ─────────────────────────────


@mcp.tool()
def find_elements(label: str = "", max_results: int = 10) -> str:
    """화면에서 UI 요소들을 감지합니다 (OpenCV + OCR).

    그라운딩 결과로 버튼, 텍스트 필드, 아이콘 등의 좌표와 신뢰도를 반환합니다.

    Args:
        label: 찾고자 하는 UI 요소의 텍스트 (빈 문자열이면 모든 요소 반환)
        max_results: 최대 반환 개수 (기본 10)
    """
    try:
        from cue_mcp.grounding import GroundingEngine
    except ImportError:
        return "그라운딩 모듈 로드 실패: opencv-python, pytesseract 설치 필요"

    engine = GroundingEngine()
    img = platform.capture_screen(monitor="primary")
    elements = engine.ground(img)

    if label:
        elements = engine.find_by_label(elements, label)

    elements = elements[:max_results]

    if not elements:
        msg = f"'{label}' 요소를 찾을 수 없습니다." if label else "UI 요소를 감지하지 못했습니다."
        return msg

    lines = [f"감지된 UI 요소 {len(elements)}개:"]
    for i, e in enumerate(elements):
        cx, cy = e.center
        lines.append(
            f"  [{i}] {e.type}: '{e.label}' "
            f"중심=({cx},{cy}) bbox={list(e.bbox)} "
            f"신뢰도={e.confidence:.0%} 소스={e.sources}"
        )
    return "\n".join(lines)


@mcp.tool()
def smart_click(label: str, button: str = "left") -> str:
    """텍스트 레이블로 UI 요소를 찾아 자동으로 클릭합니다.

    그라운딩으로 요소를 찾고 → 중심 좌표를 계산하고 → 클릭합니다.

    Args:
        label: 클릭할 UI 요소의 텍스트 (예: '로그인', 'Submit', '파일')
        button: 마우스 버튼 ('left', 'right', 'middle')
    """
    try:
        from cue_mcp.grounding import GroundingEngine
    except ImportError:
        return "그라운딩 모듈 로드 실패: opencv-python, pytesseract 설치 필요"

    engine = GroundingEngine()
    img = platform.capture_screen(monitor="primary")
    elements = engine.ground(img)
    matches = engine.find_by_label(elements, label)

    if not matches:
        return f"'{label}' 요소를 찾을 수 없습니다. screenshot으로 화면을 확인해주세요."

    best = matches[0]
    cx, cy = best.center

    # Safety check
    decision = safety_gate.check("click", label)
    if decision.level.value == "blocked":
        return f"안전 차단: {decision.reason}"

    platform.click(cx, cy, button=button)
    return (
        f"스마트 클릭 완료: '{best.label}' ({best.type}) "
        f"좌표=({cx},{cy}) 신뢰도={best.confidence:.0%}"
    )


# ─── Verification tools (Phase 2) ─────────────────────────


@mcp.tool()
def verify_action(
    before_screenshot_path: str,
    after_screenshot_path: str,
    action_type: str = "click",
    click_x: int = -1,
    click_y: int = -1,
) -> str:
    """두 스크린샷을 비교하여 액션이 효과가 있었는지 검증합니다.

    스크린샷 파일 경로를 받아 SSIM diff + 영역 분석으로 판정합니다.

    Args:
        before_screenshot_path: 액션 전 스크린샷 파일 경로
        after_screenshot_path: 액션 후 스크린샷 파일 경로
        action_type: 수행한 액션 종류 (click, type, scroll 등)
        click_x: 클릭 X 좌표 (-1이면 미지정)
        click_y: 클릭 Y 좌표 (-1이면 미지정)
    """
    from cue_mcp.verification import verify_screenshots

    cx = click_x if click_x >= 0 else None
    cy = click_y if click_y >= 0 else None

    result = verify_screenshots(
        before_screenshot_path, after_screenshot_path,
        action_type=action_type, click_x=cx, click_y=cy,
    )

    status = "성공" if result.success else "실패"
    return (
        f"검증 결과: {status} (Tier {result.tier})\n"
        f"신뢰도: {result.confidence:.0%}\n"
        f"사유: {result.reason}\n"
        f"상세: {json.dumps(result.details or {}, ensure_ascii=False)}"
    )


# ─── Safety tools (Phase 2) ───────────────────────────────


@mcp.tool()
def check_safety(action_type: str, text: str = "", key: str = "") -> str:
    """액션의 안전성을 검사합니다 (SAFE/NEEDS_CONFIRMATION/BLOCKED).

    위험한 명령어 패턴, 민감한 경로 접근, 반복 액션 등을 검사합니다.

    Args:
        action_type: 액션 종류 (click, type, key 등)
        text: 입력 텍스트 (있는 경우)
        key: 키 입력 (있는 경우)
    """
    decision = safety_gate.check(action_type, text, key)
    return (
        f"안전성: {decision.level.value}\n"
        f"사유: {decision.reason}"
        + (f"\n매칭 패턴: {decision.pattern_matched}" if decision.pattern_matched else "")
    )


# ─── Memory tools (Phase 2) ───────────────────────────────


@mcp.tool()
def recall_lessons(app: str = "", top_k: int = 5) -> str:
    """학습된 교훈(Lesson)을 조회합니다.

    과거 경험에서 추출된 '실패→성공' 패턴을 반환합니다.

    Args:
        app: 앱 이름 (빈 문자열이면 모든 앱의 교훈 반환)
        top_k: 최대 반환 개수
    """
    if app:
        lessons = memory_store.recall_lessons(app, top_k)
    else:
        lessons = memory_store.recall_all_lessons(top_k)

    if not lessons:
        return "저장된 교훈이 없습니다."

    lines = [f"교훈 {len(lessons)}개:"]
    for i, l in enumerate(lessons):
        lines.append(
            f"  [{i}] [{l.app}] {l.situation}\n"
            f"      실패: '{l.failed_approach}'\n"
            f"      성공: '{l.successful_approach}'\n"
            f"      신뢰도: {l.confidence:.0%} (강화 {l.reinforcement_count}회)"
        )
    return "\n".join(lines)


@mcp.tool()
def save_lesson(
    app: str, situation: str,
    failed_approach: str, successful_approach: str,
    confidence: float = 0.7,
) -> str:
    """새로운 교훈을 저장합니다.

    실패한 접근법과 성공한 접근법을 기록하여 향후 참조합니다.

    Args:
        app: 앱 이름 (예: 'Chrome', 'VSCode', 'Excel')
        situation: 상황 설명 (예: '로그인 폼에서 비밀번호 입력')
        failed_approach: 실패한 접근법
        successful_approach: 성공한 접근법
        confidence: 신뢰도 0.0~1.0 (기본 0.7)
    """
    lesson_id = memory_store.save_lesson(
        app=app, situation=situation,
        failed_approach=failed_approach,
        successful_approach=successful_approach,
        confidence=confidence,
    )
    return f"교훈 저장 완료: {lesson_id}"


@mcp.tool()
def store_episode(
    task: str, app: str, success: bool,
    total_steps: int = 0, reflection: str = "",
) -> str:
    """작업 에피소드를 저장합니다.

    완료된 작업의 결과를 기록하여 유사 작업 수행 시 참조합니다.

    Args:
        task: 수행한 작업 설명
        app: 앱 이름
        success: 성공 여부
        total_steps: 총 단계 수
        reflection: 회고/메모
    """
    episode_id = memory_store.store_episode(
        task=task, app=app, success=success,
        total_steps=total_steps, reflection=reflection,
    )
    return f"에피소드 저장 완료: {episode_id}"


@mcp.tool()
def recall_episodes(task: str, app: str, top_k: int = 3) -> str:
    """유사한 과거 에피소드를 조회합니다.

    Args:
        task: 현재 작업 설명
        app: 앱 이름
        top_k: 최대 반환 개수
    """
    episodes = memory_store.find_similar_episodes(task, app, top_k)

    if not episodes:
        return f"'{app}'에 대한 유사 에피소드가 없습니다."

    lines = [f"유사 에피소드 {len(episodes)}개:"]
    for i, ep in enumerate(episodes):
        status = "성공" if ep.success else "실패"
        lines.append(
            f"  [{i}] [{status}] {ep.task}\n"
            f"      단계: {ep.total_steps}, 회고: {ep.reflection[:100]}"
        )
    return "\n".join(lines)


# ─── Multi-step execution tool ────────────────────────────


@mcp.tool()
def execute_steps(steps: str) -> str:
    """여러 GUI 액션을 순차적으로 실행하며 각 단계마다 스크린샷으로 검증합니다.

    Args:
        steps: JSON 형식의 액션 리스트.
               각 항목: {"action": "click|type|key|scroll|wait", "params": {...}}

    액션별 params:
        click:  {"x": int, "y": int, "button": str}
        type:   {"text": str}
        key:    {"key": str}
        scroll: {"x": int, "y": int, "clicks": int, "direction": str}
        wait:   {"seconds": float}

    예시:
        [
          {"action": "click", "params": {"x": 100, "y": 200}},
          {"action": "wait",  "params": {"seconds": 1}},
          {"action": "type",  "params": {"text": "hello"}},
          {"action": "key",   "params": {"key": "enter"}}
        ]
    """
    from cue_mcp.verification import verify_screenshots

    # ── Parse input ───────────────────────────────────────
    try:
        action_list = json.loads(steps)
    except json.JSONDecodeError as e:
        return f"JSON 파싱 오류: {e}"

    if not isinstance(action_list, list):
        return "steps는 JSON 배열이어야 합니다."

    results = []
    total = len(action_list)

    for idx, step in enumerate(action_list):
        action = step.get("action", "")
        params = step.get("params", {})
        step_label = f"[{idx + 1}/{total}] {action}"

        if not action:
            results.append(f"{step_label}: 'action' 필드가 없습니다. 건너뜁니다.")
            continue

        # ── Safety check ─────────────────────────────────
        text_param = params.get("text", "")
        key_param = params.get("key", "")
        decision = safety_gate.check(action, text_param, key_param)
        if decision.level.value == "blocked":
            results.append(f"{step_label}: 안전 차단 — {decision.reason}")
            results.append(f"총 {idx}/{total} 단계 완료 후 중단.")
            return "\n".join(results)

        # ── Before screenshot ─────────────────────────────
        before_img = platform.capture_screen(monitor="primary")
        before_buf = io.BytesIO()
        before_img.save(before_buf, format="PNG")
        before_path = _save_screenshot_fallback(before_buf.getvalue())

        # ── Execute action ────────────────────────────────
        try:
            if action == "click":
                x = params.get("x", 0)
                y = params.get("y", 0)
                button = params.get("button", "left")
                platform.click(x, y, button=button)
                action_desc = f"click ({x},{y}) [{button}]"

            elif action == "type":
                text = params.get("text", "")
                platform.type_text(text)
                display = text[:30] + "..." if len(text) > 30 else text
                action_desc = f"type '{display}'"

            elif action == "key":
                key = params.get("key", "")
                platform.press_key(key)
                action_desc = f"key '{key}'"

            elif action == "scroll":
                x = params.get("x", 0)
                y = params.get("y", 0)
                clicks = params.get("clicks", 3)
                direction = params.get("direction", "down")
                platform.scroll(x, y, clicks=clicks, direction=direction)
                action_desc = f"scroll ({x},{y}) {direction} {clicks}칸"

            elif action == "wait":
                seconds = float(params.get("seconds", 1))
                time.sleep(seconds)
                results.append(f"{step_label}: 대기 {seconds}초 완료")
                continue  # No verification needed for wait

            else:
                results.append(f"{step_label}: 알 수 없는 액션 '{action}'. 건너뜁니다.")
                continue

        except Exception as e:
            results.append(f"{step_label}: 실행 오류 — {e}")
            results.append(f"총 {idx}/{total} 단계 완료 후 중단.")
            return "\n".join(results)

        # ── After screenshot ──────────────────────────────
        after_img = platform.capture_screen(monitor="primary")
        after_buf = io.BytesIO()
        after_img.save(after_buf, format="PNG")
        after_path = _save_screenshot_fallback(after_buf.getvalue())

        # ── Verify ───────────────────────────────────────
        click_x = params.get("x") if action == "click" else None
        click_y = params.get("y") if action == "click" else None
        vresult = verify_screenshots(
            before_path, after_path,
            action_type=action,
            click_x=click_x,
            click_y=click_y,
        )

        status = "성공" if vresult.success else "실패"
        results.append(
            f"{step_label}: {action_desc} → 검증 {status} "
            f"(Tier {vresult.tier}, 신뢰도 {vresult.confidence:.0%}) — {vresult.reason}"
        )

        if not vresult.success and vresult.confidence >= 0.7:
            results.append(f"검증 실패 (신뢰도 {vresult.confidence:.0%}) → 중단.")
            results.append(f"총 {idx + 1}/{total} 단계 완료 후 중단.")
            return "\n".join(results)

    results.append(f"\n모든 {total}단계 완료.")
    return "\n".join(results)


# ─── Helpers ───────────────────────────────────────────────


def _save_screenshot_fallback(png_bytes: bytes) -> str:
    """Save screenshot to temp file as fallback for clients that can't render ImageContent."""
    import tempfile
    import os
    fallback_dir = os.path.join(tempfile.gettempdir(), "cue-mcp")
    os.makedirs(fallback_dir, exist_ok=True)

    # Cleanup: remove files older than 1 hour
    try:
        cutoff = time.time() - 3600
        for f in os.listdir(fallback_dir):
            fpath = os.path.join(fallback_dir, f)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
    except OSError:
        pass

    filename = f"screenshot_{int(time.time() * 1000)}.png"
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
