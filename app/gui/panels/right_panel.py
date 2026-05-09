"""
INFAC-P5 — gui/panels/right_panel.py
Controls Panel — right column of the dashboard.
"""
from __future__ import annotations
import tkinter as tk
from typing import Optional, Callable

from app.utils.constants import (
    CLR_PANEL, CLR_SURFACE, CLR_ACCENT, CLR_ACCENT2, CLR_PASS, CLR_FAIL, CLR_WARN,
    CLR_TEXT, CLR_TEXT_DIM, FONT_UI, FONT_MONO,
    DEFAULT_REFLECTION_THRESH, DEFAULT_REFLECTION_BLEND,
    DELTA_E_VARIANT_A_MAX, DELTA_E_VARIANT_B_MAX,
    REFERENCE_VARIANT_A_LAB, REFERENCE_VARIANT_B_LAB,
)
from app.gui.widgets import SectionHeader, IndustrialButton, LabelledSlider, Separator


class RightPanel(tk.Frame):
    def __init__(self, parent,
                 on_start_inspection=None, on_pause_inspection=None,
                 on_calibration_toggle=None, on_threshold_change=None,
                 on_reflection_change=None, on_lab_sensitivity=None, **kwargs):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        self._on_start   = on_start_inspection
        self._on_pause   = on_pause_inspection
        self._on_calib   = on_calibration_toggle
        self._on_thresh  = on_threshold_change
        self._on_refl    = on_reflection_change
        self._on_lab     = on_lab_sensitivity
        self._calib_mode = False
        self._paused     = False
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=CLR_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=CLR_PANEL)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")

        def _cfg(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig("inner", width=canvas.winfo_width())

        inner.bind("<Configure>", _cfg)
        canvas.bind("<Configure>", _cfg)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._build_inner(inner)

    def _build_inner(self, p):
        p.columnconfigure(0, weight=1)
        row = 0

        SectionHeader(p, "INSPECTION CONTROL", icon="⬡").grid(
            row=row, column=0, sticky="ew", padx=12, pady=(12, 6)); row += 1

        btn_row = tk.Frame(p, bg=CLR_PANEL)
        btn_row.grid(row=row, column=0, sticky="ew", padx=12); row += 1
        btn_row.columnconfigure((0, 1), weight=1)

        self._btn_inspect = IndustrialButton(
            btn_row, "▶  START INSPECTION", command=self._on_start, accent=CLR_PASS)
        self._btn_inspect.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self._btn_pause = IndustrialButton(
            btn_row, "⏸  PAUSE", command=self._toggle_pause, accent=CLR_WARN)
        self._btn_pause.grid(row=1, column=0, sticky="ew", padx=(0, 4))

        self._btn_calib = IndustrialButton(
            btn_row, "⚙  CALIBRATE", command=self._toggle_calib, accent=CLR_ACCENT2)
        self._btn_calib.grid(row=1, column=1, sticky="ew", padx=(4, 0))

        self._calib_lbl = tk.Label(p, text="● CALIBRATION OFF",
            font=(*FONT_MONO, 9), bg=CLR_PANEL, fg=CLR_TEXT_DIM)
        self._calib_lbl.grid(row=row, column=0, sticky="w", padx=16, pady=4); row += 1

        Separator(p).grid(row=row, column=0, sticky="ew", padx=12, pady=8); row += 1

        # Delta-E thresholds
        SectionHeader(p, "ΔE THRESHOLDS", icon="◈").grid(
            row=row, column=0, sticky="ew", padx=12, pady=(0, 6)); row += 1
        tf = tk.Frame(p, bg=CLR_PANEL)
        tf.grid(row=row, column=0, sticky="ew", padx=12); row += 1
        tf.columnconfigure(0, weight=1)
        self._thresh_a = LabelledSlider(tf, "Variant A max ΔE", 0.5, 5.0,
            DELTA_E_VARIANT_A_MAX, command=self._on_thresh_change)
        self._thresh_a.pack(fill="x", pady=4)
        self._thresh_b = LabelledSlider(tf, "Variant B max ΔE", 1.0, 10.0,
            DELTA_E_VARIANT_B_MAX, command=self._on_thresh_change)
        self._thresh_b.pack(fill="x", pady=4)

        Separator(p).grid(row=row, column=0, sticky="ew", padx=12, pady=8); row += 1

        # Reflection suppression
        SectionHeader(p, "REFLECTION SUPPRESSION", icon="◉").grid(
            row=row, column=0, sticky="ew", padx=12, pady=(0, 6)); row += 1
        rf = tk.Frame(p, bg=CLR_PANEL)
        rf.grid(row=row, column=0, sticky="ew", padx=12); row += 1
        rf.columnconfigure(0, weight=1)
        self._refl_thresh = LabelledSlider(rf, "Highlight Threshold", 180, 255,
            DEFAULT_REFLECTION_THRESH, resolution=1.0,
            command=self._on_refl_change, fmt="{:.0f}")
        self._refl_thresh.pack(fill="x", pady=4)
        self._refl_blend = LabelledSlider(rf, "Blend Strength", 0.0, 1.0,
            DEFAULT_REFLECTION_BLEND, resolution=0.05,
            command=self._on_refl_change, fmt="{:.2f}")
        self._refl_blend.pack(fill="x", pady=4)

        Separator(p).grid(row=row, column=0, sticky="ew", padx=12, pady=8); row += 1

        # LAB sensitivity
        SectionHeader(p, "LAB SENSITIVITY", icon="▣").grid(
            row=row, column=0, sticky="ew", padx=12, pady=(0, 6)); row += 1
        lf = tk.Frame(p, bg=CLR_PANEL)
        lf.grid(row=row, column=0, sticky="ew", padx=12); row += 1
        lf.columnconfigure(0, weight=1)

        tk.Label(lf, text="Reference Variant A (L / a / b)",
            font=(*FONT_UI, 8), bg=CLR_PANEL, fg=CLR_TEXT_DIM).pack(anchor="w", pady=(2,0))
        self._labA_L = LabelledSlider(lf, "L*", 0, 100,
            REFERENCE_VARIANT_A_LAB[0], command=self._on_lab_change)
        self._labA_L.pack(fill="x")
        self._labA_a = LabelledSlider(lf, "a*", -128, 128,
            REFERENCE_VARIANT_A_LAB[1], command=self._on_lab_change, fmt="{:+.1f}")
        self._labA_a.pack(fill="x")
        self._labA_b = LabelledSlider(lf, "b*", -128, 128,
            REFERENCE_VARIANT_A_LAB[2], command=self._on_lab_change, fmt="{:+.1f}")
        self._labA_b.pack(fill="x")

        tk.Label(lf, text="Reference Variant B (L / a / b)",
            font=(*FONT_UI, 8), bg=CLR_PANEL, fg=CLR_TEXT_DIM).pack(anchor="w", pady=(8,0))
        self._labB_L = LabelledSlider(lf, "L*", 0, 100,
            REFERENCE_VARIANT_B_LAB[0], command=self._on_lab_change)
        self._labB_L.pack(fill="x")
        self._labB_a = LabelledSlider(lf, "a*", -128, 128,
            REFERENCE_VARIANT_B_LAB[1], command=self._on_lab_change, fmt="{:+.1f}")
        self._labB_a.pack(fill="x")
        self._labB_b = LabelledSlider(lf, "b*", -128, 128,
            REFERENCE_VARIANT_B_LAB[2], command=self._on_lab_change, fmt="{:+.1f}")
        self._labB_b.pack(fill="x")

        Separator(p).grid(row=row, column=0, sticky="ew", padx=12, pady=8); row += 1

        # Advanced placeholders
        SectionHeader(p, "ADVANCED / FUTURE", icon="⬡").grid(
            row=row, column=0, sticky="ew", padx=12, pady=(0, 6)); row += 1
        adv = tk.Frame(p, bg=CLR_PANEL)
        adv.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 12)); row += 1
        adv.columnconfigure(0, weight=1)

        for label, clr in [
            ("🤖  AI Model Integration", CLR_ACCENT2),
            ("📷  Multi-Camera Support",  CLR_ACCENT),
            ("🏭  PLC Communication",      CLR_WARN),
            ("⚡  GPIO Trigger",           CLR_WARN),
            ("📡  Industrial Camera SDK",  CLR_ACCENT2),
        ]:
            row_f = tk.Frame(adv, bg=CLR_SURFACE, pady=4)
            row_f.pack(fill="x", pady=2)
            tk.Label(row_f, text=label, font=(*FONT_UI, 9),
                bg=CLR_SURFACE, fg=clr).pack(side="left", padx=10)
            tk.Label(row_f, text="[PLACEHOLDER]", font=(*FONT_UI, 7),
                bg=CLR_SURFACE, fg=CLR_TEXT_DIM).pack(side="right", padx=10)

    # Getters
    def get_thresholds(self):
        return self._thresh_a.get(), self._thresh_b.get()
    def get_reflection_params(self):
        return int(self._refl_thresh.get()), self._refl_blend.get()
    def get_ref_a_lab(self):
        return (self._labA_L.get(), self._labA_a.get(), self._labA_b.get())
    def get_ref_b_lab(self):
        return (self._labB_L.get(), self._labB_a.get(), self._labB_b.get())

    # Callbacks
    def _toggle_calib(self):
        self._calib_mode = not self._calib_mode
        self._calib_lbl.config(
            text="● CALIBRATION ON" if self._calib_mode else "● CALIBRATION OFF",
            fg=CLR_WARN if self._calib_mode else CLR_TEXT_DIM)
        if self._on_calib:
            self._on_calib(self._calib_mode)

    def _toggle_pause(self):
        self._paused = not self._paused
        self._btn_pause.config(text="▶  RESUME" if self._paused else "⏸  PAUSE")
        if self._on_pause:
            self._on_pause(self._paused)

    def _on_thresh_change(self, _=None):
        if self._on_thresh:
            self._on_thresh(*self.get_thresholds())

    def _on_refl_change(self, _=None):
        if self._on_refl:
            self._on_refl(*self.get_reflection_params())

    def _on_lab_change(self, _=None):
        if self._on_lab:
            self._on_lab(self.get_ref_a_lab(), self.get_ref_b_lab())
