"""
DataTools Measurements Viewer Documentation Generator
=====================================================

Generates a Markdown user manual for the DataTools Measurements viewer and
auto-captures a deterministic screenshot set.

Default behaviour:
- Captures fresh screenshots from the Measurements viewer flow
- Creates/overwrites docs/generated/measurements-viewer-manual.md
- Embeds each screenshot inline for complete end-to-end user guidance

Screenshot data used:
- Stereo example : H715 EOL  2026/6_25  (Senmai Production)
- Mono example   : Sub8PRO EOL  2026/6_23  (Tristar Production)

Usage examples:
- python DataTools/docs/scripts/generate_measurements_markdown.py
- python DataTools/docs/scripts/generate_measurements_markdown.py --skip-screenshots
- python DataTools/docs/scripts/generate_measurements_markdown.py --title "Measurements Viewer Manual (v0.1)"
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
from kivy.uix.boxlayout import BoxLayout


DOCS_ROOT = Path(__file__).resolve().parent.parent
DATATOOLS_ROOT = DOCS_ROOT.parent
SCREENSHOT_DIR = DOCS_ROOT / "screenshots" / "measurements-viewer"
OUTPUT_FILE = DOCS_ROOT / "generated" / "measurements-viewer-manual.md"

# Data folders used for documentation screenshots
_SENMAI_ROOT = Path(
    r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dateien von Senmai Production - H715_EOL"
)
_TRISTAR_ROOT = Path(
    r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dateien von Tristar Production - Documents\Sub8PRO"
)
_STEREO_FOLDER = _SENMAI_ROOT / "Measurements" / "EOL" / "2026" / "6_25"
_MONO_FOLDER   = _TRISTAR_ROOT / "Measurements" / "EOL" / "2026" / "6_23PilotProduction"

SCREEN_SEQUENCE = [
    "01_measurements_home.png",
    "02_measurements_selection_popup.png",
    "03_measurements_chart_stereo_rms.png",
    "04_measurements_chart_stereo_phase.png",
    "05_measurements_chart_mono_rms.png",
    "06_measurements_analysis_dialog.png",
]


def _import_app_modules():
    if str(DATATOOLS_ROOT) not in sys.path:
        sys.path.insert(0, str(DATATOOLS_ROOT))

    from app.main import HomeScreen
    from app.measurements_viewer import (
        MeasurementLoader,
        MeasurementSelectionPopup,
        MeasurementsViewerRoot,
        AnalysisDialog,
        _load_category_refs,
        _load_lr_diff,
    )
    from app.settings_store import DataToolsSettingsStore

    return (
        HomeScreen,
        MeasurementsViewerRoot,
        MeasurementLoader,
        MeasurementSelectionPopup,
        AnalysisDialog,
        _load_category_refs,
        _load_lr_diff,
        DataToolsSettingsStore,
    )


class MeasurementsDocCaptureApp(App):
    """Deterministic capture app for Measurements viewer documentation screenshots."""

    title = "DataTools Measurements Doc Capture"

    def __init__(self, screenshot_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = screenshot_dir
        self.store = None
        self.scene_root = None
        self.home_screen = None
        self.viewer = None
        self.selection_popup = None
        self.analysis_dialog = None

        (
            self.HomeScreen,
            self.MeasurementsViewerRoot,
            self.MeasurementLoader,
            self.MeasurementSelectionPopup,
            self.AnalysisDialog,
            self._load_category_refs,
            self._load_lr_diff,
            self.DataToolsSettingsStore,
        ) = _import_app_modules()

    def build(self):
        self.store = self.DataToolsSettingsStore(DATATOOLS_ROOT)
        self.store.set("measurements_root_path", str(_SENMAI_ROOT))

        self.home_screen = self.HomeScreen(settings_store=self.store)
        self.scene_root = BoxLayout()
        self.scene_root.add_widget(self.home_screen)
        return self.scene_root

    def on_start(self):
        Window.size = (1920, 1080)
        Clock.schedule_once(self._prepare_home, 1.0)

    def _prepare_home(self, _dt):
        """Force full layout on the home screen before capturing."""
        self.home_screen.size = Window.size
        self.home_screen.pos = (0, 0)
        self.home_screen.do_layout()
        Clock.schedule_once(self._capture_home, 0.35)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _take_widget(self, widget, filename: str):
        """Capture current window frame (no alpha transparency)."""
        self._take_window(filename)

    def _take_window(self, filename: str):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        target = self.screenshot_dir / filename
        saved = Path(Window.screenshot(name=str(target)))
        if saved.exists() and saved != target:
            target.unlink(missing_ok=True)
            saved.replace(target)

    # ------------------------------------------------------------------
    # Capture sequence
    # ------------------------------------------------------------------

    def _capture_home(self, _dt):
        """01 — Home screen."""
        self._take_widget(self.home_screen, "01_measurements_home.png")

        # Build the measurements viewer (uses Senmai / H715 root)
        self.viewer = self.MeasurementsViewerRoot(
            settings_store=self.store,
            on_back=lambda: None,
        )
        # Prevent the viewer's __init__ auto-popup (fires at +0.2 s via Clock).
        # Setting root_path=None here causes _open_selection_popup() to bail out
        # immediately when that scheduled lambda fires.
        self.viewer.root_path = None
        self.scene_root.clear_widgets()
        self.scene_root.add_widget(self.viewer)
        Clock.schedule_once(self._capture_selection_popup, 0.6)

    def _capture_selection_popup(self, _dt):
        """02 — Selection popup with EOL category and folder list visible."""
        self.selection_popup = self.MeasurementSelectionPopup(
            root_path=_SENMAI_ROOT,
            on_confirm=lambda *_: None,
        )
        self.selection_popup.open()
        Clock.schedule_once(self._capture_popup_shot, 0.6)

    def _capture_popup_shot(self, _dt):
        self._take_window("02_measurements_selection_popup.png")
        self.selection_popup.dismiss()
        Clock.schedule_once(self._load_stereo, 0.3)

    def _load_stereo(self, _dt):
        """Load H715 stereo data directly and wait for chart to render."""
        runs = self.MeasurementLoader.load_folders([_STEREO_FOLDER])
        if not runs:
            print(f"WARNING: No stereo runs found in {_STEREO_FOLDER}")
            Clock.schedule_once(lambda _: self.stop(), 0.2)
            return

        self.viewer._current_category = "EOL"
        self.viewer._current_runs = runs
        self.viewer._analyze_btn.disabled = False
        self.viewer._analyze_btn.opacity = 1.0
        self.viewer._show_chart()
        self.viewer._chart.set_cat_refs(
            self._load_category_refs(_SENMAI_ROOT, "EOL")
        )
        lr_diff = self._load_lr_diff(_SENMAI_ROOT / "References" / "EOL" / "L-R-Diff.csv")
        if lr_diff is None:
            lr_diff = self._load_lr_diff(_SENMAI_ROOT / "References" / "L-R-Diff.csv")
        self.viewer._lr_diff_data = lr_diff
        self.viewer._chart.set_lr_diff(lr_diff)
        # Delay load_data so the chart widget is fully laid out before rendering curves
        Clock.schedule_once(lambda _: self.viewer._chart.load_data(runs), 0.5)
        Clock.schedule_once(self._capture_stereo_rms, 1.5)

    def _capture_stereo_rms(self, _dt):
        """03 — Stereo chart, RMS Level selected."""
        if "RMS_Level" in self.viewer._chart._type_buttons:
            self.viewer._chart._select_type("RMS_Level")
        Clock.schedule_once(lambda _dt2: self._take_widget(
            self.viewer, "03_measurements_chart_stereo_rms.png"
        ), 0.6)
        Clock.schedule_once(self._capture_stereo_phase, 1.2)

    def _capture_stereo_phase(self, _dt):
        """04 — Stereo chart, Phase selected."""
        if "Phase" in self.viewer._chart._type_buttons:
            self.viewer._chart._select_type("Phase")
        Clock.schedule_once(lambda _dt2: self._take_widget(
            self.viewer, "04_measurements_chart_stereo_phase.png"
        ), 0.6)
        Clock.schedule_once(self._load_mono, 1.2)

    def _load_mono(self, _dt):
        """Load Sub8PRO mono data."""
        runs = self.MeasurementLoader.load_folders([_MONO_FOLDER])
        if not runs:
            print(f"WARNING: No mono runs found in {_MONO_FOLDER}")
            Clock.schedule_once(self._capture_analysis_dialog, 0.2)
            return

        self.viewer._current_category = "EOL"
        self.viewer._current_runs = runs
        self.viewer._show_chart()
        lr_diff = self._load_lr_diff(_TRISTAR_ROOT / "References" / "EOL" / "L-R-Diff.csv")
        if lr_diff is None:
            lr_diff = self._load_lr_diff(_TRISTAR_ROOT / "References" / "L-R-Diff.csv")
        self.viewer._lr_diff_data = lr_diff
        self.viewer._chart.set_lr_diff(lr_diff)
        self.viewer._chart.set_cat_refs(
            self._load_category_refs(_TRISTAR_ROOT, "EOL")
        )
        # Delay load_data so the chart widget is fully laid out before rendering curves
        Clock.schedule_once(lambda _: self.viewer._chart.load_data(runs), 0.5)
        Clock.schedule_once(self._capture_mono_rms, 1.5)

    def _capture_mono_rms(self, _dt):
        """05 — Mono chart, RMS Level."""
        if "RMS_Level" in self.viewer._chart._type_buttons:
            self.viewer._chart._select_type("RMS_Level")
        Clock.schedule_once(lambda _dt2: self._take_widget(
            self.viewer, "05_measurements_chart_mono_rms.png"
        ), 0.6)
        # Restore stereo runs for the analysis dialog screenshot
        Clock.schedule_once(self._restore_stereo_for_analysis, 1.2)

    def _restore_stereo_for_analysis(self, _dt):
        runs = self.MeasurementLoader.load_folders([_STEREO_FOLDER])
        self.viewer._current_category = "EOL"
        self.viewer._current_runs = runs
        Clock.schedule_once(lambda _: self.viewer._chart.load_data(runs), 0.3)
        Clock.schedule_once(self._capture_analysis_dialog, 1.0)

    def _capture_analysis_dialog(self, _dt):
        """06 — Analysis dialog open."""
        if not self.viewer._current_runs:
            Clock.schedule_once(lambda _: self.stop(), 0.2)
            return

        self.analysis_dialog = self.AnalysisDialog(
            runs=self.viewer._current_runs,
            lr_diff_existing=self.viewer._lr_diff_data,
            root_path=_SENMAI_ROOT,
            category="EOL",
            settings_store=self.store,
            on_done=lambda _msg: None,
        )
        self.analysis_dialog.open()
        Clock.schedule_once(self._take_analysis_and_stop, 0.7)

    def _take_analysis_and_stop(self, _dt):
        self._take_window("06_measurements_analysis_dialog.png")
        if self.analysis_dialog:
            self.analysis_dialog.dismiss()
        Clock.schedule_once(lambda _: self.stop(), 0.2)


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------

def capture_screenshots(clean: bool = True) -> list[Path]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for p in SCREENSHOT_DIR.glob("*.png"):
            p.unlink(missing_ok=True)

    MeasurementsDocCaptureApp(screenshot_dir=SCREENSHOT_DIR).run()

    files_by_name = {p.name: p for p in SCREENSHOT_DIR.glob("*.png")}
    return [files_by_name[name] for name in SCREEN_SEQUENCE if name in files_by_name]


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _img(screenshot_map: dict, stem: str) -> str:
    """Return a relative-path image tag if the screenshot exists."""
    if stem not in screenshot_map:
        return ""
    rel = (Path("..") / "screenshots" / "measurements-viewer" / screenshot_map[stem]).as_posix()
    return f"![{stem}]({rel})"


def _build_markdown(title: str, image_paths: list[Path]) -> str:
    sm = {p.stem: p.name for p in image_paths}
    L: list[str] = []

    def ln(s: str = ""):
        L.append(s)

    ln(f"# {title}")
    ln()
    ln("This manual covers the full workflow for loading APx measurement CSV files,")
    ln("visualising frequency-response charts, and generating reference curves and limit files.")
    ln()

    # ── Overview ──────────────────────────────────────────────────────────
    ln("## Overview")
    ln()
    ln("The Measurements viewer provides three main functions:")
    ln()
    ln("1. **Select Measurements** — choose a product category and one or more result folders.")
    ln("2. **Chart** — visualise individual runs, medians, limits and sub-channel curves.")
    ln("3. **Create Refs...** — compute median reference curves and statistical limits; export CSVs, PNG plots and a README.")
    ln()

    # ── Home ──────────────────────────────────────────────────────────────
    ln("## Home Screen")
    ln()
    tag = _img(sm, "01_measurements_home")
    if tag:
        ln(tag)
        ln()
    ln("Click the **Measurements** tile to open the viewer.")
    ln()

    # ── Selection Popup ───────────────────────────────────────────────────
    ln("## Selecting Measurements")
    ln()
    tag = _img(sm, "02_measurements_selection_popup")
    if tag:
        ln(tag)
        ln()
    ln("The **Select Measurements** popup opens automatically when the viewer starts.")
    ln("It can also be reopened at any time via the **Select Measurements** button.")
    ln()
    ln("### Step 1 — Choose a Category")
    ln()
    ln("Toggle buttons at the top select the measurement category:")
    ln()
    ln("| Category | Description |")
    ln("| --- | --- |")
    ln("| EOL | End-of-line production measurements |")
    ln("| GoldenSample | Reference golden-sample measurements |")
    ln("| Reference | Reference measurements for limit generation |")
    ln()
    ln("### Step 2 — Select Result Folders")
    ln()
    ln("The scrollable list shows all available result folders under `Measurements/<Category>/`.")
    ln("Multiple folders can be selected at once — all selected runs are loaded together.")
    ln()
    ln("Click **Open** to load the selection into the chart.")
    ln()

    # ── Chart (stereo) ────────────────────────────────────────────────────
    ln("## Chart — Stereo Example (H715)")
    ln()
    tag = _img(sm, "03_measurements_chart_stereo_rms")
    if tag:
        ln(tag)
        ln()
    ln("### Measurement Type")
    ln()
    ln("Buttons in the **Measurement** row switch the plotted data type:")
    ln()
    ln("| Type | Y-axis | Description |")
    ln("| --- | --- | --- |")
    ln("| RMS Level | dBSPL | Frequency-response amplitude |")
    ln("| Phase | degrees | Frequency-response phase |")
    ln("| THD | % | Total Harmonic Distortion |")
    ln("| RnB Crest | dB | Rub-and-Buzz crest factor |")
    ln("| RnB Peak Ratio | dB | Rub-and-Buzz peak ratio |")
    ln("| L-R Compensation | dB | Left-Right difference curve (only when loaded) |")
    ln()
    ln("### Display Mode")
    ln()
    ln("| Mode | Description |")
    ln("| --- | --- |")
    ln("| Raw | All individual measurement curves (semi-transparent) |")
    ln("| Median | Per-channel median curve only |")
    ln("| Norm. | Each curve shown as deviation from its channel median |")
    ln()
    ln("### Input Channel")
    ln()
    ln("For multi-input measurements, the **Input** row filters to one input channel at a time.")
    ln()
    ln("### Sub-Channel (Channel row)")
    ln()
    ln("When a measurement type has multiple sub-columns (e.g. Left / Right for stereo),")
    ln("individual sub-channels can be toggled on and off independently.")
    ln()
    ln("### L-R Compensation (stereo RMS Level only)")
    ln()
    ln("When a `L-R-Diff.csv` fixture compensation curve is present,")
    ln("the **Compensation** row appears for RMS Level in stereo mode:")
    ln()
    ln("| Setting | Effect |")
    ln("| --- | --- |")
    ln("| Off | Raw levels displayed |")
    ln("| On | L-R difference applied (±½ diff per channel) to equalise fixture offsets |")
    ln()

    # ── Chart (phase) ─────────────────────────────────────────────────────
    ln("## Chart — Phase View")
    ln()
    tag = _img(sm, "04_measurements_chart_stereo_phase")
    if tag:
        ln(tag)
        ln()
    ln("Switching to the **Phase** type shows the frequency-response phase curves.")
    ln("Reference limit bands (if available) are overlaid automatically.")
    ln()

    # ── Chart (mono) ──────────────────────────────────────────────────────
    ln("## Chart — Mono Example (Sub8PRO)")
    ln()
    tag = _img(sm, "05_measurements_chart_mono_rms")
    if tag:
        ln(tag)
        ln()
    ln("Measurements with a single data column show one curve set.")
    ln("The Channel sub-column row and the Compensation toggle are not shown.")
    ln("A single-input product can still have Left/Right sub-columns — in that case")
    ln("the Channel row and Compensation toggle appear just as they do for multi-input data.")
    ln()

    # ── Analysis Dialog ────────────────────────────────────────────────────
    ln("## Analysis Dialog")
    ln()
    tag = _img(sm, "06_measurements_analysis_dialog")
    if tag:
        ln(tag)
        ln()
    ln("Open via the **Create Refs...** button (available after data is loaded).")
    ln()
    ln("### Reference Type (stereo only)")
    ln()
    ln("| Option | Description |")
    ln("| --- | --- |")
    ln("| Stereo | Separate Left and Right reference curves |")
    ln("| Mono | Average Left and Right into a single reference curve |")
    ln()
    ln("### Compensation (stereo only)")
    ln()
    ln("| Option | Description |")
    ln("| --- | --- |")
    ln("| On | Apply L-R fixture compensation before computing the reference |")
    ln("| Off | Compute reference without compensation |")
    ln()
    ln("### L-R Diff (stereo only)")
    ln()
    ln("| Option | Description |")
    ln("| --- | --- |")
    ln("| Use existing | Load `L-R-Diff.csv` from the References folder |")
    ln("| Compute new | Recompute from current measurements and export Right−Left |")
    ln()
    ln("### Smoothing")
    ln()
    ln("1/N octave log-scale smoothing applied to reference and limit curves before export.")
    ln("`None` disables smoothing.")
    ln()
    ln("### Per-Type Limit Settings")
    ln()
    ln("Each measurement type (RMS Level, Phase, THD) has independent limit settings:")
    ln()
    ln("| Control | Description |")
    ln("| --- | --- |")
    ln("| σ× | Limit width = value × standard deviation (frequency-dependent) |")
    ln("| +/− | Fixed absolute offset — stored as a constant 2-point boundary line |")
    ln("| Value | Multiplier (σ× mode) or offset magnitude (+/− mode) |")
    ln("| f low | Lower frequency bound for limit computation [Hz] |")
    ln("| f high | Upper frequency bound for limit computation [Hz] |")
    ln()
    ln("### Output Path")
    ln()
    ln("The output folder is set via the **…** Browse button.")
    ln("All files are written into this folder:")
    ln()
    ln("| File / Folder | Content |")
    ln("| --- | --- |")
    ln("| `RMS.csv` | Median RMS reference curve(s) |")
    ln("| `Phase.csv` | Median phase reference curve(s) |")
    ln("| `THD.csv` | Median THD reference curve(s) |")
    ln("| `L-R-Diff.csv` | Right−Left compensation curve (if Compute new selected) |")
    ln("| `Limits/` | Six limit CSVs (upper/lower per type) |")
    ln("| `Plots/` | PNG plots: individual curves + median + limit bands |")
    ln("| `README.md` | Deployment instructions and file overview |")
    ln()
    ln("Click **Generate** to run the analysis and save all files.")
    ln()

    # ── Deploying the analysis output ─────────────────────────────────────
    ln("## Deploying the Analysis Output")
    ln()
    ln("The workstation reads references from a `References/` folder inside the")
    ln("measurements root directory (configured in **Settings → Measurements Root Folder**).")
    ln()
    ln("Copy the generated files as follows:")
    ln()
    ln("```")
    ln("<Measurements root>/")
    ln("├── References/")
    ln("│   ├── EOL/                 ← or GoldenSample — mirrors the Measurements structure")
    ln("│   │   ├── RMS.csv")
    ln("│   │   ├── Phase.csv")
    ln("│   │   ├── THD.csv")
    ln("│   │   └── Limits/          ← copy the limit files here")
    ln("│   │       ├── RMS.csv")
    ln("│   │       ├── PhaseUpper.csv")
    ln("│   │       ├── PhaseLower.csv")
    ln("│   │       └── THD.csv")
    ln("│   ├── GoldenSample/        ← same structure if GoldenSample refs exist")
    ln("│   │   └── ...")
    ln("│   └── L-R-Diff.csv         ← stereo only: shared Left/Right compensation curve")
    ln("└── ...")
    ln("```")
    ln()
    ln("> **Note:** The `Plots/` subfolder contains PNG overview charts for visual")
    ln("> inspection. These plots are **not** used by the workstation.")
    ln()
    ln("### Exported File Reference")
    ln()
    ln("| File | Description | Unit |")
    ln("| --- | --- | --- |")
    ln("| `RMS.csv` | Median RMS level reference curve(s) | dBSPL |")
    ln("| `Phase.csv` | Median phase reference curve(s) | deg |")
    ln("| `THD.csv` | Median THD reference curve(s) | % |")
    ln("| `L-R-Diff.csv` | Median Right−Left difference curve (stereo only) | dB |")
    ln("| `Limits/RMS.csv` | RMS tolerance — half-width of the pass band | dB |")
    ln("| `Limits/PhaseUpper.csv` | Phase upper tolerance | deg |")
    ln("| `Limits/PhaseLower.csv` | Phase lower tolerance (negated) | deg |")
    ln("| `Limits/THD.csv` | THD tolerance as a relative factor | % |")
    ln()
    ln("All CSV files use the **AP 4-header format**: 4 rows of header followed by X/Y data pairs.")
    ln()
    ln("### Limit Modes")
    ln()
    ln("Each measurement type can use one of two limit modes:")
    ln()
    ln("| Mode | Stored as | Description |")
    ln("| --- | --- | --- |")
    ln("| **σ×** | Full-resolution curve | Limit = value × standard deviation at each frequency point |")
    ln("| **+/−** | 2-point boundary line | Fixed absolute offset — constant across the frequency range |")
    ln()
    ln("The chosen mode and value are recorded in the `README.md` inside the export folder.")
    ln()

    # ── Measurements Root Folder ───────────────────────────────────────────
    ln("## Measurements Root Folder")
    ln()
    ln("The root folder must follow this structure:")
    ln()
    ln("```")
    ln("Root/")
    ln("  Measurements/")
    ln("    EOL/                 ← or GoldenSample")
    ln("      2026/")
    ln("        6_25/            ← result folder (one run = one set of CSV files)")
    ln("    GoldenSample/        ← same structure")
    ln("      2026/")
    ln("        ...")
    ln("  References/            ← mirrors the Measurements category structure")
    ln("    EOL/")
    ln("      RMS.csv            ← median reference (generated by Create Refs...)")
    ln("      Phase.csv")
    ln("      THD.csv")
    ln("      Limits/")
    ln("    GoldenSample/        ← same structure")
    ln("      ...")
    ln("    L-R-Diff.csv         ← stereo only: shared compensation curve")
    ln("```")
    ln()
    ln("Configure the root folder in **Settings → Measurements Root Folder**.")    
    ln()

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------

def generate(title: str, embed: bool = False, html: bool = False, docx: bool = False) -> Path:
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
    parser = argparse.ArgumentParser(
        description="Generate DataTools Measurements Viewer markdown documentation."
    )
    parser.add_argument(
        "--title",
        default="DataTools Measurements Viewer",
        help="Title used as the top-level markdown heading.",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Do not capture screenshots — only generate markdown from existing PNGs.",
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
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing screenshots when capturing new ones.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.skip_screenshots:
        captured = capture_screenshots(clean=not args.keep_existing)
        print(f"Captured screenshots: {len(captured)}")

    output_path = generate(title=args.title, embed=args.embed_images, html=args.html, docx=args.docx)
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
