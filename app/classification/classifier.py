"""
INFAC-P5 — classification/classifier.py
DeltaE-based colour classification engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np

from app.utils.constants import (
    DELTA_E_VARIANT_A_MAX,
    DELTA_E_VARIANT_B_MAX,
    REFERENCE_VARIANT_A_LAB,
    REFERENCE_VARIANT_B_LAB,
)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class LABColor:
    L: float
    a: float
    b: float

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.L, self.a, self.b)

    def __repr__(self) -> str:
        return f"LAB(L={self.L:.1f}, a={self.a:.1f}, b={self.b:.1f})"


@dataclass
class ClassificationResult:
    label: str           = "UNKNOWN"
    verdict: str         = "FAIL"         # "PASS" | "FAIL" | "PROCESSING"
    confidence: float    = 0.0            # 0–100 %
    delta_e76: float     = 0.0
    delta_e2000: float   = 0.0
    lab: LABColor        = field(default_factory=lambda: LABColor(0, 0, 0))
    reflection_pct: float = 0.0
    pixel_variance: float = 0.0
    dominant_hex: str    = "#000000"


# ── DeltaE formulae ───────────────────────────────────────────────────────────

def delta_e76(lab1: LABColor, lab2: LABColor) -> float:
    """Classic CIE76 colour-difference formula."""
    return math.sqrt(
        (lab1.L - lab2.L) ** 2 +
        (lab1.a - lab2.a) ** 2 +
        (lab1.b - lab2.b) ** 2
    )


def delta_e2000(lab1: LABColor, lab2: LABColor) -> float:
    """
    CIEDE2000 colour-difference formula.
    Significantly more perceptually uniform than CIE76.
    """
    L1, a1, b1 = lab1.L, lab1.a, lab1.b
    L2, a2, b2 = lab2.L, lab2.a, lab2.b

    # Step 1 – a′
    C1 = math.sqrt(a1 ** 2 + b1 ** 2)
    C2 = math.sqrt(a2 ** 2 + b2 ** 2)
    C_avg = (C1 + C2) / 2.0
    C_avg7 = C_avg ** 7
    G = 0.5 * (1 - math.sqrt(C_avg7 / (C_avg7 + 25 ** 7)))
    a1p = a1 * (1 + G)
    a2p = a2 * (1 + G)

    # Step 2 – C′, h′
    C1p = math.sqrt(a1p ** 2 + b1 ** 2)
    C2p = math.sqrt(a2p ** 2 + b2 ** 2)

    def _hprime(ap, b):
        if ap == 0 and b == 0:
            return 0.0
        angle = math.degrees(math.atan2(b, ap))
        return angle + 360 if angle < 0 else angle

    h1p = _hprime(a1p, b1)
    h2p = _hprime(a2p, b2)

    # Step 3 – ΔL′, ΔC′, ΔH′
    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360

    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))

    # Step 4 – averages
    Lp_avg = (L1 + L2) / 2.0
    Cp_avg = (C1p + C2p) / 2.0

    if C1p * C2p == 0:
        Hp_avg = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        Hp_avg = (h1p + h2p) / 2.0
    elif h1p + h2p < 360:
        Hp_avg = (h1p + h2p + 360) / 2.0
    else:
        Hp_avg = (h1p + h2p - 360) / 2.0

    # Step 5 – weighting functions
    T = (
        1
        - 0.17 * math.cos(math.radians(Hp_avg - 30))
        + 0.24 * math.cos(math.radians(2 * Hp_avg))
        + 0.32 * math.cos(math.radians(3 * Hp_avg + 6))
        - 0.20 * math.cos(math.radians(4 * Hp_avg - 63))
    )
    SL = 1 + 0.015 * (Lp_avg - 50) ** 2 / math.sqrt(20 + (Lp_avg - 50) ** 2)
    SC = 1 + 0.045 * Cp_avg
    SH = 1 + 0.015 * Cp_avg * T

    Cp_avg7 = Cp_avg ** 7
    RC = 2 * math.sqrt(Cp_avg7 / (Cp_avg7 + 25 ** 7))
    d_theta = 30 * math.exp(-((Hp_avg - 275) / 25) ** 2)
    RT = -math.sin(math.radians(2 * d_theta)) * RC

    dE = math.sqrt(
        (dLp / SL) ** 2 +
        (dCp / SC) ** 2 +
        (dHp / SH) ** 2 +
        RT * (dCp / SC) * (dHp / SH)
    )
    return dE


# ── Classifier ────────────────────────────────────────────────────────────────

class ColorClassifier:
    """
    Compares measured LAB against reference targets and produces a
    ClassificationResult.

    Parameters
    ----------
    ref_a_lab : tuple(L, a, b) — reference for Variant A
    ref_b_lab : tuple(L, a, b) — reference for Variant B
    thresh_a  : DeltaE upper bound for Variant A  (default 2.0)
    thresh_b  : DeltaE upper bound for Variant B  (default 5.0)
    """

    def __init__(
        self,
        ref_a_lab: Tuple[float, float, float] = REFERENCE_VARIANT_A_LAB,
        ref_b_lab: Tuple[float, float, float] = REFERENCE_VARIANT_B_LAB,
        thresh_a:  float = DELTA_E_VARIANT_A_MAX,
        thresh_b:  float = DELTA_E_VARIANT_B_MAX,
    ) -> None:
        self.ref_a   = LABColor(*ref_a_lab)
        self.ref_b   = LABColor(*ref_b_lab)
        self.thresh_a = thresh_a
        self.thresh_b = thresh_b

    # ── Threshold setters (called from UI sliders) ────────────────────────────

    def set_thresholds(self, thresh_a: float, thresh_b: float) -> None:
        self.thresh_a = thresh_a
        self.thresh_b = thresh_b

    def set_reference_a(self, lab: Tuple[float, float, float]) -> None:
        self.ref_a = LABColor(*lab)

    def set_reference_b(self, lab: Tuple[float, float, float]) -> None:
        self.ref_b = LABColor(*lab)

    # ── Classification ────────────────────────────────────────────────────────

    def classify(
        self,
        measured_lab: LABColor,
        reflection_pct: float = 0.0,
        pixel_variance: float = 0.0,
        dominant_hex: str = "#000000",
    ) -> ClassificationResult:
        """
        Classify measured colour against both references and return result.
        Uses CIEDE2000 as primary metric; CIE76 reported for reference.
        """
        dE_a_2000 = delta_e2000(measured_lab, self.ref_a)
        dE_b_2000 = delta_e2000(measured_lab, self.ref_b)
        dE_a_76   = delta_e76(measured_lab, self.ref_a)
        dE_b_76   = delta_e76(measured_lab, self.ref_b)

        # Pick best matching reference
        if dE_a_2000 <= dE_b_2000:
            best_de2000 = dE_a_2000
            best_de76   = dE_a_76
            is_a_closer = True
        else:
            best_de2000 = dE_b_2000
            best_de76   = dE_b_76
            is_a_closer = False

        # Determine label and verdict
        if best_de2000 <= self.thresh_a:
            label   = "Blue Variant A"
            verdict = "PASS"
            confidence = max(0.0, 100.0 - (best_de2000 / self.thresh_a) * 30.0)
        elif best_de2000 <= self.thresh_b:
            label   = "Blue Variant B"
            verdict = "PASS"
            # Confidence decreases as dE approaches thresh_b
            span = self.thresh_b - self.thresh_a
            pos  = best_de2000 - self.thresh_a
            confidence = max(0.0, 85.0 - (pos / span) * 40.0)
        else:
            label   = "Reject / Unknown"
            verdict = "FAIL"
            confidence = max(0.0, min(50.0, 100.0 - best_de2000 * 5.0))

        return ClassificationResult(
            label         = label,
            verdict       = verdict,
            confidence    = round(confidence, 1),
            delta_e76     = round(best_de76, 3),
            delta_e2000   = round(best_de2000, 3),
            lab           = measured_lab,
            reflection_pct= round(reflection_pct, 1),
            pixel_variance= round(pixel_variance, 2),
            dominant_hex  = dominant_hex,
        )
