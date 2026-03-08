"""Grounding module: UI element detection via OpenCV + OCR + merge.

Ported from CUE grounding/visual.py, grounding/textual.py, grounding/merger.py.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from PIL import Image

from cue_mcp.types import TextElement, UIElement, VisualElement

logger = logging.getLogger(__name__)

# ─── OpenCV Visual Grounder ───────────────────────────────


class OpenCVGrounder:
    """Detects UI elements via Canny edges + contour analysis + NMS."""

    _MIN_W = 15
    _MIN_H = 10
    _MAX_W = 800
    _MAX_H = 600

    def __init__(self, nms_iou_threshold: float = 0.5) -> None:
        self._nms_iou = nms_iou_threshold

    def detect(self, screenshot: Image.Image) -> list[VisualElement]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("opencv-python not installed, skipping visual grounding")
            return []

        img = np.array(screenshot.convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        candidates: list[VisualElement] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if not (self._MIN_W <= w <= self._MAX_W and self._MIN_H <= h <= self._MAX_H):
                continue
            elem_type = self._classify(w, h)
            confidence = self._confidence(cnt, w, h)
            candidates.append(VisualElement(
                type=elem_type,
                bbox=(x, y, x + w, y + h),
                confidence=confidence,
            ))

        return self._nms(candidates)

    @staticmethod
    def _classify(w: int, h: int) -> str:
        ratio = w / max(h, 1)
        if ratio > 3 and h < 40:
            return "text_field"
        if 0.8 < ratio < 1.5 and w < 50:
            return "icon"
        if ratio > 2 and h < 35:
            return "button"
        if w > 200 and h > 100:
            return "panel"
        return "unknown"

    @staticmethod
    def _confidence(contour: Any, w: int, h: int) -> float:
        import cv2
        area = float(cv2.contourArea(contour))
        if area < 1:
            return 0.0
        rect_area = float(w * h)
        rectangularity = min(area / rect_area, 1.0)
        perimeter = cv2.arcLength(contour, True)
        circularity = 0.0
        if perimeter >= 1:
            circularity = min((4 * math.pi * area) / (perimeter ** 2), 1.0)
        return round(0.6 * rectangularity + 0.4 * circularity, 4)

    def _nms(self, elements: list[VisualElement]) -> list[VisualElement]:
        if not elements:
            return []
        sorted_elems = sorted(elements, key=lambda e: e.confidence, reverse=True)
        kept: list[VisualElement] = []
        for candidate in sorted_elems:
            if not any(_iou(candidate.bbox, a.bbox) > self._nms_iou for a in kept):
                kept.append(candidate)
        return kept


# ─── OCR Text Grounder ────────────────────────────────────


class TextGrounder:
    """Detects text elements using Tesseract OCR."""

    def detect(self, screenshot: Image.Image) -> list[TextElement]:
        try:
            import pytesseract
        except ImportError:
            logger.warning("pytesseract not installed, skipping OCR grounding")
            return []

        try:
            data = pytesseract.image_to_data(
                screenshot, output_type=pytesseract.Output.DICT, lang="eng"
            )
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s", e)
            return []

        elements: list[TextElement] = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])
            if not text or conf < 30:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            elements.append(TextElement(
                text=text,
                bbox=(x, y, x + w, y + h),
                confidence=conf / 100.0,
            ))
        return elements


# ─── Source Merger ─────────────────────────────────────────

_CONF_VISUAL_ONLY = 0.40
_CONF_TEXT_BONUS = 0.25
_CONF_STRUCTURAL_BONUS = 0.35
_IOU_MATCH_THRESHOLD = 0.3


class SourceMerger:
    """Merges outputs from visual and text experts into unified UIElements."""

    def merge(
        self,
        visual: list[VisualElement],
        text: list[TextElement],
    ) -> list[UIElement]:
        merged: list[UIElement] = []
        used_text: set[int] = set()

        for vel in visual:
            elem = UIElement(
                type=vel.type, bbox=vel.bbox, label="",
                confidence=_CONF_VISUAL_ONLY, sources=["visual"],
            )

            best_text_idx = self._best_match(vel.bbox, text, used_text)
            if best_text_idx is not None:
                tel = text[best_text_idx]
                used_text.add(best_text_idx)
                elem.label = tel.text
                elem.confidence += _CONF_TEXT_BONUS
                elem.sources.append("text")
                elem.bbox = tel.bbox

            elem.confidence = round(min(elem.confidence, 1.0), 4)
            merged.append(elem)

        # Add unmatched text-only elements
        for i, tel in enumerate(text):
            if i in used_text:
                continue
            merged.append(UIElement(
                type="text_field", bbox=tel.bbox, label=tel.text,
                confidence=round(_CONF_TEXT_BONUS, 4), sources=["text"],
            ))

        merged.sort(key=lambda e: e.confidence, reverse=True)
        return merged

    def _best_match(
        self, ref_bbox: tuple[int, int, int, int],
        candidates: list[Any], used: set[int],
    ) -> int | None:
        best_idx: int | None = None
        best_iou = _IOU_MATCH_THRESHOLD
        for i, cand in enumerate(candidates):
            if i in used:
                continue
            iou_val = _iou(ref_bbox, cand.bbox)
            if iou_val > best_iou:
                best_iou = iou_val
                best_idx = i
        return best_idx


# ─── Grounding Orchestrator ───────────────────────────────


class GroundingEngine:
    """Orchestrates visual + text grounding and merges results."""

    def __init__(self) -> None:
        self._visual = OpenCVGrounder()
        self._text = TextGrounder()
        self._merger = SourceMerger()

    def ground(self, screenshot: Image.Image) -> list[UIElement]:
        visual = self._visual.detect(screenshot)
        text = self._text.detect(screenshot)
        return self._merger.merge(visual, text)

    def find_by_label(self, elements: list[UIElement], label: str) -> list[UIElement]:
        label_lower = label.lower()
        return [e for e in elements if label_lower in e.label.lower()]


# ─── Helpers ──────────────────────────────────────────────


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
