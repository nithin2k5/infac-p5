"""
INFAC-P5 — gui/dashboard.py
Main application window — assembles all panels and wires all callbacks.
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from typing import Optional
import os

import cv2
import numpy as np
from PIL import Image, ImageTk

from app.utils.constants import (
    APP_NAME, APP_VERSION, APP_SUBTITLE, COMPANY_NAME,
    CLR_BG, CLR_PANEL, CLR_SURFACE, CLR_BORDER,
    CLR_ACCENT, CLR_TEXT, CLR_TEXT_DIM, CLR_PASS, CLR_FAIL,
    FONT_UI, FONT_MONO,
    WINDOW_MIN_W, WINDOW_MIN_H, WINDOW_START_W, WINDOW_START_H,
    UI_UPDATE_INTERVAL_MS,
)
from app.camera.capture import CameraCapture
from app.processing.pipeline import InspectionPipeline, ProcessedFrame
from app.classification.classifier import ColorClassifier
from app.gui.panels.left_panel   import LeftPanel
from app.gui.panels.center_panel import CenterPanel
from app.gui.panels.right_panel  import RightPanel
from app.gui.panels.bottom_bar   import BottomBar

logger = logging.getLogger(__name__)


class InspectionDashboard(tk.Tk):
    """
    Root Tk window.  Wires camera → pipeline → UI.
    """

    def __init__(self):
        super().__init__()
        self._camera:   Optional[CameraCapture]    = None
        self._pipeline: Optional[InspectionPipeline] = None
        self._classifier = ColorClassifier()

        # Latest processed frame (set from pipeline thread, read in UI thread)
        self._latest_pf: Optional[ProcessedFrame] = None
        self._pf_lock = threading.Lock()

        # Latest raw frame for display when pipeline is paused / idle
        self._latest_raw: Optional[np.ndarray] = None
        self._raw_lock = threading.Lock()

        self._inspecting = False
        self._calib_mode = False

        self._setup_window()
        self._build_title_bar()
        self._build_main_layout()
        self._start_ui_refresh()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry(f"{WINDOW_START_W}x{WINDOW_START_H}")
        self.minsize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.configure(bg=CLR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set icon (if assets/icon.ico exists)
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        try:
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _build_title_bar(self):
        bar = tk.Frame(self, bg=CLR_SURFACE, height=44)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # Brand
        tk.Label(bar, text="⬡  INFAC", font=(*FONT_MONO, 13, "bold"),
            bg=CLR_SURFACE, fg=CLR_ACCENT).pack(side="left", padx=16, pady=8)
        tk.Label(bar, text=APP_SUBTITLE, font=(*FONT_UI, 9),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM).pack(side="left")

        # Separator
        tk.Frame(bar, bg=CLR_BORDER, width=1).pack(side="left", fill="y", pady=8, padx=12)

        # Time
        self._time_lbl = tk.Label(bar, text="", font=(*FONT_MONO, 9),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM)
        self._time_lbl.pack(side="right", padx=16)
        self._update_clock()

        # Company
        tk.Label(bar, text=COMPANY_NAME, font=(*FONT_UI, 8),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM).pack(side="right", padx=8)

        # Thin accent bottom border
        tk.Frame(self, bg=CLR_ACCENT, height=2).pack(fill="x", side="top")

    def _update_clock(self):
        self._time_lbl.config(text=datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))
        self.after(1000, self._update_clock)

    # ── Main layout ───────────────────────────────────────────────────────────

    def _build_main_layout(self):
        # Main content area (above bottom bar)
        content = tk.Frame(self, bg=CLR_BG)
        content.pack(fill="both", expand=True)

        content.columnconfigure(0, weight=3, minsize=480)  # Left
        content.columnconfigure(1, weight=3, minsize=340)  # Centre
        content.columnconfigure(2, weight=2, minsize=300)  # Right
        content.rowconfigure(0, weight=1)

        # Dividers
        def _vdiv(col):
            tk.Frame(content, bg=CLR_BORDER, width=1).grid(
                row=0, column=col, sticky="ns")

        # ── Left panel
        self._left = LeftPanel(
            content,
            on_start_camera   = self._start_camera,
            on_stop_camera    = self._stop_camera,
            on_switch_camera  = self._switch_camera,
            on_snapshot       = self._take_snapshot,
        )
        self._left.grid(row=0, column=0, sticky="nsew", padx=(4, 0))
        _vdiv(1)  # col 1 is divider placeholder — use actual column 2

        # ── Centre panel  (re-index: left=0, div=1, center=2, div=3, right=4)
        content.columnconfigure(0, weight=3, minsize=480)
        content.columnconfigure(2, weight=3, minsize=340)
        content.columnconfigure(4, weight=2, minsize=300)

        tk.Frame(content, bg=CLR_BORDER, width=1).grid(row=0, column=1, sticky="ns")

        self._center = CenterPanel(content)
        self._center.grid(row=0, column=2, sticky="nsew")

        tk.Frame(content, bg=CLR_BORDER, width=1).grid(row=0, column=3, sticky="ns")

        # ── Right panel
        self._right = RightPanel(
            content,
            on_start_inspection  = self._start_inspection,
            on_pause_inspection  = self._pause_inspection,
            on_calibration_toggle= self._toggle_calibration,
            on_threshold_change  = self._update_thresholds,
            on_reflection_change = self._update_reflection,
            on_lab_sensitivity   = self._update_lab_refs,
        )
        self._right.grid(row=0, column=4, sticky="nsew", padx=(0, 4))

        # ── Bottom bar
        self._bottom = BottomBar(self)
        self._bottom.pack(fill="x", side="bottom")
        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", side="bottom")

    # ── Camera control callbacks ───────────────────────────────────────────────

    def _start_camera(self):
        if self._camera and self._camera.is_connected:
            return
        self._camera = CameraCapture(
            camera_index=0,
            on_frame=self._on_raw_frame,
            on_status=self._on_camera_status,
        )
        ok = self._camera.start()
        if not ok:
            messagebox.showerror("Camera Error", "Could not open camera.\nCheck connections.")

    def _stop_camera(self):
        if self._camera:
            self._camera.stop()
            self._camera = None
        self._left.set_camera_status(False)
        self._bottom.set_camera_status(False)

    def _switch_camera(self, idx: int):
        if self._camera:
            self._camera.switch_camera(idx)
            self._left.update_camera_label(idx)
        else:
            self._camera = CameraCapture(
                camera_index=idx,
                on_frame=self._on_raw_frame,
                on_status=self._on_camera_status,
            )
            self._camera.start()

    def _take_snapshot(self):
        frame = None
        if self._camera:
            frame = self._camera.snapshot()
        if frame is None:
            with self._raw_lock:
                frame = self._latest_raw.copy() if self._latest_raw is not None else None
        if frame is None:
            messagebox.showwarning("Snapshot", "No frame available.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.path.expanduser("~"), f"infac_snapshot_{ts}.jpg")
        cv2.imwrite(path, frame)
        messagebox.showinfo("Snapshot Saved", f"Saved to:\n{path}")

    # ── Inspection control callbacks ──────────────────────────────────────────

    def _start_inspection(self):
        if not self._camera or not self._camera.is_connected:
            messagebox.showwarning("No Camera", "Start the camera first.")
            return
        if self._pipeline and self._pipeline.active:
            return
        self._pipeline = InspectionPipeline(
            classifier=self._classifier,
            on_result=self._on_pipeline_result,
        )
        # Apply current UI settings
        ta, tb = self._right.get_thresholds()
        self._classifier.set_thresholds(ta, tb)
        rt, rb = self._right.get_reflection_params()
        self._pipeline.set_reflection_thresh(rt)
        self._pipeline.set_reflection_blend(rb)

        self._pipeline.start()
        self._inspecting = True
        self._bottom.set_state("INSPECTING")
        self._center.set_processing_state("INSPECTING…")
        self._center.set_spinner_active(True)
        logger.info("Inspection started")

    def _pause_inspection(self, paused: bool):
        if self._pipeline:
            if paused:
                self._pipeline.pause()
                self._bottom.set_state("PAUSED")
                self._center.set_processing_state("PAUSED")
                self._center.set_spinner_active(False)
            else:
                self._pipeline.resume()
                self._bottom.set_state("INSPECTING")
                self._center.set_processing_state("INSPECTING…")
                self._center.set_spinner_active(True)

    def _toggle_calibration(self, enabled: bool):
        self._calib_mode = enabled
        state = "CALIBRATING" if enabled else ("INSPECTING" if self._inspecting else "IDLE")
        self._bottom.set_state(state)

    # ── Parameter update callbacks ────────────────────────────────────────────

    def _update_thresholds(self, ta: float, tb: float):
        self._classifier.set_thresholds(ta, tb)

    def _update_reflection(self, thresh: int, blend: float):
        if self._pipeline:
            self._pipeline.set_reflection_thresh(thresh)
            self._pipeline.set_reflection_blend(blend)

    def _update_lab_refs(self, ref_a, ref_b):
        self._classifier.set_reference_a(ref_a)
        self._classifier.set_reference_b(ref_b)

    # ── Camera frame callback (background thread) ─────────────────────────────

    def _on_raw_frame(self, frame: np.ndarray):
        with self._raw_lock:
            self._latest_raw = frame
        if self._pipeline:
            self._pipeline.submit_frame(frame)

    def _on_camera_status(self, status: str):
        online = status == "ONLINE"
        # UI updates must happen on main thread — schedule via after()
        self.after(0, lambda: self._apply_camera_status(online))

    def _apply_camera_status(self, online: bool):
        self._left.set_camera_status(online)
        self._bottom.set_camera_status(online)

    # ── Pipeline result callback (background thread) ──────────────────────────

    def _on_pipeline_result(self, pf: ProcessedFrame):
        with self._pf_lock:
            self._latest_pf = pf

    # ── UI refresh loop (main thread) ─────────────────────────────────────────

    def _start_ui_refresh(self):
        self._refresh_ui()

    def _refresh_ui(self):
        """Called every UI_UPDATE_INTERVAL_MS on the main thread."""
        try:
            self._do_refresh()
        except Exception as exc:
            logger.error("UI refresh error: %s", exc, exc_info=True)
        finally:
            self.after(UI_UPDATE_INTERVAL_MS, self._refresh_ui)

    def _do_refresh(self):
        # Grab latest data
        with self._pf_lock:
            pf = self._latest_pf
            self._latest_pf = None  # consume

        with self._raw_lock:
            raw = self._latest_raw

        # If we have a processed frame — use its annotated display
        if pf is not None:
            self._left.update_frame(pf.display_frame)
            self._center.update_result(pf.result)
            self._center.set_processing_state("INSPECTING…", pf.latency_ms)
            self._bottom.set_latency(pf.latency_ms)
            self._bottom.set_detected_colour(pf.result.dominant_hex)
            self._bottom.set_lighting(pf.lighting_ok)
            self._left.update_reflection(pf.result.reflection_pct)
        elif raw is not None and (not self._inspecting):
            # Show raw frame when not inspecting
            self._left.update_frame(raw)

        # FPS from camera
        if self._camera:
            self._left.update_fps(self._camera.fps)
            self._left.update_frame_count(self._camera.frame_count)
            self._bottom.set_fps(self._camera.fps)

    # ── Window close ─────────────────────────────────────────────────────────

    def _on_close(self):
        if self._pipeline:
            self._pipeline.stop()
        if self._camera:
            self._camera.stop()
        self.destroy()
