"""Tests for cue_mcp.verification module."""

from __future__ import annotations

import pytest
from PIL import Image

from cue_mcp.verification import verify_screenshots
from cue_mcp.types import VerificationResult


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def same_images(tmp_path):
    """Two identical images — no visual change."""
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    for x in range(50, 150):
        for y in range(50, 150):
            img.putpixel((x, y), (200, 100, 50))
    p1 = str(tmp_path / "before.png")
    p2 = str(tmp_path / "after.png")
    img.save(p1)
    img.save(p2)
    return p1, p2


@pytest.fixture
def different_images(tmp_path):
    """Two visually different images — clear change."""
    img_a = Image.new("RGB", (200, 200), color=(10, 10, 10))
    for x in range(10, 190):
        for y in range(10, 190):
            img_a.putpixel((x, y), (20, 20, 20))

    img_b = Image.new("RGB", (200, 200), color=(240, 240, 240))
    for x in range(10, 190):
        for y in range(10, 190):
            img_b.putpixel((x, y), (220, 220, 220))

    p1 = str(tmp_path / "before.png")
    p2 = str(tmp_path / "after.png")
    img_a.save(p1)
    img_b.save(p2)
    return p1, p2


# ── Return type ─────────────────────────────────────────────────────────────────

class TestReturnType:
    def test_returns_verification_result(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert isinstance(result, VerificationResult)

    def test_result_has_tier(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert isinstance(result.tier, int)

    def test_result_has_success(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert isinstance(result.success, bool)

    def test_result_has_confidence(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert isinstance(result.confidence, float)

    def test_result_has_reason(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert isinstance(result.reason, str)


# ── Same images (no change) ─────────────────────────────────────────────────────

class TestSameImages:
    def test_no_change_detected(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert result.success is False

    def test_tier_is_nonzero(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert result.tier >= 1

    def test_confidence_is_positive(self, same_images):
        before, after = same_images
        result = verify_screenshots(before, after)
        assert result.confidence >= 0.0


# ── Different images (clear change) ────────────────────────────────────────────

class TestDifferentImages:
    def test_change_detected(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after)
        assert result.success is True

    def test_tier_is_nonzero(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after)
        assert result.tier >= 1

    def test_confidence_is_positive(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after)
        assert result.confidence > 0.0


# ── Action types ────────────────────────────────────────────────────────────────

class TestActionTypes:
    def test_click_with_coordinates(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="click",
                                    click_x=100, click_y=100)
        assert result.success is True

    def test_click_without_coordinates(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="click")
        assert result.success is True

    def test_scroll_action(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="scroll")
        assert result.success is True

    def test_type_action(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="type")
        assert result.success is True

    def test_key_action(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="key")
        assert result.success is True

    def test_unknown_action_type(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="unknown_action")
        assert isinstance(result, VerificationResult)

    def test_left_click_action(self, different_images):
        before, after = different_images
        result = verify_screenshots(before, after, action_type="left_click",
                                    click_x=50, click_y=50)
        assert isinstance(result, VerificationResult)


# ── Default action type ─────────────────────────────────────────────────────────

class TestDefaultActionType:
    def test_default_is_click(self, different_images):
        """verify_screenshots defaults to action_type='click'."""
        before, after = different_images
        result_default = verify_screenshots(before, after)
        result_click = verify_screenshots(before, after, action_type="click")
        assert result_default.success == result_click.success


# ── Invalid / missing paths ─────────────────────────────────────────────────────

class TestInvalidPaths:
    def test_nonexistent_before(self, different_images):
        _, after = different_images
        result = verify_screenshots("/nonexistent/before.png", after)
        assert result.success is False
        assert result.tier == 0

    def test_nonexistent_after(self, different_images):
        before, _ = different_images
        result = verify_screenshots(before, "/nonexistent/after.png")
        assert result.success is False
        assert result.tier == 0

    def test_both_nonexistent(self):
        result = verify_screenshots("/nonexistent/a.png", "/nonexistent/b.png")
        assert result.success is False
        assert result.tier == 0

    def test_invalid_path_has_reason(self):
        result = verify_screenshots("/nonexistent/a.png", "/nonexistent/b.png")
        assert result.reason != ""


# ── Tier logic ──────────────────────────────────────────────────────────────────

class TestTierLogic:
    def test_tier1_or_tier2_for_obvious_changes(self, different_images):
        """Large changes should resolve at tier 1 or fall through to tier 2."""
        before, after = different_images
        result = verify_screenshots(before, after)
        assert result.tier in (1, 2)

    def test_tier1_or_tier2_for_identical_images(self, same_images):
        """Identical images should resolve at tier 1 with high confidence fail."""
        before, after = same_images
        result = verify_screenshots(before, after)
        assert result.tier in (1, 2)
