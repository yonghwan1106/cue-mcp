"""Safety Gate: classifies actions as SAFE, NEEDS_CONFIRMATION, or BLOCKED.

Ported from CUE (Computer Use Enhancer) safety/gate.py.
"""

from __future__ import annotations

import re
import time

from cue_mcp.types import SafetyDecision, SafetyLevel

# Default blocked command patterns
DEFAULT_BLOCKED = [
    "rm -rf", "sudo rm", "mkfs", "dd if=",
    "DROP TABLE", "DROP DATABASE", "DELETE FROM", "TRUNCATE",
    "shutdown", "reboot", "init 0", "init 6",
    "format c:", "del /s /q", "rd /s /q",  # Windows additions
]

# Default confirmation patterns
DEFAULT_CONFIRM = [
    "send", "submit", "publish", "delete", "remove",
    "post", "tweet", "email", "purchase", "pay",
]

# Default sensitive paths
DEFAULT_SENSITIVE_PATHS = [
    "/etc/", "/boot/", "/sys/", "~/.ssh/", "~/.gnupg/", "/root/",
    "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",  # Windows
]


class EmergencyStop:
    """Detects repeated actions to prevent infinite loops."""

    def __init__(self, max_repeated: int = 5, timeout: int = 600) -> None:
        self.max_repeated = max_repeated
        self.timeout = timeout
        self._history: list[str] = []
        self._start_time: float = 0.0

    def start(self) -> None:
        self._start_time = time.time()
        self._history.clear()

    def check(self, action_key: str) -> tuple[bool, str]:
        if self._start_time > 0 and time.time() - self._start_time > self.timeout:
            return False, f"Timeout exceeded ({self.timeout}s)"

        self._history.append(action_key)
        if len(self._history) >= self.max_repeated:
            recent = self._history[-self.max_repeated:]
            if len(set(recent)) == 1:
                return False, f"Repeated action ({self.max_repeated}x): {action_key}"

        return True, ""

    def reset(self) -> None:
        self._history.clear()
        self._start_time = 0.0


class SafetyGate:
    """Three-level action classifier based on pattern matching."""

    def __init__(
        self,
        blocked_commands: list[str] | None = None,
        confirmation_patterns: list[str] | None = None,
        sensitive_paths: list[str] | None = None,
    ) -> None:
        blocked = blocked_commands or DEFAULT_BLOCKED
        confirm = confirmation_patterns or DEFAULT_CONFIRM

        self._blocked_patterns = [
            (raw, re.compile(re.escape(raw), re.IGNORECASE))
            for raw in blocked
        ]
        self._confirmation_patterns = [
            (raw, re.compile(r"\b" + re.escape(raw) + r"\b", re.IGNORECASE))
            for raw in confirm
        ]
        self._sensitive_paths = sensitive_paths or DEFAULT_SENSITIVE_PATHS
        self._emergency_stop = EmergencyStop()

    def check(self, action_type: str, text: str = "", key: str = "") -> SafetyDecision:
        """Classify an action and return a SafetyDecision."""
        combined = f"{text} {key}".strip()

        # 1. BLOCKED check
        for raw, pattern in self._blocked_patterns:
            if pattern.search(combined):
                return SafetyDecision(
                    level=SafetyLevel.BLOCKED,
                    reason=f"Blocked command pattern: {raw!r}",
                    pattern_matched=raw,
                )

        # 2. NEEDS_CONFIRMATION: confirmation words
        for raw, pattern in self._confirmation_patterns:
            if pattern.search(combined):
                return SafetyDecision(
                    level=SafetyLevel.NEEDS_CONFIRMATION,
                    reason=f"Confirmation pattern: {raw!r}",
                    pattern_matched=raw,
                )

        # 3. NEEDS_CONFIRMATION: sensitive path access
        for path in self._sensitive_paths:
            if path.lower() in combined.lower():
                return SafetyDecision(
                    level=SafetyLevel.NEEDS_CONFIRMATION,
                    reason=f"Sensitive path: {path!r}",
                    pattern_matched=path,
                )

        return SafetyDecision(level=SafetyLevel.SAFE, reason="No safety patterns matched")

    def check_emergency(self, action_key: str) -> SafetyDecision:
        safe, reason = self._emergency_stop.check(action_key)
        if not safe:
            return SafetyDecision(level=SafetyLevel.BLOCKED, reason=reason)
        return SafetyDecision(level=SafetyLevel.SAFE, reason="OK")

    def start_session(self) -> None:
        self._emergency_stop.start()

    def reset_session(self) -> None:
        self._emergency_stop.reset()
