"""Verification module: Tier 1 (SSIM) + Tier 2 (region diff) screenshot comparison.

Ported from CUE verification/tier1.py and verification/tier2.py.
Tier 3 (Claude API semantic) is intentionally excluded — Claude Code itself
serves as the semantic judge.
"""

from __future__ import annotations

import logging

from cue_mcp.types import VerificationResult

logger = logging.getLogger(__name__)


def verify_screenshots(
    before_path: str,
    after_path: str,
    action_type: str = "click",
    click_x: int | None = None,
    click_y: int | None = None,
) -> VerificationResult:
    """Compare before/after screenshots to verify an action had effect.

    Uses numpy for fast pixel-level comparison. Falls back gracefully
    if numpy or PIL are unavailable.

    Args:
        before_path: Path to screenshot taken before the action.
        after_path: Path to screenshot taken after the action.
        action_type: Type of action performed (click, type, scroll, etc.)
        click_x: X coordinate of click (for region-based Tier 2 check).
        click_y: Y coordinate of click (for region-based Tier 2 check).
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return VerificationResult(
            tier=0, success=False, confidence=0.0,
            reason="numpy/PIL not available for verification",
        )

    try:
        img_a = np.array(Image.open(before_path).convert("RGB"))
        img_b = np.array(Image.open(after_path).convert("RGB"))
    except Exception as e:
        return VerificationResult(
            tier=0, success=False, confidence=0.0,
            reason=f"Failed to load screenshots: {e}",
        )

    # ── Tier 1: SSIM-like overall diff ─────────────────────
    tier1 = _tier1_verify(img_a, img_b)
    if tier1.confidence >= 0.8:
        return tier1  # High-confidence pass or fail

    if not tier1.success and tier1.confidence >= 0.7:
        return tier1  # High-confidence fail (screen unchanged)

    # ── Tier 2: Action-type-aware region check ─────────────
    tier2 = _tier2_verify(img_a, img_b, action_type, click_x, click_y)
    return tier2


def _tier1_verify(img_a, img_b) -> VerificationResult:
    """Fast SSIM-like verification via mean absolute difference."""
    import numpy as np

    # Downscale for performance
    h, w = img_a.shape[:2]
    scale = max(1, min(h // 270, w // 480))
    if scale > 1:
        img_a_s = img_a[::scale, ::scale]
        img_b_s = img_b[::scale, ::scale]
    else:
        img_a_s, img_b_s = img_a, img_b

    gray_a = np.mean(img_a_s, axis=2).astype(np.float32)
    gray_b = np.mean(img_b_s, axis=2).astype(np.float32)

    mad = float(np.mean(np.abs(gray_a - gray_b)) / 255.0)
    ssim_approx = max(0.0, 1.0 - mad * 10.0)
    ssim_diff = 1.0 - ssim_approx

    details = {"ssim_approx": round(ssim_approx, 4), "ssim_diff": round(ssim_diff, 4)}

    SSIM_CHANGE = 0.005
    SSIM_MINOR = 0.001

    if ssim_diff >= SSIM_CHANGE:
        return VerificationResult(
            tier=1, success=True, confidence=0.8,
            reason=f"Tier1 pass: screen changed (diff={ssim_diff:.4f})",
            details=details,
        )

    if ssim_diff < SSIM_MINOR:
        return VerificationResult(
            tier=1, success=False, confidence=0.9,
            reason=f"Tier1 fail: screen unchanged (diff={ssim_diff:.4f})",
            details=details,
        )

    # Ambiguous
    return VerificationResult(
        tier=1, success=False, confidence=0.4,
        reason=f"Tier1 ambiguous: diff={ssim_diff:.4f}",
        details=details,
    )


def _tier2_verify(img_a, img_b, action_type: str,
                  click_x: int | None, click_y: int | None) -> VerificationResult:
    """Action-type-aware region comparison."""
    import numpy as np

    if img_a.shape != img_b.shape:
        return VerificationResult(
            tier=2, success=True, confidence=0.5,
            reason="Tier2: image size changed, assuming action had effect",
        )

    overall = float(np.mean(np.abs(img_a.astype(np.float32) - img_b.astype(np.float32)))) / 255.0
    details = {"overall_diff": round(overall, 6), "action_type": action_type}

    PASS_SCORE = 0.6
    FAIL_SCORE = 0.2

    if action_type in ("click", "left_click") and click_x is not None and click_y is not None:
        region_diff = _region_diff(img_a, img_b, click_x, click_y)
        details["region_diff"] = round(region_diff, 6)
        region_score = min(region_diff / 0.005, 1.0)
        overall_score = min(overall / 0.003, 1.0)
        score = 0.7 * region_score + 0.3 * overall_score
    elif action_type == "scroll":
        h = img_a.shape[0]
        strip_h = max(1, h // 10)
        top_diff = float(np.mean(np.abs(
            img_a[:strip_h].astype(np.float32) - img_b[:strip_h].astype(np.float32)
        ))) / 255.0
        bot_diff = float(np.mean(np.abs(
            img_a[h - strip_h:].astype(np.float32) - img_b[h - strip_h:].astype(np.float32)
        ))) / 255.0
        shift_score = min((top_diff + bot_diff) / 0.02, 1.0)
        overall_score = min(overall / 0.01, 1.0)
        score = 0.6 * shift_score + 0.4 * overall_score
    elif action_type in ("type", "key"):
        changed = overall >= 0.0005
        score = max(0.65, min(overall / 0.005, 1.0)) if changed else 0.1
    else:
        score = 0.7 if overall >= 0.003 else 0.1

    details["score"] = round(score, 4)

    if score >= PASS_SCORE:
        return VerificationResult(
            tier=2, success=True,
            confidence=0.6 + 0.3 * min((score - PASS_SCORE) / (1.0 - PASS_SCORE), 1.0),
            reason=f"Tier2 pass: score={score:.2f}",
            details=details,
        )
    if score <= FAIL_SCORE:
        return VerificationResult(
            tier=2, success=False, confidence=0.7,
            reason=f"Tier2 fail: score={score:.2f}",
            details=details,
        )

    return VerificationResult(
        tier=2, success=False, confidence=0.3,
        reason=f"Tier2 ambiguous: score={score:.2f}",
        details=details,
    )


def _region_diff(img_a, img_b, cx: int, cy: int, half: int = 80) -> float:
    """Normalized mean absolute pixel diff in a region around (cx, cy)."""
    import numpy as np
    h, w = img_a.shape[:2]
    x1, y1 = max(0, cx - half), max(0, cy - half)
    x2, y2 = min(w, cx + half), min(h, cy + half)
    crop_a = img_a[y1:y2, x1:x2].astype(np.float32)
    crop_b = img_b[y1:y2, x1:x2].astype(np.float32)
    if crop_a.size == 0:
        return 0.0
    return float(np.mean(np.abs(crop_a - crop_b))) / 255.0
