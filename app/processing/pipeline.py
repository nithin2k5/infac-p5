"""
INFAC-P5 — processing/pipeline.py
Full image-processing pipeline:
  Frame → Reflection Reduction → Segmentation → LAB Extraction → Result
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple

import cv2
import numpy as np

from app.classification.classifier import ColorClassifier, ClassificationResult, LABColor
from app.utils.constants import (
    ROI_X_FRAC, ROI_Y_FRAC, ROI_W_FRAC, ROI_H_FRAC,
    DEFAULT_REFLECTION_THRESH, DEFAULT_REFLECTION_BLEND,
    PROCESSING_QUEUE_MAXSIZE,
    FRAME_W, FRAME_H,
)

logger = logging.getLogger(__name__)


# ── Processed frame bundle ────────────────────────────────────────────────────

@dataclass
class ProcessedFrame:
    """Everything the UI needs for one inspection cycle."""
    display_frame: np.ndarray = field(default_factory=lambda: np.zeros((FRAME_H, FRAME_W, 3), np.uint8))
    result: ClassificationResult = field(default_factory=ClassificationResult)
    roi: Tuple[int, int, int, int] = (0, 0, 0, 0)      # x, y, w, h
    contours_found: int = 0
    lighting_ok: bool = True
    latency_ms: float = 0.0


# ── Processing pipeline ───────────────────────────────────────────────────────

class InspectionPipeline:
    """
    Threaded inspection pipeline.

    Accepts raw frames via `submit_frame()`, processes them in a background
    thread, and delivers `ProcessedFrame` objects via `on_result` callback.
    """

    def __init__(
        self,
        classifier: Optional[ColorClassifier] = None,
        on_result: Optional[Callable[[ProcessedFrame], None]] = None,
    ) -> None:
        self.classifier  = classifier or ColorClassifier()
        self.on_result   = on_result

        # Processing parameters (tunable from UI)
        self.roi_frac    = (ROI_X_FRAC, ROI_Y_FRAC, ROI_W_FRAC, ROI_H_FRAC)
        self.refl_thresh = DEFAULT_REFLECTION_THRESH
        self.refl_blend  = DEFAULT_REFLECTION_BLEND
        self.active      = False
        self.paused      = False

        # Internal
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=PROCESSING_QUEUE_MAXSIZE)
        self._thread: Optional[threading.Thread] = None
        self._lock   = threading.Lock()

    # ── Control API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        if self.active:
            return
        self.active = True
        self.paused = False
        self._thread = threading.Thread(
            target=self._process_loop, daemon=True, name="InspectionPipeline"
        )
        self._thread.start()
        logger.info("InspectionPipeline started")

    def stop(self) -> None:
        self.active = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("InspectionPipeline stopped")

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def submit_frame(self, frame: np.ndarray) -> None:
        """Non-blocking frame submission; drops frame if queue full."""
        if not self.active or self.paused:
            return
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            pass  # drop silently to keep latency low

    # ── Parameter setters (from UI) ───────────────────────────────────────────

    def set_roi_frac(self, x: float, y: float, w: float, h: float) -> None:
        with self._lock:
            self.roi_frac = (x, y, w, h)

    def set_reflection_thresh(self, thresh: int) -> None:
        with self._lock:
            self.refl_thresh = int(thresh)

    def set_reflection_blend(self, blend: float) -> None:
        with self._lock:
            self.refl_blend = float(blend)

    # ── Internal processing loop ──────────────────────────────────────────────

    def _process_loop(self) -> None:
        import time
        while self.active:
            try:
                frame = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            t0 = time.perf_counter()
            try:
                pf = self._run_pipeline(frame)
                pf.latency_ms = (time.perf_counter() - t0) * 1000
                if self.on_result:
                    self.on_result(pf)
            except Exception as exc:
                logger.error("Pipeline error: %s", exc, exc_info=True)

    # ── Pipeline stages ───────────────────────────────────────────────────────

    def _run_pipeline(self, frame: np.ndarray) -> ProcessedFrame:
        with self._lock:
            roi_frac    = self.roi_frac
            refl_thresh = self.refl_thresh
            refl_blend  = self.refl_blend

        H, W = frame.shape[:2]

        # ── 1. Compute ROI pixel coordinates ─────────────────────────────────
        rx = int(roi_frac[0] * W)
        ry = int(roi_frac[1] * H)
        rw = int(roi_frac[2] * W)
        rh = int(roi_frac[3] * H)
        rx = max(0, min(rx, W - rw))
        ry = max(0, min(ry, H - rh))
        roi_rect = (rx, ry, rw, rh)

        # ── 2. Extract ROI ────────────────────────────────────────────────────
        roi_bgr = frame[ry:ry+rh, rx:rx+rw].copy()

        # ── 3. Reflection reduction ───────────────────────────────────────────
        roi_bgr, refl_pct = self._suppress_reflections(roi_bgr, refl_thresh, refl_blend)

        # ── 4. Segmentation — detect dominant object in ROI ───────────────────
        mask, contours = self._segment_object(roi_bgr)
        n_contours = len(contours)

        # ── 5. Apply mask to ROI ──────────────────────────────────────────────
        if mask is not None:
            roi_masked = cv2.bitwise_and(roi_bgr, roi_bgr, mask=mask)
        else:
            roi_masked = roi_bgr

        # ── 6. LAB conversion & feature extraction ────────────────────────────
        lab_color, pixel_var = self._extract_lab(roi_masked, mask)

        # ── 7. Dominant colour ────────────────────────────────────────────────
        dominant_hex = self._dominant_hex(roi_masked, mask)

        # ── 8. Classify ───────────────────────────────────────────────────────
        result = self.classifier.classify(
            measured_lab  = lab_color,
            reflection_pct= refl_pct,
            pixel_variance= pixel_var,
            dominant_hex  = dominant_hex,
        )

        # ── 9. Build display frame ────────────────────────────────────────────
        display = self._build_display(frame, roi_rect, contours, result, refl_pct)

        # ── 10. Lighting consistency check ────────────────────────────────────
        lighting_ok = 40 < lab_color.L < 95

        return ProcessedFrame(
            display_frame  = display,
            result         = result,
            roi            = roi_rect,
            contours_found = n_contours,
            lighting_ok    = lighting_ok,
        )

    # ── Stage implementations ─────────────────────────────────────────────────

    @staticmethod
    def _suppress_reflections(
        roi: np.ndarray, thresh: int, blend: float
    ) -> Tuple[np.ndarray, float]:
        """Inpaint specular highlights; return processed ROI + reflection %."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, highlight_mask = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        refl_pct = 100.0 * np.count_nonzero(highlight_mask) / gray.size

        if refl_pct > 0.5:
            # Dilate mask slightly to capture highlight halos
            kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            dilated = cv2.dilate(highlight_mask, kernel, iterations=1)
            inpainted = cv2.inpaint(roi, dilated, 3, cv2.INPAINT_TELEA)
            out = cv2.addWeighted(roi, 1 - blend, inpainted, blend, 0)
        else:
            out = roi

        return out, refl_pct

    @staticmethod
    def _segment_object(roi: np.ndarray):
        """
        Segment the main object in the ROI.
        Returns (mask, list_of_contours).
        """
        gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur  = cv2.GaussianBlur(gray, (9, 9), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        closed = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN,  kernel, iterations=1)

        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, []

        # Keep only the largest contour
        largest = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(largest) / (roi.shape[0] * roi.shape[1])

        # Reject if object too small (< 5 % of ROI) — probably noise
        if area_ratio < 0.05:
            return None, []

        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [largest], -1, 255, thickness=cv2.FILLED)
        return mask, [largest]

    @staticmethod
    def _extract_lab(
        roi_masked: np.ndarray, mask: Optional[np.ndarray]
    ) -> Tuple[LABColor, float]:
        """Convert to LAB and compute mean + variance over non-black pixels."""
        lab_img = cv2.cvtColor(roi_masked, cv2.COLOR_BGR2LAB).astype(np.float32)
        # OpenCV encodes L: 0-255 (maps 0-100), a/b: 0-255 (maps -128-127)
        lab_img[:, :, 0] = lab_img[:, :, 0] * (100.0 / 255.0)
        lab_img[:, :, 1] = lab_img[:, :, 1] - 128.0
        lab_img[:, :, 2] = lab_img[:, :, 2] - 128.0

        if mask is not None:
            pixels = lab_img[mask > 0]
        else:
            pixels = lab_img.reshape(-1, 3)
            # Remove near-black pixels (background)
            pixels = pixels[pixels[:, 0] > 5]

        if len(pixels) < 10:
            return LABColor(0, 0, 0), 0.0

        mean_lab = pixels.mean(axis=0)
        variance = float(pixels.var(axis=0).mean())
        return LABColor(float(mean_lab[0]), float(mean_lab[1]), float(mean_lab[2])), variance

    @staticmethod
    def _dominant_hex(roi: np.ndarray, mask: Optional[np.ndarray]) -> str:
        """Return hex string of the dominant BGR colour in masked region."""
        if mask is not None:
            pixels = roi[mask > 0]
        else:
            pixels = roi.reshape(-1, 3)
        if len(pixels) == 0:
            return "#000000"
        # Use median as a robust "dominant" estimate
        med = np.median(pixels, axis=0).astype(int)
        b, g, r = int(med[0]), int(med[1]), int(med[2])
        return f"#{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def _build_display(
        frame: np.ndarray,
        roi_rect: Tuple[int, int, int, int],
        contours: list,
        result: ClassificationResult,
        refl_pct: float,
    ) -> np.ndarray:
        """
        Overlay ROI box, contours, and a minimal HUD on the raw frame.
        Returns a copy suitable for display.
        """
        display = frame.copy()
        rx, ry, rw, rh = roi_rect

        # Verdict colour
        if result.verdict == "PASS":
            vclr = (0, 230, 118)       # green
        elif result.verdict == "FAIL":
            vclr = (60, 61, 255)       # red (BGR)
        else:
            vclr = (0, 200, 255)       # cyan

        # ROI rectangle
        cv2.rectangle(display, (rx, ry), (rx+rw, ry+rh), vclr, 2)

        # Corner ticks for industrial feel
        tick = 12
        for px, py in [(rx, ry), (rx+rw, ry), (rx, ry+rh), (rx+rw, ry+rh)]:
            dx = -tick if px == rx+rw else tick
            dy = -tick if py == ry+rh else tick
            cv2.line(display, (px, py), (px+dx, py),   vclr, 3)
            cv2.line(display, (px, py), (px, py+dy),   vclr, 3)

        # Contours inside ROI
        if contours:
            offset_contours = [c + np.array([[[rx, ry]]]) for c in contours]
            cv2.drawContours(display, offset_contours, -1, (0, 255, 255), 1)

        # Reflection highlight overlay — faint orange tint over bright spots
        if refl_pct > 1.0:
            roi_area  = display[ry:ry+rh, rx:rx+rw]
            gray      = cv2.cvtColor(roi_area, cv2.COLOR_BGR2GRAY)
            _, hmask  = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            overlay   = roi_area.copy()
            overlay[hmask > 0] = (0, 128, 255)   # orange in BGR
            cv2.addWeighted(overlay, 0.3, roi_area, 0.7, 0, dst=roi_area)

        # Mini HUD label
        label_text = f"{result.label}  dE:{result.delta_e2000:.2f}"
        cv2.putText(
            display, label_text, (rx, max(ry - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, vclr, 1, cv2.LINE_AA
        )

        return display
