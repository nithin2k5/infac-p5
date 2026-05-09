"""
INFAC-P5 — Industrial Color Inspection System
Constants and configuration shared across all modules.
"""

# ── Application metadata ──────────────────────────────────────────────────────
APP_NAME        = "INFAC Vision Inspector"
APP_VERSION     = "1.0.0"
APP_SUBTITLE    = "Industrial Color Inspection System"
COMPANY_NAME    = "INFAC Vision Systems"

# ── Window ────────────────────────────────────────────────────────────────────
WINDOW_MIN_W    = 1280
WINDOW_MIN_H    = 800
WINDOW_START_W  = 1600
WINDOW_START_H  = 920

# ── Camera ────────────────────────────────────────────────────────────────────
DEFAULT_CAMERA_INDEX  = 0
TARGET_FPS            = 30
FRAME_W               = 640
FRAME_H               = 480
CAMERA_TIMEOUT        = 5.0          # seconds before declared offline

# ── ROI (Region Of Interest) — fraction of frame ──────────────────────────────
ROI_X_FRAC = 0.25
ROI_Y_FRAC = 0.20
ROI_W_FRAC = 0.50
ROI_H_FRAC = 0.60

# ── Classification thresholds ─────────────────────────────────────────────────
DELTA_E_VARIANT_A_MAX  = 2.0    # < this → Variant A  (PASS)
DELTA_E_VARIANT_B_MAX  = 5.0    # < this → Variant B  (PASS)
DELTA_E_REJECT_MIN     = 5.0    # ≥ this → Reject      (FAIL)

# ── Reflection suppression ────────────────────────────────────────────────────
DEFAULT_REFLECTION_THRESH  = 230   # pixel brightness considered a highlight
DEFAULT_REFLECTION_BLEND   = 0.5   # blend factor 0.0–1.0

# ── LAB reference colours (calibration defaults) ──────────────────────────────
# These represent two "blue" variants on the production line.
REFERENCE_VARIANT_A_LAB = (38.0, 5.0, -42.0)   # (L*, a*, b*)
REFERENCE_VARIANT_B_LAB = (41.0, 4.0, -37.0)

# ── Colour palette (UI) ───────────────────────────────────────────────────────
CLR_BG          = "#0D0F14"
CLR_PANEL       = "#13161E"
CLR_SURFACE     = "#1A1D28"
CLR_BORDER      = "#252A38"
CLR_ACCENT      = "#00C8FF"
CLR_ACCENT2     = "#7B5EA7"
CLR_PASS        = "#00E676"
CLR_FAIL        = "#FF3D57"
CLR_WARN        = "#FFB300"
CLR_TEXT        = "#E2E8F0"
CLR_TEXT_DIM    = "#64748B"
CLR_TEXT_MUTED  = "#334155"

# ── Font family ───────────────────────────────────────────────────────────────
FONT_MONO  = ("Courier New", )
FONT_UI    = ("Segoe UI", )

# ── Processing ────────────────────────────────────────────────────────────────
PROCESSING_QUEUE_MAXSIZE = 2   # keep queue small for low-latency
UI_UPDATE_INTERVAL_MS    = 33  # ~30 Hz UI refresh
