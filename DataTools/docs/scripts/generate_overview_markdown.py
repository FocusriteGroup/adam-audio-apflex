"""
DataTools Overview Documentation Generator
==========================================

Generates the DataTools overview manual (one Home-screen screenshot + descriptive
markdown) and writes it to docs/generated/overview-manual.md.

Default behaviour:
- Captures a fresh Home-screen screenshot
- Creates/overwrites docs/generated/overview-manual.md

Usage examples:
- python DataTools/docs/scripts/generate_overview_markdown.py
- python DataTools/docs/scripts/generate_overview_markdown.py --skip-screenshots
- python DataTools/docs/scripts/generate_overview_markdown.py --title "DataTools Overview (v0.3)"
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window


DOCS_ROOT = Path(__file__).resolve().parent.parent
DATATOOLS_ROOT = DOCS_ROOT.parent
SCREENSHOT_DIR = DOCS_ROOT / "screenshots" / "overview"
OUTPUT_FILE = DOCS_ROOT / "generated" / "overview-manual.md"

SCREEN_SEQUENCE = ["01_home.png"]


def _import_app_modules():
    if str(DATATOOLS_ROOT) not in sys.path:
        sys.path.insert(0, str(DATATOOLS_ROOT))

    from app.main import HomeScreen
    from app.settings_store import DataToolsSettingsStore

    return HomeScreen, DataToolsSettingsStore


class OverviewDocCaptureApp(App):
    """Single-screenshot capture app for the DataTools overview manual."""

    title = "DataTools Overview Doc Capture"

    def __init__(self, screenshot_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = screenshot_dir
        self.HomeScreen, self.DataToolsSettingsStore = _import_app_modules()
        self.store = None
        self.home_screen = None

    def build(self):
        self.store = self.DataToolsSettingsStore(DATATOOLS_ROOT)
        self.home_screen = self.HomeScreen(settings_store=self.store)
        return self.home_screen

    def on_start(self):
        Window.size = (1920, 1080)
        Clock.schedule_once(self._prepare_home, 1.0)

    def _prepare_home(self, _dt):
        self.home_screen.size = Window.size
        self.home_screen.pos = (0, 0)
        self.home_screen.do_layout()
        Clock.schedule_once(self._capture_home, 0.35)

    def _capture_home(self, _dt):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        target = self.screenshot_dir / "01_home.png"
        target.unlink(missing_ok=True)
        saved = Path(Window.screenshot(name=str(target)))
        if saved.exists() and saved != target:
            target.unlink(missing_ok=True)
            saved.replace(target)
        Clock.schedule_once(lambda _: self.stop(), 0.2)


def capture_screenshots(clean: bool = True) -> list[Path]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for p in SCREENSHOT_DIR.glob("*.png"):
            p.unlink(missing_ok=True)

    OverviewDocCaptureApp(screenshot_dir=SCREENSHOT_DIR).run()

    files_by_name = {p.name: p for p in SCREENSHOT_DIR.glob("*.png")}
    return [files_by_name[n] for n in SCREEN_SEQUENCE if n in files_by_name]


def _build_markdown(title: str, image_paths: list[Path]) -> str:
    screenshot_map = {p.stem: p.name for p in image_paths}
    lines: list[str] = []

    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        "DataTools is a production-support desktop application for data handling. "
        "It is used to process and analyse measurement data produced by "
        "the APx500 Flex Production Tool, and consolidates measurement analysis, module "
        "matching, device provisioning, and configuration into a single interface."
    )
    lines.append("")

    # ── Home Screen ──────────────────────────────────────────────────────────
    lines.append("## Home Screen")
    lines.append("")
    if "01_home" in screenshot_map:
        rel = Path("..") / "screenshots" / "overview" / screenshot_map["01_home"]
        lines.append(f"![DataTools Home Screen]({rel.as_posix()})")
        lines.append("")
    lines.append(
        "The home screen shows four feature tiles. Click a tile to open the corresponding viewer."
    )
    lines.append("")

    # ── Feature Overview ─────────────────────────────────────────────────────
    lines.append("## Features")
    lines.append("")

    lines.append("### Matching Viewer")
    lines.append("")
    lines.append(
        "Inspects driver-module matching data from the production database. "
        "Module pairs are matched algorithmically by frequency-response similarity "
        "so that left and right drivers in a stereo headphone are acoustically consistent."
    )
    lines.append("")
    lines.append("Key tasks:")
    lines.append("")
    lines.append("- Browse Pool, Matched, Paired, and Assembled states")
    lines.append("- Look up any module serial and view its measurement curve")
    lines.append("- Overlay many curves in a single chart for batch inspection")
    lines.append("- Filter all lists by date range")
    lines.append("- Export a read-only CSV snapshot")
    lines.append("")
    lines.append("→ See [Matching Viewer Manual](matching-viewer-manual.md) for detailed workflows.")
    lines.append("")

    lines.append("### Tristar Databases Viewer")
    lines.append("")
    lines.append(
        "Provides a unified read-only view of Serial Number / Firmware (SN/FW) test records "
        "and MAC address provisioning status for Tristar production units. "
        "It also handles automated MAC address assignment for spare backplate units."
    )
    lines.append("")
    lines.append("Key tasks:")
    lines.append("")
    lines.append("- Browse all produced units with their test result, firmware, and parts")
    lines.append("- Filter by date range or look up a specific serial number")
    lines.append("- Check MAC provisioning status per unit")
    lines.append("- Provision spare backplate units with a new MAC address via OCA")
    lines.append("- Export unit and parts data to CSV")
    lines.append("")
    lines.append("→ See [Tristar Databases Manual](tristar-viewer-manual.md) for detailed workflows.")
    lines.append("")

    lines.append("### Measurements Viewer")
    lines.append("")
    lines.append(
        "Loads Audio Precision APx CSV measurement files, visualises frequency-response "
        "charts, and generates reference curves and statistical limit files used by "
        "production test programs."
    )
    lines.append("")
    lines.append("Key tasks:")
    lines.append("")
    lines.append("- Select one or more result folders from the measurements root")
    lines.append("- Plot RMS Level, Phase, THD, Rub-and-Buzz, and L-R Compensation curves")
    lines.append("- Switch between Raw, Median, and Normalised display modes")
    lines.append("- Toggle individual sub-channels (Left / Right / Mono) on and off")
    lines.append("- Run analysis to compute median reference curves and ±σ limits")
    lines.append("- Export Reference CSV, Limit CSV, PNG chart, and a README summary")
    lines.append("")
    lines.append("→ See [Measurements Viewer Manual](measurements-viewer-manual.md) for detailed workflows.")
    lines.append("")

    lines.append("### Settings")
    lines.append("")
    lines.append(
        "Password-protected configuration panel for all DataTools path and provisioning settings. "
        "All values are persisted in a local SQLite store."
    )
    lines.append("")
    lines.append("Configurable items:")
    lines.append("")
    lines.append("| Setting | Description |")
    lines.append("| --- | --- |")
    lines.append("| Measurements Root Folder | Root folder containing Measurements/ and References/ sub-folders |")
    lines.append("| Matching DB path | SQLite database used by the Matching Viewer |")
    lines.append("| SN FW Workstation DB path | SQLite database used by the SN/FW workstation |")
    lines.append("| MAC addresses DB path | SQLite database used by the MAC provisioning system |")
    lines.append("| Backplate Default Serial | Placeholder serial for unprovisioned backplate units |")
    lines.append("| Backplate Default MAC | Placeholder MAC address for unprovisioned backplate units |")
    lines.append("| Settings password | Password required to open the Settings panel |")
    lines.append("")
    lines.append("→ See [Settings Manual](settings-menu-manual.md) for detailed workflows.")
    lines.append("")

    # ── Folder layout ─────────────────────────────────────────────────────────
    lines.append("## Data Folder Layout")
    lines.append("")
    lines.append(
        "All measurement data is organised under a single **Measurements Root Folder** "
        "configured in Settings. The structure mirrors the product hierarchy used at the "
        "production sites."
    )
    lines.append("")
    lines.append("```")
    lines.append("<Measurements Root>/")
    lines.append("├── Measurements/          # Raw APx CSV exports from production")
    lines.append("│   ├── EOL/               # End-of-line test results")
    lines.append("│   │   └── <Year>/")
    lines.append("│   │       └── <Month_Day>/   # One folder per production day")
    lines.append("│   └── GoldenSample/      # Reference golden-sample measurements")
    lines.append("└── References/            # Generated reference and limit CSVs (mirrors Measurements/)")
    lines.append("    ├── EOL/")
    lines.append("    │   └── <Year>/")
    lines.append("    │       └── <Month_Day>/")
    lines.append("    └── GoldenSample/")
    lines.append("```")
    lines.append("")

    # ── Quick-start ───────────────────────────────────────────────────────────
    lines.append("## Quick Start")
    lines.append("")
    lines.append("### First-time setup")
    lines.append("")
    lines.append("1. Click **Settings** and enter the password.")
    lines.append("2. Set the **Measurements Root Folder** to your product's data root.")
    lines.append("3. Set the **Matching DB path** if you use the Matching Viewer.")
    lines.append("4. Set the **SN FW Workstation DB path** and **MAC addresses DB path** if you use Tristar Databases.")
    lines.append("5. Click **Apply** and close Settings.")
    lines.append("")
    lines.append("### Inspecting a daily production batch")
    lines.append("")
    lines.append("1. Open **Measurements Viewer**.")
    lines.append("2. Click **Select Measurements**, choose **EOL**, and select today's folder.")
    lines.append("3. Review the **RMS Level** chart for outliers.")
    lines.append("4. If the batch looks representative, run **Analyze** to update the Reference and Limit files.")
    lines.append("")
    lines.append("### Checking module matching status")
    lines.append("")
    lines.append("1. Open **Matching Viewer**.")
    lines.append("2. Use **Matched** mode to see all suggested pairs awaiting operator confirmation.")
    lines.append("3. Use the serial input to look up a specific module if needed.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DataTools overview manual.")
    parser.add_argument("--title", default="DataTools Overview", help="Document title")
    parser.add_argument(
        "--skip-screenshots", action="store_true", help="Use existing screenshots without capturing"
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
    args = parser.parse_args()

    if args.skip_screenshots:
        files_by_name = {p.name: p for p in SCREENSHOT_DIR.glob("*.png")}
        image_paths = [files_by_name[n] for n in SCREEN_SEQUENCE if n in files_by_name]
        print(f"  Using {len(image_paths)} existing screenshot(s).")
    else:
        print("  Capturing Home-screen screenshot…")
        image_paths = capture_screenshots(clean=True)
        print(f"  Captured {len(image_paths)} screenshot(s).")

    md = _build_markdown(args.title, image_paths)

    if args.embed_images:
        from docs_utils import embed_images_in_markdown
        md = embed_images_in_markdown(md, DOCS_ROOT)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(md, encoding="utf-8")
    print(f"  Written: {OUTPUT_FILE}")

    if args.html:
        from docs_utils import markdown_to_html, embed_images_in_markdown
        md_embedded = embed_images_in_markdown(_build_markdown(args.title, image_paths), DOCS_ROOT)
        html_path = OUTPUT_FILE.with_suffix(".html")
        html_path.write_text(markdown_to_html(md_embedded, args.title), encoding="utf-8")
        print(f"  Written: {html_path}")

    if args.docx:
        from docs_utils import markdown_to_docx
        docx_path = OUTPUT_FILE.with_suffix(".docx")
        docx_path.write_bytes(markdown_to_docx(_build_markdown(args.title, image_paths), DOCS_ROOT, args.title))
        print(f"  Written: {docx_path}")


if __name__ == "__main__":
    main()
