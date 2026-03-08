"""Lightweight data types for CUE-MCP. No numpy dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── Safety ───────────────────────────────────────────────

class SafetyLevel(Enum):
    SAFE = "safe"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"


@dataclass
class SafetyDecision:
    level: SafetyLevel
    reason: str = ""
    pattern_matched: str | None = None


# ─── Grounding ────────────────────────────────────────────

@dataclass
class UIElement:
    type: str  # button, input, text_field, icon, panel, unknown
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    label: str = ""
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        return (self.bbox[0] + self.bbox[2]) // 2, (self.bbox[1] + self.bbox[3]) // 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "bbox": list(self.bbox),
            "label": self.label,
            "confidence": self.confidence,
            "center": list(self.center),
            "sources": self.sources,
        }


@dataclass
class VisualElement:
    type: str
    bbox: tuple[int, int, int, int]
    confidence: float = 0.0


@dataclass
class TextElement:
    text: str
    bbox: tuple[int, int, int, int]
    confidence: float = 0.0


@dataclass
class StructuralElement:
    role: str
    name: str
    bbox: tuple[int, int, int, int]
    states: list[str] = field(default_factory=list)


# ─── Verification ─────────────────────────────────────────

@dataclass
class VerificationResult:
    tier: int = 1
    success: bool = False
    confidence: float = 0.0
    reason: str = ""
    details: dict[str, Any] | None = None


# ─── Memory ───────────────────────────────────────────────

@dataclass
class Lesson:
    id: str = ""
    app: str = ""
    situation: str = ""
    failed_approach: str = ""
    successful_approach: str = ""
    confidence: float = 0.7
    success_count: int = 0
    failure_count: int = 0
    created_at: float = 0.0
    last_used: float = 0.0
    task_context: str = ""
    text: str = ""
    reinforcement_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app,
            "situation": self.situation,
            "failed_approach": self.failed_approach,
            "successful_approach": self.successful_approach,
            "confidence": self.confidence,
            "text": self.text,
        }


@dataclass
class EpisodeRecord:
    id: str = ""
    task: str = ""
    app: str = ""
    success: bool = False
    total_steps: int = 0
    steps_summary: str = ""
    failure_patterns: list[str] = field(default_factory=list)
    recovery_strategies: list[str] = field(default_factory=list)
    reflection: str = ""
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "app": self.app,
            "success": self.success,
            "total_steps": self.total_steps,
            "reflection": self.reflection,
        }
