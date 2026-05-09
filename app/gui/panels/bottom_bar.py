"""
INFAC-P5 — gui/panels/bottom_bar.py
Bottom status bar — live system metrics.
"""
from __future__ import annotations
import tkinter as tk
import time

from app.utils.constants import (
    CLR_BG, CLR_SURFACE, CLR_BORDER, CLR_ACCENT, CLR_ACCENT2,
    CLR_PASS, CLR_FAIL, CLR_WARN, CLR_TEXT, CLR_TEXT_DIM, FONT_UI, FONT_MONO,
)


class _Metric(tk.Frame):
    """Small label + value block for the status bar."""
    def __init__(self, parent, label: str, value: str = "—", clr=None, **kwargs):
        clr = clr or CLR_ACCENT
        super().__init__(parent, bg=CLR_SURFACE, padx=14, pady=4, **kwargs)
        tk.Label(self, text=label, font=(*FONT_UI, 7, "bold"),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM).pack(anchor="w")
        self._val = tk.Label(self, text=value, font=(*FONT_MONO, 10, "bold"),
            bg=CLR_SURFACE, fg=clr)
        self._val.pack(anchor="w")

    def set(self, value: str, clr=None):
        cfg = {"text": value}
        if clr:
            cfg["fg"] = clr
        self._val.config(**cfg)


class BottomBar(tk.Frame):
    """Horizontal status bar — camera, FPS, latency, colour, state, lighting."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CLR_SURFACE, height=60, **kwargs)
        self.pack_propagate(False)
        self._build()
        self._start_time = time.time()
        self._tick()

    def _build(self):
        # Left logo
        tk.Label(self, text="  INFAC  ", font=(*FONT_MONO, 11, "bold"),
            bg=CLR_SURFACE, fg=CLR_ACCENT).pack(side="left", padx=4)

        sep = tk.Frame(self, bg=CLR_BORDER, width=1)
        sep.pack(side="left", fill="y", pady=6, padx=4)

        self._cam_metric      = _Metric(self, "CAMERA STATUS", "OFFLINE", CLR_FAIL)
        self._fps_metric      = _Metric(self, "FPS", "—")
        self._latency_metric  = _Metric(self, "LATENCY", "— ms", CLR_ACCENT2)
        self._colour_metric   = _Metric(self, "DETECTED COLOUR", "#------")
        self._state_metric    = _Metric(self, "SYSTEM STATE", "IDLE", CLR_WARN)
        self._lighting_metric = _Metric(self, "LIGHTING", "—", CLR_PASS)

        for m in [self._cam_metric, self._fps_metric, self._latency_metric,
                  self._colour_metric, self._state_metric, self._lighting_metric]:
            m.pack(side="left")
            tk.Frame(self, bg=CLR_BORDER, width=1).pack(side="left", fill="y", pady=6)

        # Right: uptime
        self._uptime_lbl = tk.Label(self, text="UP: 00:00:00",
            font=(*FONT_MONO, 9), bg=CLR_SURFACE, fg=CLR_TEXT_DIM)
        self._uptime_lbl.pack(side="right", padx=16)

        # Version
        tk.Label(self, text="v1.0.0", font=(*FONT_UI, 8),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM).pack(side="right", padx=8)

    def _tick(self):
        elapsed = int(time.time() - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self._uptime_lbl.config(text=f"UP: {h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._tick)

    # Public update methods
    def set_camera_status(self, online: bool):
        self._cam_metric.set("ONLINE" if online else "OFFLINE",
                             CLR_PASS if online else CLR_FAIL)

    def set_fps(self, fps: float):
        self._fps_metric.set(f"{fps:.1f}")

    def set_latency(self, ms: float):
        clr = CLR_PASS if ms < 50 else (CLR_WARN if ms < 100 else CLR_FAIL)
        self._latency_metric.set(f"{ms:.1f} ms", clr)

    def set_detected_colour(self, hex_str: str):
        self._colour_metric.set(hex_str)

    def set_state(self, state: str):
        clr = CLR_PASS if state == "INSPECTING" else (CLR_WARN if state == "CALIBRATING" else CLR_TEXT_DIM)
        self._state_metric.set(state, clr)

    def set_lighting(self, ok: bool):
        self._lighting_metric.set("OK ✓" if ok else "WARN !", CLR_PASS if ok else CLR_WARN)
