"""
INFAC-P5 — gui/panels/center_panel.py
Inspection Analysis Panel — centre column of the dashboard.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from app.utils.constants import (
    CLR_BG, CLR_PANEL, CLR_SURFACE, CLR_BORDER,
    CLR_ACCENT, CLR_ACCENT2, CLR_PASS, CLR_FAIL, CLR_WARN,
    CLR_TEXT, CLR_TEXT_DIM,
    FONT_UI, FONT_MONO,
)
from app.gui.widgets import (
    SectionHeader, StatusCard, ConfidenceMeter, StatusBadge,
    LABBar, DeltaEGauge, ScannerSpinner, Separator,
)
from app.classification.classifier import ClassificationResult


class CenterPanel(tk.Frame):
    """
    Centre panel: classification result, PASS/FAIL badge, confidence meter,
    DeltaE gauge, LAB readouts, and live processing state.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)

        # ── Header
        SectionHeader(self, "INSPECTION ANALYSIS", icon="◈").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 6)
        )

        # ── PASS/FAIL Badge
        self._badge = StatusBadge(self)
        self._badge.grid(row=1, column=0, pady=(0, 8))

        # ── Classification label
        clf_frame = tk.Frame(self, bg=CLR_SURFACE, padx=12, pady=8)
        clf_frame.grid(row=2, column=0, sticky="ew", padx=12)
        clf_frame.columnconfigure(0, weight=1)

        tk.Label(
            clf_frame, text="CLASSIFICATION",
            font=(*FONT_UI, 8, "bold"), bg=CLR_SURFACE, fg=CLR_TEXT_DIM,
        ).pack(anchor="w")

        self._class_lbl = tk.Label(
            clf_frame, text="— Awaiting —",
            font=(*FONT_MONO, 18, "bold"), bg=CLR_SURFACE, fg=CLR_ACCENT,
        )
        self._class_lbl.pack(anchor="w", pady=(2, 0))

        Separator(self, horizontal=True).grid(row=3, column=0, sticky="ew", padx=12, pady=8)

        # ── Confidence meter + DeltaE gauge side-by-side
        meter_row = tk.Frame(self, bg=CLR_PANEL)
        meter_row.grid(row=4, column=0, sticky="ew", padx=12)
        meter_row.columnconfigure((0, 1), weight=1)

        conf_frame = tk.Frame(meter_row, bg=CLR_PANEL)
        conf_frame.grid(row=0, column=0, sticky="ew", pady=4)
        self._conf_meter = ConfidenceMeter(conf_frame, bg=CLR_SURFACE)
        self._conf_meter.pack()

        de_frame = tk.Frame(meter_row, bg=CLR_PANEL)
        de_frame.grid(row=0, column=1, sticky="ew", pady=4)
        tk.Label(
            de_frame, text="ΔE 2000",
            font=(*FONT_UI, 9, "bold"), bg=CLR_PANEL, fg=CLR_TEXT_DIM,
        ).pack(anchor="w", padx=4)
        self._de_gauge = DeltaEGauge(de_frame, bg=CLR_SURFACE)
        self._de_gauge.pack(pady=(4, 0))

        self._de_lbl = tk.Label(
            de_frame, text="0.000",
            font=(*FONT_MONO, 16, "bold"), bg=CLR_PANEL, fg=CLR_WARN,
        )
        self._de_lbl.pack(pady=(4, 0))

        tk.Label(
            de_frame, text="ΔE76:",
            font=(*FONT_UI, 8), bg=CLR_PANEL, fg=CLR_TEXT_DIM,
        ).pack(anchor="w", padx=4)
        self._de76_lbl = tk.Label(
            de_frame, text="0.000",
            font=(*FONT_MONO, 12), bg=CLR_PANEL, fg=CLR_TEXT_DIM,
        )
        self._de76_lbl.pack(anchor="w", padx=4)

        Separator(self, horizontal=True).grid(row=5, column=0, sticky="ew", padx=12, pady=8)

        # ── LAB Channels
        SectionHeader(self, "LAB COLOUR VALUES", icon="◉").grid(
            row=6, column=0, sticky="ew", padx=12, pady=(0, 4)
        )

        lab_frame = tk.Frame(self, bg=CLR_SURFACE)
        lab_frame.grid(row=7, column=0, sticky="ew", padx=12)
        lab_frame.columnconfigure(0, weight=1)

        self._bar_L = LABBar(lab_frame, "L*",   0,   100)
        self._bar_L.pack(fill="x", pady=2)
        self._bar_a = LABBar(lab_frame, "a*", -128, +128)
        self._bar_a.pack(fill="x", pady=2)
        self._bar_b = LABBar(lab_frame, "b*", -128, +128)
        self._bar_b.pack(fill="x", pady=2)

        Separator(self, horizontal=True).grid(row=8, column=0, sticky="ew", padx=12, pady=8)

        # ── Stats cards row
        stats_row = tk.Frame(self, bg=CLR_PANEL)
        stats_row.grid(row=9, column=0, sticky="ew", padx=12)
        stats_row.columnconfigure((0, 1), weight=1)

        self._var_card = StatusCard(
            stats_row, "PIXEL VARIANCE", "0.00",
            accent=CLR_ACCENT2, value_font_size=14,
        )
        self._var_card.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)

        self._dom_card = StatusCard(
            stats_row, "DOMINANT HEX", "#------",
            accent=CLR_ACCENT, value_font_size=14,
        )
        self._dom_card.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=2)

        Separator(self, horizontal=True).grid(row=10, column=0, sticky="ew", padx=12, pady=8)

        # ── Processing status row
        proc_row = tk.Frame(self, bg=CLR_PANEL)
        proc_row.grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._spinner = ScannerSpinner(proc_row, size=30)
        self._spinner.grid(row=0, column=0, padx=(0, 8))
        self._spinner.start()

        proc_text_col = tk.Frame(proc_row, bg=CLR_PANEL)
        proc_text_col.grid(row=0, column=1, sticky="w")
        self._proc_lbl = tk.Label(
            proc_text_col, text="PROCESSING…",
            font=(*FONT_MONO, 10, "bold"), bg=CLR_PANEL, fg=CLR_ACCENT,
        )
        self._proc_lbl.pack(anchor="w")
        self._latency_lbl = tk.Label(
            proc_text_col, text="Latency: — ms",
            font=(*FONT_UI, 8), bg=CLR_PANEL, fg=CLR_TEXT_DIM,
        )
        self._latency_lbl.pack(anchor="w")

    # ── Public update API ─────────────────────────────────────────────────────

    def update_result(self, result: ClassificationResult):
        # Badge
        self._badge.set_verdict(result.verdict)

        # Classification label + colour
        clr = CLR_PASS if result.verdict == "PASS" else CLR_FAIL
        self._class_lbl.config(text=result.label, fg=clr)

        # Confidence meter
        self._conf_meter.set_value(result.confidence)

        # DeltaE
        self._de_gauge.set_value(result.delta_e2000)
        de_clr = CLR_PASS if result.delta_e2000 < 2 else (CLR_WARN if result.delta_e2000 < 5 else CLR_FAIL)
        self._de_lbl.config(text=f"{result.delta_e2000:.3f}", fg=de_clr)
        self._de76_lbl.config(text=f"{result.delta_e76:.3f}")

        # LAB bars
        self._bar_L.set_value(result.lab.L)
        self._bar_a.set_value(result.lab.a)
        self._bar_b.set_value(result.lab.b)

        # Stats
        self._var_card.set_value(f"{result.pixel_variance:.2f}")
        self._dom_card.set_value(result.dominant_hex)

    def set_processing_state(self, label: str, latency_ms: Optional[float] = None):
        self._proc_lbl.config(text=label)
        if latency_ms is not None:
            self._latency_lbl.config(text=f"Latency: {latency_ms:.1f} ms")

    def set_spinner_active(self, active: bool):
        if active:
            self._spinner.start()
        else:
            self._spinner.stop()
