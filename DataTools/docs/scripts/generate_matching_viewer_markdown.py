"""
DataTools Matching Viewer Documentation Generator
================================================

This script generates a detailed Markdown user manual for the DataTools
Matching Viewer and can auto-capture a deterministic screenshot set.

Default behavior:
- Captures fresh screenshots from the Matching viewer flow
- Creates/overwrites docs/generated/matching-viewer-manual.md
- Embeds each screenshot inline for readable end-to-end user guidance

Usage examples:
- python DataTools/docs/scripts/generate_matching_viewer_markdown.py
- python DataTools/docs/scripts/generate_matching_viewer_markdown.py --skip-screenshots
- python DataTools/docs/scripts/generate_matching_viewer_markdown.py --title "Matching Viewer Manual (v0.2)"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout


DOCS_ROOT = Path(__file__).resolve().parent.parent
DATATOOLS_ROOT = DOCS_ROOT.parent
SCREENSHOT_DIR = DOCS_ROOT / "screenshots" / "matching-viewer"
OUTPUT_FILE = DOCS_ROOT / "generated" / "matching-viewer-manual.md"

SCREEN_SEQUENCE = [
    "01_matching_home.png",
    "02_matching_open_default.png",
    "03_matching_modes.png",
    "04_matching_serial_lookup.png",
    "05_matching_overlay_popup_default.png",
    "06_matching_overlay_popup_error_invalid.png",
    "07_matching_overlay_popup_error_range.png",
    "08_matching_overlay_popup_custom_range.png",
]

# Preferred pair used for documentation screenshots when available in DB.
PREFERRED_PAIR_LEFT = "IA6600029"
PREFERRED_PAIR_RIGHT = "IB6600010"


def _import_app_modules():
    """Import DataTools app modules after adding DataTools root to sys.path."""
    if str(DATATOOLS_ROOT) not in sys.path:
        sys.path.insert(0, str(DATATOOLS_ROOT))

    from app.main import HomeScreen
    from app.matching_viewer import MatchingViewerRoot, TimeframeOverlayPopup
    from app.settings_store import DataToolsSettingsStore

    return HomeScreen, MatchingViewerRoot, TimeframeOverlayPopup, DataToolsSettingsStore


class MatchingViewerDocCaptureApp(App):
    """Deterministic capture app for Matching Viewer user manual screenshots."""

    title = "DataTools Matching Viewer Doc Capture"

    def __init__(self, screenshot_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = screenshot_dir
        self.store = None
        self.scene_root = None
        self.home_screen = None
        self.viewer = None
        self.overlay_popup = None

        (
            self.HomeScreen,
            self.MatchingViewerRoot,
            self.TimeframeOverlayPopup,
            self.DataToolsSettingsStore,
        ) = _import_app_modules()

    def build(self):
        """Build home screen with matching callback replaced for deterministic capture."""
        self.store = self.DataToolsSettingsStore(DATATOOLS_ROOT)

        # Stable data paths for repeatable docs generation.
        self.store.set(
            "matching_db_path",
            str((DATATOOLS_ROOT.parent / "Matching_App" / "Data" / "db" / "matcher.db").resolve()),
        )
        self.store.set(
            "default_export_folder",
            str((DATATOOLS_ROOT / "Exports").resolve()),
        )

        self.home_screen = self.HomeScreen(settings_store=self.store)
        self.scene_root = BoxLayout()
        self.scene_root.add_widget(self.home_screen)
        return self.scene_root

    def _take_widget(self, widget, filename: str):
        """Capture widget area via Window.screenshot (no alpha transparency)."""
        self._take_window(filename)

    def on_start(self):
        """Run the screenshot capture timeline when UI is ready."""
        Window.size = (1920, 1080)
        Clock.schedule_once(self._prepare_home_capture, 1.0)

    def _prepare_home_capture(self, _dt):
        """Ensure home view has final geometry before taking the first screenshot."""
        self.scene_root.size = Window.size
        self.scene_root.pos = (0, 0)
        self.home_screen.size = Window.size
        self.home_screen.pos = (0, 0)
        self.scene_root.do_layout()
        self.home_screen.do_layout()
        Clock.schedule_once(self._capture_home, 0.35)

    def _take_window(self, filename: str):
        """Capture one screenshot and normalize to deterministic filename."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        target = self.screenshot_dir / filename
        saved = Path(Window.screenshot(name=str(target)))
        if saved.exists() and saved != target:
            target.unlink(missing_ok=True)
            saved.replace(target)

    def _capture_home(self, _dt):
        """Capture home screen and open matching viewer state."""
        self._take_widget(self.home_screen, "01_matching_home.png")

        self.viewer = self.MatchingViewerRoot(settings_store=self.store, on_back=lambda: None)
        self.scene_root.clear_widgets()
        self.scene_root.add_widget(self.viewer)
        Clock.schedule_once(self._capture_viewer_default, 0.8)

    def _capture_viewer_default(self, _dt):
        """Capture default matching viewer state with summary and list."""
        self._take_widget(self.viewer, "02_matching_open_default.png")
        self.viewer._set_mode("paired")
        Clock.schedule_once(self._capture_modes, 0.5)

    def _capture_modes(self, _dt):
        """Capture mode view and continue with one serial lookup."""
        self._take_widget(self.viewer, "03_matching_modes.png")

        sample_serial = self._pick_serial_for_docs()

        self.viewer.serial_input.text = sample_serial
        self.viewer._show_serial_lookup()
        Clock.schedule_once(self._capture_serial_lookup, 0.5)

    def _pick_serial_for_docs(self) -> str:
        """Pick a deterministic serial for screenshots, preferring the requested pair."""
        # First, try to use the explicitly requested pair from documentation feedback.
        for pair_item in self.viewer.paired_items:
            left_serial = pair_item.get("left_serial", "")
            right_serial = pair_item.get("right_serial", "")
            if left_serial == PREFERRED_PAIR_LEFT and right_serial == PREFERRED_PAIR_RIGHT:
                return left_serial
            if left_serial == PREFERRED_PAIR_RIGHT and right_serial == PREFERRED_PAIR_LEFT:
                return left_serial

        # Fallback: keep previous deterministic behavior.
        if self.viewer.matched_items:
            return self.viewer.matched_items[0].get("left_serial", "")
        if self.viewer.paired_items:
            return self.viewer.paired_items[0].get("left_serial", "")
        if self.viewer.pool_items:
            return self.viewer.pool_items[0].get("serial", "")
        return ""

    def _capture_serial_lookup(self, _dt):
        """Capture serial lookup result and open timeframe overlay popup."""
        self._take_widget(self.viewer, "04_matching_serial_lookup.png")
        self.overlay_popup = self.TimeframeOverlayPopup(repository=self.viewer.repository, settings_store=self.store)
        self.overlay_popup.open()
        Clock.schedule_once(self._capture_overlay_default, 0.7)

    def _capture_overlay_default(self, _dt):
        """Capture default overlay popup state and then invalid format error."""
        self._take_widget(self.overlay_popup, "05_matching_overlay_popup_default.png")
        self.overlay_popup.start_input.text = "25.06.2026"
        self.overlay_popup.end_input.text = "2026-06-25"
        self.overlay_popup._render_overlay()
        Clock.schedule_once(self._capture_overlay_invalid, 0.4)

    def _capture_overlay_invalid(self, _dt):
        """Capture invalid date format validation state."""
        self._take_widget(self.overlay_popup, "06_matching_overlay_popup_error_invalid.png")
        self.overlay_popup.start_input.text = "2026-06-25"
        self.overlay_popup.end_input.text = "2026-06-20"
        self.overlay_popup._render_overlay()
        Clock.schedule_once(self._capture_overlay_range_error, 0.4)

    def _capture_overlay_range_error(self, _dt):
        """Capture end-before-start validation state and then valid custom range."""
        self._take_widget(self.overlay_popup, "07_matching_overlay_popup_error_range.png")
        self.overlay_popup.start_input.text = "2026-06-11"
        self.overlay_popup.end_input.text = "2026-06-25"
        self.overlay_popup._render_overlay()
        Clock.schedule_once(self._capture_overlay_custom, 0.5)

    def _capture_overlay_custom(self, _dt):
        """Capture valid overlay result and finish capture run."""
        self._take_widget(self.overlay_popup, "08_matching_overlay_popup_custom_range.png")
        if self.overlay_popup:
            self.overlay_popup.dismiss()
        Clock.schedule_once(lambda _inner_dt: self.stop(), 0.2)


def capture_screenshots(clean: bool = True) -> list[Path]:
    """
    Capture deterministic Matching Viewer screenshots.

    Args:
        clean: Delete existing screenshot PNG files before capturing.

    Returns:
        Ordered list of screenshot paths that were captured.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for path in SCREENSHOT_DIR.glob("*.png"):
            path.unlink(missing_ok=True)

    MatchingViewerDocCaptureApp(screenshot_dir=SCREENSHOT_DIR).run()

    files_by_name = {path.name: path for path in SCREENSHOT_DIR.glob("*.png")}
    ordered = [files_by_name[name] for name in SCREEN_SEQUENCE if name in files_by_name]
    return ordered


def _build_markdown(title: str, image_paths: list[Path]) -> str:
    """Build a detailed Matching Viewer manual with inline screenshots."""
    lines: list[str] = []
    screenshot_map = {path.stem: path.name for path in image_paths}

    lines.append(f"# {title}")
    lines.append("")
    lines.append("This manual documents the DataTools Matching Viewer in read-only mode.")
    lines.append("It includes detailed workflows, keyboard-first operation, and troubleshooting.")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("The Matching Viewer is used to inspect existing matcher data without changing it.")
    lines.append("Main capabilities:")
    lines.append("")
    lines.append("- View pool, matched, paired, and assembled states")
    lines.append("- Inspect one serial quickly via Enter-based lookup")
    lines.append("- Plot single curves or left/right pair overlays")
    lines.append("- Filter any list by date range to reduce scrolling")
    lines.append("- Open timeframe overlay to display many curves together")
    lines.append("- Export a read-only CSV snapshot of all data")
    lines.append("")
    lines.append("## Navigation")
    lines.append("")
    lines.append("1. Open DataTools.")
    lines.append("2. Click the Matching tile.")
    lines.append("3. The viewer opens in the same window.")
    lines.append("4. Use Back to Home to return.")
    lines.append("")

    if "01_matching_home" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["01_matching_home"]
        lines.append("## Home Screen")
        lines.append("")
        lines.append(f"![DataTools Home with Matching Tile]({rel.as_posix()})")
        lines.append("")

    if "02_matching_open_default" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["02_matching_open_default"]
        lines.append("## Matching Viewer Overview")
        lines.append("")
        lines.append(f"![Matching Viewer Default]({rel.as_posix()})")
        lines.append("")
        lines.append("Areas in this screen:")
        lines.append("")
        lines.append("- Top toolbar: Refresh, Export CSV, Timeframe Overlay")
        lines.append("- Summary row: Pool, Matched, Paired, and Assembled counts")
        lines.append("- Left panel: mode selection, date filter buttons, and serial input")
        lines.append("- Right panel: selected item label with RMSE, and chart")
        lines.append("- Footer line: status and error feedback")
        lines.append("- Error messages are highlighted in red for fast operator recognition")
        lines.append("")

    if "03_matching_modes" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["03_matching_modes"]
        lines.append("## Mode Selection")
        lines.append("")
        lines.append(f"![Matching Modes]({rel.as_posix()})")
        lines.append("")
        lines.append("Modes:")
        lines.append("")
        lines.append("- **Pool**: Single unmatched drivers awaiting matching.")
        lines.append("- **Matched**: Left/right pairs suggested by the matching tool, but not yet confirmed for installation. A worker has seen the suggested match serial on screen but has not yet scanned it.")
        lines.append("- **Paired**: Confirmed pairs sorted for installation. The worker scanned both module serials, marking them as a set to be installed together.")
        lines.append("- **Assembled**: Completed systems. Each entry links a system serial number to the two installed driver modules and the date of assembly.")
        lines.append("")

    lines.append("## Filtering by Date Range")
    lines.append("")
    lines.append("All list views support date-range filtering to reduce scrolling in long lists. Each mode filters by a different date field:")
    lines.append("")
    lines.append("| Mode      | Date field   | Meaning                                    |")
    lines.append("|-----------|--------------|--------------------------------------------|")
    lines.append("| Pool      | `loaded_at`  | Measurement date of the driver             |")
    lines.append("| Matched   | `loaded_at`  | Measurement date of the driver             |")
    lines.append("| Paired    | `matched_at` | Date when the worker confirmed the pair    |")
    lines.append("| Assembled | `built_at`   | Date when the system was assembled         |")
    lines.append("")
    lines.append("### How to Filter")
    lines.append("")
    lines.append("1. Switch to the desired mode (Pool, Matched, Paired, or Assembled).")
    lines.append("2. Click the **Filter** button in the left panel.")
    lines.append("3. Enter a **Start** date (e.g., `2026-06-22`).")
    lines.append("4. Enter an **End** date (e.g., `2026-06-29`).")
    lines.append("5. Click **Apply** or press Enter in either date field.")
    lines.append("6. Only items within the date range are shown in the list.")
    lines.append("7. Click **Clear Filter** to show all items again.")
    lines.append("")
    lines.append("### Supported Date Formats")
    lines.append("")
    lines.append("- `YYYY-MM-DD`")
    lines.append("- `YYYY-MM-DD HH:MM`")
    lines.append("- `YYYY-MM-DD HH:MM:SS`")
    lines.append("- `YYYY-MM-DDTHH:MM`")
    lines.append("- `YYYY-MM-DDTHH:MM:SS`")
    lines.append("")
    lines.append("### Filter Behavior")
    lines.append("")
    lines.append("- **Auto-save**: The last used date range is saved per mode. Switching between modes preserves each mode's own filter settings independently.")
    lines.append("- **Default range**: If no filter has been set before, the default is the last 30 days.")
    lines.append("- **Error feedback**: Invalid dates or an end date before start date are highlighted in red.")
    lines.append("- **Count display**: After filtering, you see how many items match the range, e.g., `Filtered: 12 of 58 items in range.`")
    lines.append("")

    if "04_matching_serial_lookup" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["04_matching_serial_lookup"]
        lines.append("## Serial Lookup (Enter Only)")
        lines.append("")
        lines.append(f"![Serial Lookup Result]({rel.as_posix()})")
        lines.append("")
        lines.append("Workflow:")
        lines.append("")
        lines.append("1. Scan or type module serial in the Serial field.")
        lines.append("2. Press Enter.")
        lines.append("3. Viewer auto-switches to the relevant mode and displays curve(s).")
        lines.append("4. Input field is cleared after a successful lookup.")
        lines.append("")
        lines.append("### Important: Lookup Ignores Active Filters")
        lines.append("")
        lines.append("**Serial lookup searches the entire database, not just the filtered list.** This means:")
        lines.append("")
        lines.append("- If you search for a serial that is **outside the active timeframe filter**, it will still be found and displayed.")
        lines.append("- The filter only affects what is shown in the list view; it does not restrict the search capability.")
        lines.append("- This allows you to quickly access any module even if it falls outside your current date range.")
        lines.append("")

    lines.append("## Timeframe Overlay")
    lines.append("")
    lines.append("The overlay popup draws all curves in one selected period in one shared chart.")
    lines.append("Color coding:")
    lines.append("")
    lines.append("- Blue: left modules")
    lines.append("- Red: right modules")
    lines.append("- Both are thin and semi-transparent for dense overlays")
    lines.append("")

    if "05_matching_overlay_popup_default" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["05_matching_overlay_popup_default"]
        lines.append("### Default Overlay on Open")
        lines.append("")
        lines.append(f"![Overlay Default Range]({rel.as_posix()})")
        lines.append("")
        lines.append("Behavior:")
        lines.append("")
        lines.append("- Last used timeframe is restored automatically")
        lines.append("- If no value exists yet, default is last 7 days")
        lines.append("- Overlay is rendered automatically when popup opens")
        lines.append("")

    lines.append("### Date Input Formats")
    lines.append("")
    lines.append("Accepted formats:")
    lines.append("")
    lines.append("- YYYY-MM-DD")
    lines.append("- YYYY-MM-DD HH:MM")
    lines.append("- YYYY-MM-DD HH:MM:SS")
    lines.append("- YYYY-MM-DDTHH:MM")
    lines.append("- YYYY-MM-DDTHH:MM:SS")
    lines.append("")
    lines.append("Press Enter in either date field to refresh the overlay.")
    lines.append("")

    if "06_matching_overlay_popup_error_invalid" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["06_matching_overlay_popup_error_invalid"]
        lines.append("### Validation Error: Invalid Date Format")
        lines.append("")
        lines.append(f"![Invalid Date Error]({rel.as_posix()})")
        lines.append("")
        lines.append("If date format is invalid, an error is shown in red and plot is not updated.")
        lines.append("")

    if "07_matching_overlay_popup_error_range" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["07_matching_overlay_popup_error_range"]
        lines.append("### Validation Error: End Before Start")
        lines.append("")
        lines.append(f"![End Before Start Error]({rel.as_posix()})")
        lines.append("")
        lines.append("If End is before Start, an error is shown in red and no new query is executed.")
        lines.append("")

    if "08_matching_overlay_popup_custom_range" in screenshot_map:
        rel = Path("..") / "screenshots" / "matching-viewer" / screenshot_map["08_matching_overlay_popup_custom_range"]
        lines.append("### Custom Valid Range Result")
        lines.append("")
        lines.append(f"![Custom Timeframe Overlay]({rel.as_posix()})")
        lines.append("")
        lines.append("When range is valid, all matching curves are rendered and count summary is shown.")
        lines.append("")

    lines.append("### Export Overlay Plot as PNG")
    lines.append("")
    lines.append("After rendering an overlay, you can export the current plot to a PNG file without opening a separate window:")
    lines.append("")
    lines.append("1. Render a valid overlay by entering dates and clicking Apply (or pressing Enter).")
    lines.append("2. Click the **Export PNG** button in the popup controls.")
    lines.append("3. A native save dialog opens.")
    lines.append("4. Choose a destination and confirm.")
    lines.append("5. The plot is saved as PNG in light mode with a legend showing left/right curve labels.")
    lines.append("")
    lines.append("**Features:**")
    lines.append("")
    lines.append("- Matplotlib renders in the background (no additional window appears).")
    lines.append("- PNG uses light-mode styling (white background, black text) for better printing and sharing.")
    lines.append("- Title shows the timeframe of the exported overlay (Start to End dates).")
    lines.append("- Individual curves shown as thin semi-transparent lines.")
    lines.append("- Median curves calculated and shown as thick dotted lines for each side (blue for left, red for right) to ignore outliers.")
    lines.append("- Legend shows: individual modules, left median, right median.")
    lines.append("- Log-scale frequency axis and all curve colors and transparency are preserved.")
    lines.append("- Default filename is `overlay_plot.png`, can be changed in save dialog.")
    lines.append("")

    lines.append("## Read-Only Guarantee")
    lines.append("")
    lines.append("The Matching Viewer does not change matcher database content.")
    lines.append("Operations are read-only, except CSV and PNG exports which write separate output files.")
    lines.append("")

    lines.append("## CSV Export")
    lines.append("")
    lines.append("1. Click Export CSV.")
    lines.append("2. Choose destination in native save dialog.")
    lines.append("3. The file contains two sections:")
    lines.append("")
    lines.append("**Section 1 - Drivers** (`serial`, `side`, `status`, `partner`, `loaded_at`, `matched_at`)")
    lines.append("")
    lines.append("**Section 2 - Assembled** (`system_serial`, `module_1`, `module_2`, `built_at`)")
    lines.append("")
    lines.append("The export summary shows how many driver rows and assembled system rows were written, e.g., `Exported 64 drivers + 27 assembled systems`.")
    lines.append("")

    lines.append("## Troubleshooting")
    lines.append("")
    lines.append("### Overlay shows no curves")
    lines.append("")
    lines.append("- Check selected timeframe includes known loaded_at data.")
    lines.append("- Verify matching DB path in Settings is correct.")
    lines.append("- Confirm matcher DB contains level arrays.")
    lines.append("")

    lines.append("### Serial lookup returns not found")
    lines.append("")
    lines.append("- Verify scanned serial matches database value.")
    lines.append("- Ensure scanner input has no trailing hidden characters.")
    lines.append("- Confirm current DB file is the expected production/test DB.")
    lines.append("")

    lines.append("### Viewer opens but data is empty")
    lines.append("")
    lines.append("- Use Settings to validate matching DB path.")
    lines.append("- Check DB file exists and is not locked by another process.")
    lines.append("- Press Refresh in viewer toolbar.")
    lines.append("")
    lines.append("### Assembled list is empty")
    lines.append("")
    lines.append("- Confirm the matcher DB contains a `system_builds` table.")
    lines.append("- Press Refresh to reload data from the current DB file.")
    lines.append("")

    return "\n".join(lines)


def generate(title: str, embed: bool = False, html: bool = False, docx: bool = False) -> Path:
    """Generate markdown output from existing screenshot files."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(SCREENSHOT_DIR.glob("*.png"))
    markdown = _build_markdown(title=title, image_paths=image_paths)
    if embed or html:
        from docs_utils import embed_images_in_markdown
        embedded = embed_images_in_markdown(markdown, DOCS_ROOT)
    else:
        embedded = markdown
    OUTPUT_FILE.write_text(embedded if embed else markdown, encoding="utf-8")
    if html:
        from docs_utils import markdown_to_html
        html_path = OUTPUT_FILE.with_suffix(".html")
        html_path.write_text(markdown_to_html(embedded, title), encoding="utf-8")
        print(f"  Written HTML: {html_path}")
    if docx:
        from docs_utils import markdown_to_docx
        docx_path = OUTPUT_FILE.with_suffix(".docx")
        docx_path.write_bytes(markdown_to_docx(markdown, DOCS_ROOT, title))
        print(f"  Written DOCX: {docx_path}")
    return OUTPUT_FILE


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments for manual generation."""
    parser = argparse.ArgumentParser(description="Generate DataTools Matching Viewer markdown documentation.")
    parser.add_argument(
        "--title",
        default="DataTools Matching Viewer User Manual",
        help="Title used as top-level markdown heading.",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Do not capture screenshots, only regenerate markdown from existing PNG files.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing screenshots when capturing new ones.",
    )
    parser.add_argument(
        "--embed-images", action="store_true",
        help="Embed screenshots as base64 data URIs (self-contained, for Confluence).",
    )
    parser.add_argument(
        "--html", action="store_true",
        help="Also generate a self-contained HTML file (open in browser, copy-paste into Confluence).",
    )
    parser.add_argument(
        "--docx", action="store_true",
        help="Also generate a Word .docx file (import into Confluence via Space Tools → Import).",
    )
    return parser.parse_args()


def main() -> None:
    """Run screenshot capture (optional) and markdown generation."""
    args = _parse_args()

    if not args.skip_screenshots:
        capture_screenshots(clean=not args.keep_existing)

    output = generate(title=args.title, embed=args.embed_images, html=args.html, docx=args.docx)
    print(f"Generated manual: {output}")


if __name__ == "__main__":
    main()
