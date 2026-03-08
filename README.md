# CUE-MCP - Computer Use Enhanced MCP Server

Claude Code에서 컴퓨터 화면을 보고 GUI를 직접 조작할 수 있게 하는 MCP 서버입니다. Windows 10/11에서 외부 의존성을 최소화하고 안전하게 작동합니다.

## 개요

CUE-MCP는 Claude를 Windows GUI 자동화 에이전트로 변환합니다. 스크린샷 캡처, 마우스/키보드 제어, 창 관리, UI 요소 감지, 액션 검증, 안전성 검사, 학습 메모리를 통해 복잡한 컴퓨터 작업을 자동화합니다.

## 주요 기능

- **스크린샷 캡처**: 멀티모니터 지원, 영역 지정 캡처, JPEG 압축, 캐싱
- **마우스 제어**: 클릭, 더블클릭, 우클릭, 드래그, 스크롤
- **키보드 입력**: 한글/유니코드 지원, 단축키 조합
- **창 관리**: 창 목록, 포커스, 최소화/최대화
- **클립보드**: 텍스트 읽기/쓰기
- **UI 요소 감지**: OpenCV + Tesseract OCR 그라운딩 (선택 설치)
- **스마트 클릭**: 텍스트 레이블로 UI 요소 자동 찾기 및 클릭
- **액션 검증**: SSIM 기반 스크린샷 비교 검증
- **다단계 실행**: 여러 GUI 액션을 순차 실행하며 각 단계 검증
- **안전 장치**: 위험한 명령어 차단, 민감한 경로 접근 제한
- **학습 메모리**: SQLite 기반 에피소드 및 교훈 저장/조회

## 설치

### 기본 설치

```bash
git clone https://github.com/yonghwan1106/cue-mcp.git
cd cue-mcp
pip install -e .
```

### 그라운딩 기능 포함 (권장)

UI 요소 감지 및 스마트 클릭을 사용하려면:

```bash
pip install -e ".[grounding]"
```

포함되는 패키지:
- `opencv-python`: 이미지 처리 및 UI 요소 감지
- `pytesseract`: OCR (광학 문자 인식)
- `scikit-image`: 이미지 비교 알고리즘

### Tesseract OCR 설치 (선택)

OCR 기능을 사용하려면 Tesseract를 별도로 설치해야 합니다.

**Windows (Chocolatey):**
```bash
choco install tesseract
```

**Windows (수동 설치):**
1. [GitHub UB-Mannheim/tesseract releases](https://github.com/UB-Mannheim/tesseract/releases)에서 MSI 파일 다운로드
2. 설치 마법사 실행 (기본 경로: `C:\Program Files\Tesseract-OCR`)
3. 확인: `tesseract --version`

### 개발 환경 설정

```bash
pip install -e ".[dev]"
pytest tests/ -v
pip install -e ".[grounding,dev]"  # 모든 기능 포함
```

## Claude Code 설정

`~/.claude/settings.json`에 다음을 추가합니다:

```json
{
  "mcpServers": {
    "cue-mcp": {
      "command": "python",
      "args": ["-m", "cue_mcp"],
      "cwd": "C:\\Users\\[username]\\projects\\2026_active\\cue-mcp"
    }
  }
}
```

**참고**: `cwd`는 실제 프로젝트 경로로 변경하세요.

Claude Code를 재시작하면 `@cue-mcp` 프롬프트로 도구에 접근할 수 있습니다.

## 도구 목록 (29개)

### 스크린샷 도구 (2개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `screenshot` | 화면 캡처 | `monitor` (primary/all/0/1), `max_width` (픽셀), `quality` (1-95) |
| `screenshot_region` | 영역 캡처 | `x`, `y`, `width`, `height`, `quality` |

### 마우스 도구 (6개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `click` | 좌표 클릭 | `x`, `y`, `button` (left/right/middle) |
| `double_click` | 더블클릭 | `x`, `y` |
| `right_click` | 우클릭 | `x`, `y` |
| `drag` | 드래그 | `start_x`, `start_y`, `end_x`, `end_y`, `button`, `duration` (초) |
| `scroll` | 스크롤 | `x`, `y`, `clicks`, `direction` (up/down/left/right) |
| `move_mouse` | 커서 이동 | `x`, `y` |

### 키보드 도구 (3개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `type_text` | 텍스트 입력 (한글/유니코드) | `text` |
| `press_key` | 단일 키 또는 조합 | `key` (예: `ctrl+s`, `alt+f4`) |
| `hotkey` | 단축키 실행 (press_key 별칭) | `keys` |

### 창 관리 도구 (5개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `list_windows` | 열린 창 목록 | 없음 |
| `get_active_window` | 활성 창 정보 | 없음 |
| `focus_window` | 창 포커스 | `title` (부분 일치) |
| `minimize_window` | 창 최소화 | `title` |
| `maximize_window` | 창 최대화 | `title` |

### 클립보드 도구 (2개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `get_clipboard` | 클립보드 텍스트 읽기 | 없음 |
| `set_clipboard` | 클립보드 텍스트 설정 | `text` |

### 시스템 정보 도구 (2개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `get_screen_info` | 모니터 정보 | 없음 |
| `get_cursor_position` | 커서 위치 | 없음 |

### 그라운딩 도구 (2개, 선택 설치)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `find_elements` | UI 요소 감지 | `label` (텍스트로 검색), `max_results` |
| `smart_click` | 텍스트로 UI 요소 찾아 클릭 | `label`, `button` |

### 검증 도구 (2개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `verify_action` | 액션 효과 검증 | `before_screenshot_path`, `after_screenshot_path`, `action_type`, `click_x`, `click_y` |
| `execute_steps` | 다단계 실행 및 검증 | `steps` (JSON 배열) |

### 안전 도구 (1개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `check_safety` | 액션 안전성 검사 | `action_type`, `text`, `key` |

### 메모리 도구 (4개)

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `recall_lessons` | 저장된 교훈 조회 | `app` (필터), `top_k` |
| `save_lesson` | 새 교훈 저장 | `app`, `situation`, `failed_approach`, `successful_approach`, `confidence` |
| `store_episode` | 작업 에피소드 저장 | `task`, `app`, `success`, `total_steps`, `reflection` |
| `recall_episodes` | 유사한 에피소드 조회 | `task`, `app`, `top_k` |

## 사용 예시

### 스크린샷 캡처

```
@cue-mcp screenshot
```

응답:
```
스크린샷 캡처 완료: 원본 1920x1080, 전송 800x450 (원본 파일: C:\...\screenshot_xxx.png)
[이미지 표시]
```

### 텍스트 입력 (한글 지원)

```
@cue-mcp type_text text:"안녕하세요"
```

### 마우스 클릭

```
@cue-mcp click x:500 y:300 button:left
```

### 단축키 실행

```
@cue-mcp press_key key:ctrl+s
```

### 창 관리

```
@cue-mcp list_windows
@cue-mcp focus_window title:Chrome
```

### UI 요소 감지 (그라운딩 설치 필수)

```
@cue-mcp find_elements label:로그인
```

응답:
```
감지된 UI 요소 2개:
  [0] button: '로그인' 중심=(450,300) bbox=[400, 280, 500, 320] 신뢰도=92% 소스=['text']
  [1] textfield: '이메일' 중심=(300,200) bbox=[200, 180, 400, 220] 신뢰도=40% 소스=['visual']
```

### 스마트 클릭 (텍스트로 자동 찾기)

```
@cue-mcp smart_click label:로그인
```

### 액션 검증

```
@cue-mcp verify_action before_screenshot_path:C:\...\before.png after_screenshot_path:C:\...\after.png action_type:click click_x:450 click_y:300
```

응답:
```
검증 결과: 성공 (Tier 1)
신뢰도: 80%
사유: Tier1 pass: screen changed (diff=0.0063)
상세: {"ssim_approx": 0.9937, "ssim_diff": 0.0063}

또는 Tier 2로 진행 시:
검증 결과: 성공 (Tier 2)
신뢰도: 75%
사유: Tier2 pass: score=0.83
상세: {"overall_diff": 0.003, "action_type": "click", "region_diff": 0.0041, "score": 0.83}
```

### 다단계 실행 및 검증

```
@cue-mcp execute_steps steps:[
  {"action": "click", "params": {"x": 100, "y": 200}},
  {"action": "wait",  "params": {"seconds": 1}},
  {"action": "type",  "params": {"text": "hello"}},
  {"action": "key",   "params": {"key": "enter"}}
]
```

각 단계마다 자동으로 검증됩니다.

### 메모리 기능

교훈 저장:
```
@cue-mcp save_lesson app:Chrome situation:로그인 버튼 찾기 failed_approach:임의의 좌표 클릭 successful_approach:OCR로 '로그인' 텍스트 위치 감지 후 클릭 confidence:0.85
```

교훈 조회:
```
@cue-mcp recall_lessons app:Chrome top_k:5
```

## 시스템 요구사항

- **OS**: Windows 10 또는 Windows 11
- **Python**: 3.11 이상
- **메모리**: 최소 512MB (그라운딩 사용 시 2GB 권장)
- **Tesseract OCR**: 그라운딩의 OCR 기능 사용 시 필수

## 구조

```
cue-mcp/
├── src/cue_mcp/
│   ├── __init__.py            # 패키지 메타데이터
│   ├── __main__.py            # 모듈 실행 엔트리포인트
│   ├── server.py              # MCP 서버 + 29개 도구 정의
│   ├── platform.py            # Windows 플랫폼 계층 (ctypes)
│   ├── safety.py              # 안전성 검사 + 긴급정지
│   ├── memory.py              # SQLite 기반 메모리 저장소
│   ├── grounding.py           # UI 요소 감지 (OpenCV + OCR)
│   ├── verification.py        # SSIM 기반 액션 검증
│   └── types.py               # 데이터 타입 정의
├── tests/                     # pytest 테스트
├── pyproject.toml             # 패키지 설정
└── README.md                  # 이 파일
```

## 트러블슈팅

### ImportError: No module named 'cue_mcp'

```bash
pip install -e .
```

### pytesseract.TesseractNotFoundError

Tesseract OCR이 설치되지 않았습니다.

```bash
choco install tesseract
```

또는 수동 설치 후 PATH에 `C:\Program Files\Tesseract-OCR` 추가.

### 그라운딩 도구 사용 불가

```bash
pip install -e ".[grounding]"
```

### 스크린샷이 검은색으로 나옴

멀티모니터 환경에서 잘못된 모니터가 선택되었을 수 있습니다.

```
@cue-mcp get_screen_info
```

로 모니터 정보를 확인한 후:

```
@cue-mcp screenshot monitor:0
```

### 명령어가 차단되었습니다 (안전 장치)

위험한 패턴이 감지되었습니다. 안전성을 확인하려면:

```
@cue-mcp check_safety action_type:type text:"위험한_명령어"
```

## 테스트

```bash
pytest tests/ -v
pytest tests/test_platform.py -v  # 특정 파일
ruff check src/ tests/            # 린트 검사
```

## 성능 팁

1. **스크린샷 품질**: 기본값 40은 전송 크기 최소화. 세부 작업 시 60 이상 권장.
   ```
   @cue-mcp screenshot quality:70
   ```

2. **멀티모니터**: 전체 화면 대신 특정 모니터 사용.
   ```
   @cue-mcp screenshot monitor:0
   ```

3. **UI 요소 감지**: 첫 실행은 느림 (OpenCV 초기화).

4. **메모리**: 메모리 저장소 정리 필요 시 수동 삭제:
   ```bash
   rm ~/.cue-mcp/episodic.db
   rm ~/.cue-mcp/semantic.db
   ```

## 라이선스

MIT License

## 기여

버그 리포트, 기능 제안, 풀 리퀘스트를 환영합니다.

## 연락처

- GitHub: https://github.com/yonghwan1106/cue-mcp
- 이슈: https://github.com/yonghwan1106/cue-mcp/issues
