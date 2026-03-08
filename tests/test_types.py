"""Tests for cue_mcp.types — platform-independent."""

from __future__ import annotations

import pytest

from cue_mcp.types import (
    EpisodeRecord,
    Lesson,
    SafetyDecision,
    SafetyLevel,
    StructuralElement,
    TextElement,
    UIElement,
    VerificationResult,
    VisualElement,
)


# ── SafetyLevel ────────────────────────────────────────────────────────────────

class TestSafetyLevel:
    def test_safe_value(self):
        assert SafetyLevel.SAFE.value == "safe"

    def test_needs_confirmation_value(self):
        assert SafetyLevel.NEEDS_CONFIRMATION.value == "needs_confirmation"

    def test_blocked_value(self):
        assert SafetyLevel.BLOCKED.value == "blocked"

    def test_all_members(self):
        members = {m.value for m in SafetyLevel}
        assert members == {"safe", "needs_confirmation", "blocked"}

    def test_enum_identity(self):
        assert SafetyLevel("safe") is SafetyLevel.SAFE
        assert SafetyLevel("blocked") is SafetyLevel.BLOCKED


# ── SafetyDecision ─────────────────────────────────────────────────────────────

class TestSafetyDecision:
    def test_minimal_creation(self):
        d = SafetyDecision(level=SafetyLevel.SAFE)
        assert d.level is SafetyLevel.SAFE
        assert d.reason == ""
        assert d.pattern_matched is None

    def test_full_creation(self):
        d = SafetyDecision(
            level=SafetyLevel.BLOCKED,
            reason="dangerous command",
            pattern_matched="rm -rf",
        )
        assert d.level is SafetyLevel.BLOCKED
        assert d.reason == "dangerous command"
        assert d.pattern_matched == "rm -rf"

    def test_needs_confirmation(self):
        d = SafetyDecision(
            level=SafetyLevel.NEEDS_CONFIRMATION,
            reason="confirm required",
            pattern_matched="delete",
        )
        assert d.level is SafetyLevel.NEEDS_CONFIRMATION


# ── UIElement ──────────────────────────────────────────────────────────────────

class TestUIElement:
    def test_creation_minimal(self):
        el = UIElement(type="button", bbox=(0, 0, 100, 50))
        assert el.type == "button"
        assert el.bbox == (0, 0, 100, 50)
        assert el.label == ""
        assert el.confidence == 0.0
        assert el.sources == []

    def test_creation_full(self):
        el = UIElement(
            type="input",
            bbox=(10, 20, 110, 60),
            label="Search",
            confidence=0.95,
            sources=["ocr", "accessibility"],
        )
        assert el.label == "Search"
        assert el.confidence == 0.95
        assert el.sources == ["ocr", "accessibility"]

    def test_center_even_bbox(self):
        el = UIElement(type="button", bbox=(0, 0, 100, 50))
        assert el.center == (50, 25)

    def test_center_odd_bbox(self):
        el = UIElement(type="button", bbox=(10, 20, 110, 70))
        # (10+110)//2=60, (20+70)//2=45
        assert el.center == (60, 45)

    def test_center_zero_size(self):
        el = UIElement(type="icon", bbox=(5, 5, 5, 5))
        assert el.center == (5, 5)

    def test_center_non_zero_origin(self):
        el = UIElement(type="panel", bbox=(100, 200, 300, 400))
        assert el.center == (200, 300)

    def test_to_dict(self):
        el = UIElement(
            type="button",
            bbox=(0, 0, 100, 50),
            label="OK",
            confidence=0.9,
            sources=["ocr"],
        )
        d = el.to_dict()
        assert d["type"] == "button"
        assert d["bbox"] == [0, 0, 100, 50]
        assert d["label"] == "OK"
        assert d["confidence"] == 0.9
        assert d["center"] == [50, 25]
        assert d["sources"] == ["ocr"]

    def test_sources_are_independent(self):
        el = UIElement(type="button", bbox=(0, 0, 10, 10))
        el.sources.append("ocr")
        el2 = UIElement(type="icon", bbox=(0, 0, 5, 5))
        assert el2.sources == []


# ── VisualElement ──────────────────────────────────────────────────────────────

class TestVisualElement:
    def test_creation_minimal(self):
        ve = VisualElement(type="icon", bbox=(0, 0, 16, 16))
        assert ve.type == "icon"
        assert ve.bbox == (0, 0, 16, 16)
        assert ve.confidence == 0.0

    def test_creation_with_confidence(self):
        ve = VisualElement(type="button", bbox=(10, 10, 60, 30), confidence=0.88)
        assert ve.confidence == 0.88


# ── TextElement ────────────────────────────────────────────────────────────────

class TestTextElement:
    def test_creation_minimal(self):
        te = TextElement(text="Hello", bbox=(0, 0, 50, 20))
        assert te.text == "Hello"
        assert te.bbox == (0, 0, 50, 20)
        assert te.confidence == 0.0

    def test_creation_with_confidence(self):
        te = TextElement(text="Submit", bbox=(5, 5, 55, 25), confidence=0.99)
        assert te.confidence == 0.99

    def test_empty_text(self):
        te = TextElement(text="", bbox=(0, 0, 0, 0))
        assert te.text == ""


# ── StructuralElement ──────────────────────────────────────────────────────────

class TestStructuralElement:
    def test_creation_minimal(self):
        se = StructuralElement(role="button", name="OK", bbox=(0, 0, 80, 30))
        assert se.role == "button"
        assert se.name == "OK"
        assert se.states == []

    def test_creation_with_states(self):
        se = StructuralElement(
            role="checkbox", name="Accept", bbox=(0, 0, 20, 20), states=["checked"]
        )
        assert se.states == ["checked"]

    def test_states_independent(self):
        se1 = StructuralElement(role="button", name="A", bbox=(0, 0, 1, 1))
        se2 = StructuralElement(role="button", name="B", bbox=(0, 0, 1, 1))
        se1.states.append("focused")
        assert se2.states == []


# ── VerificationResult ─────────────────────────────────────────────────────────

class TestVerificationResult:
    def test_defaults(self):
        vr = VerificationResult()
        assert vr.tier == 1
        assert vr.success is False
        assert vr.confidence == 0.0
        assert vr.reason == ""
        assert vr.details is None

    def test_full_creation(self):
        vr = VerificationResult(
            tier=2,
            success=True,
            confidence=0.85,
            reason="screen changed",
            details={"ssim_diff": 0.05},
        )
        assert vr.tier == 2
        assert vr.success is True
        assert vr.confidence == 0.85
        assert vr.details == {"ssim_diff": 0.05}


# ── Lesson ─────────────────────────────────────────────────────────────────────

class TestLesson:
    def test_defaults(self):
        lesson = Lesson()
        assert lesson.id == ""
        assert lesson.app == ""
        assert lesson.confidence == 0.7
        assert lesson.success_count == 0
        assert lesson.failure_count == 0
        assert lesson.reinforcement_count == 0

    def test_to_dict(self):
        lesson = Lesson(
            app="notepad",
            situation="file not saved",
            failed_approach="close directly",
            successful_approach="ctrl+s first",
            confidence=0.9,
            text="In notepad, when file not saved, use ctrl+s first.",
        )
        d = lesson.to_dict()
        assert d["app"] == "notepad"
        assert d["situation"] == "file not saved"
        assert d["failed_approach"] == "close directly"
        assert d["successful_approach"] == "ctrl+s first"
        assert d["confidence"] == 0.9
        assert d["text"] == "In notepad, when file not saved, use ctrl+s first."


# ── EpisodeRecord ──────────────────────────────────────────────────────────────

class TestEpisodeRecord:
    def test_defaults(self):
        ep = EpisodeRecord()
        assert ep.id == ""
        assert ep.task == ""
        assert ep.app == ""
        assert ep.success is False
        assert ep.total_steps == 0
        assert ep.failure_patterns == []
        assert ep.recovery_strategies == []

    def test_failure_patterns_independent(self):
        ep1 = EpisodeRecord()
        ep2 = EpisodeRecord()
        ep1.failure_patterns.append("timeout")
        assert ep2.failure_patterns == []

    def test_to_dict(self):
        ep = EpisodeRecord(
            task="open browser",
            app="chrome",
            success=True,
            total_steps=3,
            reflection="worked fine",
        )
        d = ep.to_dict()
        assert d["task"] == "open browser"
        assert d["app"] == "chrome"
        assert d["success"] is True
        assert d["total_steps"] == 3
        assert d["reflection"] == "worked fine"
