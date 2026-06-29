"""
DataTools Entry Point
=====================

This entry point can start either:
- the main DataTools hub application
- the read-only Matching viewer window

The viewer mode is used so the Matching feature can open in its own window
while still being shipped as part of the same DataTools executable.
"""

import os

# Disable Kivy's multitouch emulation (red dot on right-click) for desktop use.
# Must be set before any Kivy window/input modules are imported.
from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")

from app.main import DataToolsApp
from app.matching_viewer import MatchingViewerApp


def main() -> None:
    """Start the requested DataTools application mode."""
    if os.environ.get("DATATOOLS_MODE", "").strip().lower() == "matching_viewer":
        MatchingViewerApp().run()
        return

    DataToolsApp().run()


if __name__ == "__main__":
    main()
