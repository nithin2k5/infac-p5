"""
INFAC-P5 — gui/panels/left_panel.py
Live camera feed panel — left column of the dashboard.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from PIL import Image, ImageTk
import numpy as np
import cv2

from app.utils.constants import (
    CLR_BG, CLR_PANEL, CLR_SURFACE, CLR_BORDER,
    CLR_ACCENT, CLR_ACCENT2, CLR_TEXT, CLR_TEXT_DIM, CLR_PASS, CLR_FAIL, CLR_WARN,
    FONT_UI, FONT_MONO, FRAME_W, FRAME_H,
)
from app.gui.widgets import (
    SectionHeader, IndustrialButton, StatusCard, Separator,
)


class LeftPanel(tk.Frame):
    """
    Left panel: live camera feed + camera controls.
    """

    PREVIEW_W = 480
    PREVIEW_H = 360

    def __init__(
        self,
        parent,
        on_start_camera:  Optional[Callable] = None,
        on_stop_camera:   Optional[Callable] = None,
        on_switch_camera: Optional[Callable] = None,
        on_snapshot:      Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        self._on_start   = on_start_camera
        self._on_stop    = on_stop_camera
        self._on_switch  = on_switch_camera
        self._on_snapshot= on_snapshot
        self._camera_idx = 0
        self._photo_ref: Optional[ImageTk.PhotoImage] = None

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)

        # ── Header
        SectionHeader(self, "LIVE CAMERA FEED", icon="⬡").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 4)
        )

        # ── Camera canvas
        canvas_frame = tk.Frame(self, bg=CLR_BORDER, bd=1, relief="flat")
        canvas_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=0)

        self._canvas = tk.Canvas(
            canvas_frame,
            width=self.PREVIEW_W, height=self.PREVIEW_H,
            bg="#000000", highlightthickness=0,
        )
        self._canvas.pack()
        self._draw_offline_screen()

        # ── FPS / camera index overlay strip
        info_row = tk.Frame(self, bg=CLR_SURFACE)
        info_row.grid(row=2, column=0, sticky="ew", padx=12, pady=0)

        self._fps_lbl = tk.Label(
            info_row, text="FPS: —",
            font=(*FONT_MONO, 9), bg=CLR_SURFACE, fg=CLR_ACCENT,
        )
        self._fps_lbl.pack(side="left", padx=10, pady=4)

        self._cam_lbl = tk.Label(
            info_row, text="CAM: 0",
            font=(*FONT_MONO, 9), bg=CLR_SURFACE, fg=CLR_TEXT_DIM,
        )
        self._cam_lbl.pack(side="left", padx=10)

        self._res_lbl = tk.Label(
            info_row, text=f"{FRAME_W}×{FRAME_H}",
            font=(*FONT_MONO, 9), bg=CLR_SURFACE, fg=CLR_TEXT_DIM,
        )
        self._res_lbl.pack(side="right", padx=10)

        Separator(self, horizontal=True).grid(row=3, column=0, sticky="ew", padx=12, pady=6)

        # ── Camera controls
        SectionHeader(self, "CAMERA CONTROLS", icon="⚙").grid(
            row=4, column=0, sticky="ew", padx=12, pady=(0, 6)
        )

        btn_grid = tk.Frame(self, bg=CLR_PANEL)
        btn_grid.grid(row=5, column=0, sticky="ew", padx=12)
        btn_grid.columnconfigure((0, 1), weight=1)

        self._btn_start = IndustrialButton(
            btn_grid, "▶  START",
            command=self._on_start, accent=CLR_PASS,
        )
        self._btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=3)

        self._btn_stop = IndustrialButton(
            btn_grid, "■  STOP",
            command=self._on_stop, accent=CLR_FAIL,
        )
        self._btn_stop.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=3)

        self._btn_switch = IndustrialButton(
            btn_grid, "⇄  SWITCH CAM",
            command=self._do_switch_camera,
        )
        self._btn_switch.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=3)

        self._btn_snap = IndustrialButton(
            btn_grid, "📷  SNAPSHOT",
            command=self._on_snapshot, accent=CLR_WARN,
        )
        self._btn_snap.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=3)

        # ── Camera index selector
        idx_row = tk.Frame(self, bg=CLR_PANEL)
        idx_row.grid(row=6, column=0, sticky="ew", padx=12, pady=(8, 6))
        tk.Label(
            idx_row, text="Camera index:",
            font=(*FONT_UI, 9), bg=CLR_PANEL, fg=CLR_TEXT_DIM,
        ).pack(side="left")
        self._cam_idx_var = tk.IntVar(value=0)
        for i in range(4):
            tk.Radiobutton(
                idx_row, text=str(i), variable=self._cam_idx_var, value=i,
                font=(*FONT_UI, 9), bg=CLR_PANEL, fg=CLR_TEXT,
                selectcolor=CLR_SURFACE, activebackground=CLR_PANEL,
            ).pack(side="left", padx=6)

        # ── Stats cards at bottom
        stats_frame = tk.Frame(self, bg=CLR_PANEL)
        stats_frame.grid(row=7, column=0, sticky="ew", padx=12, pady=8)
        stats_frame.columnconfigure((0, 1), weight=1)

        self._frame_card = StatusCard(
            stats_frame, "FRAME COUNT", "0",
            accent=CLR_ACCENT2, value_font_size=16,
        )
        self._frame_card.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._refl_card = StatusCard(
            stats_frame, "REFLECTION %", "0.0",
            accent=CLR_WARN, value_font_size=16,
        )
        self._refl_card.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    # ── Public update methods ─────────────────────────────────────────────────

    def update_frame(self, bgr_frame: np.ndarray):
        """Render a BGR OpenCV frame onto the canvas."""
        frame_rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img = img.resize((self.PREVIEW_W, self.PREVIEW_H), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(img)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo_ref)

    def update_fps(self, fps: float):
        self._fps_lbl.config(text=f"FPS: {fps:.1f}")

    def update_camera_label(self, idx: int):
        self._cam_lbl.config(text=f"CAM: {idx}")

    def update_frame_count(self, count: int):
        self._frame_card.set_value(str(count))

    def update_reflection(self, pct: float):
        self._refl_card.set_value(f"{pct:.1f}")

    def set_camera_status(self, online: bool):
        if online:
            self._canvas.config(bg="#050810")
        else:
            self._draw_offline_screen()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _draw_offline_screen(self):
        self._canvas.delete("all")
        self._canvas.create_rectangle(
            0, 0, self.PREVIEW_W, self.PREVIEW_H, fill="#050810"
        )
        self._canvas.create_text(
            self.PREVIEW_W // 2, self.PREVIEW_H // 2 - 20,
            text="⬡", font=("Arial", 40), fill=CLR_BORDER,
        )
        self._canvas.create_text(
            self.PREVIEW_W // 2, self.PREVIEW_H // 2 + 28,
            text="NO SIGNAL", font=(*FONT_MONO, 14, "bold"), fill=CLR_BORDER,
        )

    def _do_switch_camera(self):
        idx = self._cam_idx_var.get()
        if self._on_switch:
            self._on_switch(idx)
