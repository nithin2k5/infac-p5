"""
INFAC-P5 — gui/widgets.py
Reusable industrial Tkinter widgets used across the dashboard.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Optional

from app.utils.constants import (
    CLR_BG, CLR_PANEL, CLR_SURFACE, CLR_BORDER,
    CLR_ACCENT, CLR_ACCENT2, CLR_PASS, CLR_FAIL, CLR_WARN,
    CLR_TEXT, CLR_TEXT_DIM, CLR_TEXT_MUTED,
    FONT_UI, FONT_MONO,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


# ── Status Card ───────────────────────────────────────────────────────────────

class StatusCard(tk.Frame):
    """
    Raised card widget that shows a title, a large value label, and an
    optional sub-label.
    """

    def __init__(
        self,
        parent,
        title: str,
        value: str = "—",
        sub: str = "",
        accent: str = CLR_ACCENT,
        value_font_size: int = 22,
        **kwargs,
    ):
        super().__init__(
            parent,
            bg=CLR_SURFACE,
            relief="flat",
            bd=0,
            **kwargs,
        )
        self._accent = accent
        self._draw_border()

        tk.Label(
            self, text=title.upper(), font=(*FONT_UI, 8, "bold"),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM,
        ).pack(anchor="w", padx=12, pady=(10, 0))

        self._val_lbl = tk.Label(
            self, text=value,
            font=(*FONT_MONO, value_font_size, "bold"),
            bg=CLR_SURFACE, fg=accent,
        )
        self._val_lbl.pack(anchor="w", padx=12, pady=(2, 0))

        self._sub_lbl = tk.Label(
            self, text=sub, font=(*FONT_UI, 9),
            bg=CLR_SURFACE, fg=CLR_TEXT_DIM,
        )
        self._sub_lbl.pack(anchor="w", padx=12, pady=(0, 10))

    def _draw_border(self):
        """Thin left-side accent strip."""
        strip = tk.Frame(self, bg=self._accent, width=3)
        strip.place(relx=0, rely=0, relheight=1)

    def set_value(self, value: str, color: Optional[str] = None):
        self._val_lbl.config(text=value)
        if color:
            self._val_lbl.config(fg=color)

    def set_sub(self, sub: str):
        self._sub_lbl.config(text=sub)


# ── Confidence Meter (Canvas arc) ─────────────────────────────────────────────

class ConfidenceMeter(tk.Canvas):
    """
    Circular arc-based confidence indicator.
    0–100 % mapped to an arc from 210° to -30° (240° sweep).
    """

    SIZE = 160

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent, width=self.SIZE, height=self.SIZE,
            bg=CLR_SURFACE, highlightthickness=0,
        )
        self._value = 0.0
        self._anim_value = 0.0
        self._draw()

    def _draw(self):
        self.delete("all")
        cx = cy = self.SIZE / 2
        r  = self.SIZE / 2 - 14
        x0, y0, x1, y1 = cx-r, cy-r, cx+r, cy+r

        # Background track
        self.create_arc(
            x0, y0, x1, y1,
            start=210, extent=-240,
            outline=CLR_BORDER, width=10,
            style="arc",
        )

        # Coloured value arc
        t = self._anim_value / 100.0
        arc_color = _lerp_color(CLR_FAIL, CLR_PASS, t)
        extent = -t * 240
        if abs(extent) > 0.5:
            self.create_arc(
                x0, y0, x1, y1,
                start=210, extent=extent,
                outline=arc_color, width=10,
                style="arc",
            )

        # Centre text
        self.create_text(
            cx, cy - 6,
            text=f"{self._anim_value:.0f}",
            font=(*FONT_MONO, 26, "bold"),
            fill=arc_color,
        )
        self.create_text(
            cx, cy + 20,
            text="CONFIDENCE %",
            font=(*FONT_UI, 7),
            fill=CLR_TEXT_DIM,
        )

    def set_value(self, value: float):
        self._value = max(0.0, min(100.0, value))
        self._animate_to(self._value)

    def _animate_to(self, target: float, steps: int = 6):
        delta = (target - self._anim_value) / steps

        def step(remaining):
            if remaining <= 0:
                self._anim_value = target
                self._draw()
                return
            self._anim_value += delta
            self._draw()
            self.after(16, lambda: step(remaining - 1))

        step(steps)


# ── Animated Status Badge ─────────────────────────────────────────────────────

class StatusBadge(tk.Frame):
    """
    Large 'PASS' / 'FAIL' / 'PROCESSING' badge with animated glow pulse.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        self._verdict    = "PROCESSING"
        self._pulse_dir  = 1
        self._pulse_val  = 0.0
        self._anim_id    = None

        self._canvas = tk.Canvas(
            self, width=240, height=80,
            bg=CLR_PANEL, highlightthickness=0,
        )
        self._canvas.pack()
        self._draw()
        self._start_pulse()

    # ── colour mapping ────────────────────────────────────────────────────────

    def _verdict_color(self) -> str:
        if self._verdict == "PASS":
            return CLR_PASS
        elif self._verdict == "FAIL":
            return CLR_FAIL
        return CLR_WARN

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self._canvas.delete("all")
        clr  = self._verdict_color()
        alpha = 0.15 + self._pulse_val * 0.25

        # Outer glow rectangle (simulated with nested rects)
        for i in range(5, 0, -1):
            glow_clr = _lerp_color(CLR_PANEL, clr, alpha * i / 5)
            self._canvas.create_rectangle(
                20 - i*2, 8 - i*2, 220 + i*2, 72 + i*2,
                fill=glow_clr, outline="", tags="glow",
            )

        # Main badge
        self._canvas.create_rectangle(
            20, 8, 220, 72,
            fill=CLR_SURFACE, outline=clr, width=2,
            tags="badge",
        )

        # Verdict text
        self._canvas.create_text(
            120, 40,
            text=self._verdict,
            font=(*FONT_MONO, 24, "bold"),
            fill=clr,
            tags="text",
        )

    # ── Pulse animation ───────────────────────────────────────────────────────

    def _start_pulse(self):
        self._pulse_val += 0.05 * self._pulse_dir
        if self._pulse_val >= 1.0:
            self._pulse_dir = -1
        elif self._pulse_val <= 0.0:
            self._pulse_dir = 1
        self._draw()
        speed = 50 if self._verdict == "FAIL" else 80
        self._anim_id = self.after(speed, self._start_pulse)

    def set_verdict(self, verdict: str):
        self._verdict = verdict
        self._draw()


# ── LAB Colour Bar ────────────────────────────────────────────────────────────

class LABBar(tk.Frame):
    """Horizontal bar visualising a LAB channel value."""

    def __init__(self, parent, channel: str, lo: float, hi: float, **kwargs):
        super().__init__(parent, bg=CLR_SURFACE, **kwargs)
        self.channel = channel
        self.lo      = lo
        self.hi      = hi

        tk.Label(
            self, text=channel, width=3,
            font=(*FONT_MONO, 9, "bold"),
            bg=CLR_SURFACE, fg=CLR_ACCENT,
        ).pack(side="left", padx=(8, 4))

        self._canvas = tk.Canvas(
            self, height=14, bg=CLR_BORDER, highlightthickness=0,
        )
        self._canvas.pack(side="left", fill="x", expand=True, pady=4)

        self._val_lbl = tk.Label(
            self, text="0.0", width=7,
            font=(*FONT_MONO, 9),
            bg=CLR_SURFACE, fg=CLR_TEXT,
        )
        self._val_lbl.pack(side="left", padx=(4, 8))

        self._canvas.bind("<Configure>", self._redraw)
        self._value = 0.0

    def set_value(self, value: float):
        self._value = value
        self._val_lbl.config(text=f"{value:+.1f}")
        self._redraw()

    def _redraw(self, _=None):
        self._canvas.delete("all")
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 4:
            return
        span    = self.hi - self.lo
        clipped = max(self.lo, min(self.hi, self._value))
        frac    = (clipped - self.lo) / span if span else 0.5
        bar_w   = int(frac * w)
        clr     = _lerp_color(CLR_FAIL, CLR_PASS, frac)
        if bar_w > 0:
            self._canvas.create_rectangle(0, 0, bar_w, h, fill=clr, outline="")
        # Centre tick (zero line)
        mid = int((-self.lo / span) * w) if span else w // 2
        self._canvas.create_line(mid, 0, mid, h, fill=CLR_TEXT_MUTED, width=1)


# ── Animated Spinner ──────────────────────────────────────────────────────────

class ScannerSpinner(tk.Canvas):
    """Rotating arc scanner indicator for 'PROCESSING' state."""

    def __init__(self, parent, size: int = 36, **kwargs):
        super().__init__(
            parent, width=size, height=size,
            bg=CLR_SURFACE, highlightthickness=0,
        )
        self._size  = size
        self._angle = 0
        self._running = False
        self._job = None

    def start(self):
        self._running = True
        self._spin()

    def stop(self):
        self._running = False
        if self._job:
            self.after_cancel(self._job)
        self.delete("all")

    def _spin(self):
        if not self._running:
            return
        self.delete("all")
        s = self._size
        pad = 4
        self.create_arc(
            pad, pad, s - pad, s - pad,
            start=self._angle, extent=270,
            outline=CLR_ACCENT, width=3, style="arc",
        )
        self.create_arc(
            pad, pad, s - pad, s - pad,
            start=self._angle + 270, extent=90,
            outline=CLR_BORDER, width=3, style="arc",
        )
        self._angle = (self._angle + 8) % 360
        self._job = self.after(25, self._spin)


# ── Delta-E Gauge ─────────────────────────────────────────────────────────────

class DeltaEGauge(tk.Canvas):
    """
    Horizontal gradient gauge for DeltaE value (0 → 10+).
    """

    W, H = 220, 28

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent, width=self.W, height=self.H,
            bg=CLR_SURFACE, highlightthickness=0,
        )
        self._value = 0.0
        self._draw()

    def set_value(self, v: float):
        self._value = v
        self._draw()

    def _draw(self):
        self.delete("all")
        # Gradient background (green → yellow → red)
        steps = self.W
        for i in range(steps):
            t = i / steps
            if t < 0.3:
                c = _lerp_color(CLR_PASS, CLR_WARN, t / 0.3)
            else:
                c = _lerp_color(CLR_WARN, CLR_FAIL, (t - 0.3) / 0.7)
            self.create_line(i, 0, i, self.H, fill=c)

        # Pointer
        max_de = 10.0
        frac   = min(1.0, self._value / max_de)
        px     = int(frac * self.W)
        self.create_polygon(
            px - 6, self.H, px + 6, self.H, px, self.H - 10,
            fill="white", outline="",
        )
        self.create_text(
            px, 10,
            text=f"{self._value:.2f}",
            font=(*FONT_MONO, 8, "bold"),
            fill="white",
            anchor="s",
        )


# ── Industrial Separator ──────────────────────────────────────────────────────

class Separator(tk.Frame):
    def __init__(self, parent, horizontal: bool = True, **kwargs):
        super().__init__(parent, bg=CLR_BORDER, **kwargs)
        if horizontal:
            self.config(height=1)
        else:
            self.config(width=1)


# ── Labelled Slider ───────────────────────────────────────────────────────────

class LabelledSlider(tk.Frame):
    """Slider with title label and live value readout."""

    def __init__(
        self,
        parent,
        title: str,
        from_: float,
        to: float,
        initial: float,
        resolution: float = 0.1,
        command=None,
        fmt: str = "{:.1f}",
        **kwargs,
    ):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        self._fmt     = fmt
        self._command = command

        row = tk.Frame(self, bg=CLR_PANEL)
        row.pack(fill="x")

        tk.Label(
            row, text=title, font=(*FONT_UI, 9),
            bg=CLR_PANEL, fg=CLR_TEXT,
        ).pack(side="left")

        self._val_lbl = tk.Label(
            row, text=fmt.format(initial), width=7,
            font=(*FONT_MONO, 9, "bold"),
            bg=CLR_PANEL, fg=CLR_ACCENT,
        )
        self._val_lbl.pack(side="right")

        self._var = tk.DoubleVar(value=initial)
        self._slider = ttk.Scale(
            self, from_=from_, to=to,
            orient="horizontal", variable=self._var,
            command=self._on_change,
        )
        self._slider.pack(fill="x", padx=4)

    def _on_change(self, _=None):
        v = self._var.get()
        self._val_lbl.config(text=self._fmt.format(v))
        if self._command:
            self._command(v)

    def get(self) -> float:
        return self._var.get()

    def set(self, value: float):
        self._var.set(value)
        self._val_lbl.config(text=self._fmt.format(value))


# ── Industrial Button ─────────────────────────────────────────────────────────

class IndustrialButton(tk.Button):
    """
    Flat button with accent border and hover highlight.
    """

    def __init__(
        self,
        parent,
        text: str,
        command=None,
        accent: str = CLR_ACCENT,
        danger: bool = False,
        **kwargs,
    ):
        clr = CLR_FAIL if danger else accent
        super().__init__(
            parent,
            text=text,
            command=command,
            font=(*FONT_UI, 9, "bold"),
            bg=CLR_SURFACE,
            fg=clr,
            activebackground=clr,
            activeforeground=CLR_BG,
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightbackground=clr,
            highlightcolor=clr,
            cursor="hand2",
            padx=14,
            pady=6,
            **kwargs,
        )
        self._clr = clr
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _):
        self.config(bg=self._clr, fg=CLR_BG)

    def _on_leave(self, _):
        self.config(bg=CLR_SURFACE, fg=self._clr)


# ── Section Header ────────────────────────────────────────────────────────────

class SectionHeader(tk.Frame):
    def __init__(self, parent, title: str, icon: str = "◈", **kwargs):
        super().__init__(parent, bg=CLR_PANEL, **kwargs)
        tk.Label(
            self, text=f"{icon}  {title}",
            font=(*FONT_UI, 10, "bold"),
            bg=CLR_PANEL, fg=CLR_ACCENT,
        ).pack(side="left", pady=6)
        Separator(self, horizontal=True).pack(side="left", fill="x", expand=True, padx=10, pady=10)
