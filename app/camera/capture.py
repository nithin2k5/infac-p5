"""
INFAC-P5 — camera/capture.py
Threaded OpenCV camera capture with hot-swap and snapshot support.
"""

from __future__ import annotations

import threading
import time
import logging
from typing import Optional, Callable

import cv2
import numpy as np

from app.utils.constants import (
    DEFAULT_CAMERA_INDEX, TARGET_FPS, FRAME_W, FRAME_H, CAMERA_TIMEOUT,
)

logger = logging.getLogger(__name__)


class CameraCapture:
    """
    Thread-safe webcam capture.

    Usage
    -----
    cam = CameraCapture(on_frame=my_callback)
    cam.start()
    ...
    cam.stop()
    """

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        on_frame: Optional[Callable[[np.ndarray], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.camera_index  = camera_index
        self.on_frame      = on_frame
        self.on_status     = on_status

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running   = threading.Event()
        self._lock      = threading.Lock()

        # Metrics
        self.fps: float    = 0.0
        self.frame_count   = 0
        self.last_frame: Optional[np.ndarray] = None
        self.is_connected  = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        if self._running.is_set():
            return True
        ok = self._open_camera(self.camera_index)
        if not ok:
            self._emit_status("OFFLINE")
            return False
        self._running.set()
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="CameraCapture"
        )
        self._thread.start()
        self._emit_status("ONLINE")
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._release()
        self.is_connected = False
        self._emit_status("OFFLINE")

    def switch_camera(self, index: int) -> bool:
        was_running = self._running.is_set()
        self.stop()
        self.camera_index = index
        if was_running:
            return self.start()
        return True

    def snapshot(self) -> Optional[np.ndarray]:
        """Return a copy of the latest frame (thread-safe)."""
        with self._lock:
            if self.last_frame is not None:
                return self.last_frame.copy()
        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _open_camera(self, index: int) -> bool:
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            logger.warning("Cannot open camera %d", index)
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        cap.set(cv2.CAP_PROP_FPS,          TARGET_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)           # low-latency
        with self._lock:
            self._cap = cap
        self.is_connected = True
        return True

    def _release(self) -> None:
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None

    def _capture_loop(self) -> None:
        fps_timer  = time.perf_counter()
        fps_frames = 0
        interval   = 1.0 / TARGET_FPS

        while self._running.is_set():
            t0 = time.perf_counter()

            with self._lock:
                cap = self._cap

            if cap is None:
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret:
                logger.warning("Camera read failed — retrying")
                time.sleep(0.1)
                continue

            # Resize to standard dimensions
            frame = cv2.resize(frame, (FRAME_W, FRAME_H))

            with self._lock:
                self.last_frame = frame
                self.frame_count += 1

            # FPS calculation
            fps_frames += 1
            elapsed = time.perf_counter() - fps_timer
            if elapsed >= 1.0:
                self.fps = fps_frames / elapsed
                fps_frames = 0
                fps_timer  = time.perf_counter()

            # Fire callback
            if self.on_frame:
                try:
                    self.on_frame(frame.copy())
                except Exception as exc:
                    logger.error("on_frame callback error: %s", exc)

            # Pace to target FPS
            elapsed_frame = time.perf_counter() - t0
            sleep_t = interval - elapsed_frame
            if sleep_t > 0:
                time.sleep(sleep_t)

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            try:
                self.on_status(status)
            except Exception as exc:
                logger.error("on_status callback error: %s", exc)

    # ── Context-manager support ───────────────────────────────────────────────

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
