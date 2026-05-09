#!/usr/bin/env python3
"""
INFAC-P5 — Industrial Color Inspection System
Entry point.
"""

import logging
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("infac.main")


def main():
    logger.info("Starting INFAC-P5 Industrial Color Inspection System")

    # Validate dependencies
    try:
        import cv2
        import numpy
        from PIL import Image
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("Run:  pip install -r requirements.txt\n")
        sys.exit(1)

    # Import and launch dashboard
    from app.gui.dashboard import InspectionDashboard
    app = InspectionDashboard()
    app.mainloop()
    logger.info("Application exited cleanly")


if __name__ == "__main__":
    main()
