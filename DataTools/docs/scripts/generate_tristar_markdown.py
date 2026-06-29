"""
DataTools Tristar Databases Viewer Documentation Generator
========================================================

This script generates comprehensive Markdown documentation for the DataTools
Tristar Databases Viewer and Backplate Provisioning feature.

Default behavior:
- Captures fresh screenshots from the Tristar viewer and provisioning flows
- Creates/overwrites docs/generated/tristar-viewer-manual.md
- Embeds each screenshot inline for complete end-to-end user guidance

Usage examples:
- python DataTools/docs/scripts/generate_tristar_markdown.py
- python DataTools/docs/scripts/generate_tristar_markdown.py --skip-screenshots
- python DataTools/docs/scripts/generate_tristar_markdown.py --title "Tristar Databases Manual (v0.1)"
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


DOCS_ROOT = Path(__file__).resolve().parent.parent
DATATOOLS_ROOT = DOCS_ROOT.parent
SCREENSHOT_DIR = DOCS_ROOT / "screenshots" / "tristar-viewer"
OUTPUT_FILE = DOCS_ROOT / "generated" / "tristar-viewer-manual.md"

SCREEN_SEQUENCE = [
    "01_tristar_home.png",
    "02_tristar_viewer_main.png",
    "03_tristar_filter_popup.png",
    "04_tristar_parts_details.png",
    "05_backplate_provisioning_popup.png",
]


def _import_app_modules():
    """Import DataTools app modules after adding DataTools root to sys.path."""
    if str(DATATOOLS_ROOT) not in sys.path:
        sys.path.insert(0, str(DATATOOLS_ROOT))

    from app.main import HomeScreen
    from app.tristar_databases_viewer import (
        TristarDatabasesViewerRoot,
        ListTimeframeFilterPopup,
        BackplateProvisioningPopup,
    )
    from app.settings_store import DataToolsSettingsStore

    return (
        HomeScreen,
        TristarDatabasesViewerRoot,
        ListTimeframeFilterPopup,
        BackplateProvisioningPopup,
        DataToolsSettingsStore,
    )


class TristarDocCaptureApp(App):
    """Deterministic capture app for Tristar Viewer documentation screenshots."""

    title = "DataTools Tristar Viewer Doc Capture"

    def __init__(self, screenshot_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = screenshot_dir
        self.store = None
        self.home_screen = None
        self.viewer = None
        self.filter_popup = None
        self.provisioning_popup = None

        (
            self.HomeScreen,
            self.TristarDatabasesViewerRoot,
            self.ListTimeframeFilterPopup,
            self.BackplateProvisioningPopup,
            self.DataToolsSettingsStore,
        ) = _import_app_modules()

    def build(self):
        """Build home screen and initialize viewer for screenshot capture."""
        self.store = self.DataToolsSettingsStore(DATATOOLS_ROOT)

        # Stable data paths for repeatable docs generation
        self.store.set(
            "sn_fw_db_path",
            str((DATATOOLS_ROOT.parent / "SubPro_SN_FW_Workstation" / "Data" / "subpro_workstation.db").resolve()),
        )
        self.store.set(
            "mac_db_path",
            str((DATATOOLS_ROOT.parent / "SubProMACAddresses" / "db" / "mac_addresses.db").resolve()),
        )
        self.store.set(
            "default_export_folder",
            str((DATATOOLS_ROOT / "Exports").resolve()),
        )

        self.home_screen = self.HomeScreen(settings_store=self.store)
        return self.home_screen

    def on_start(self):
        """Start the timed screenshot sequence when UI is ready."""
        Window.size = (1280, 800)
        Clock.schedule_once(self._capture_home, 1.0)

    def _take(self, filename: str):
        """Take one screenshot of the current window state."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        target = self.screenshot_dir / filename
        saved = Path(Window.screenshot(name=str(target)))

        # Normalize Kivy-generated filename with counter
        if saved.exists() and saved != target:
            target.unlink(missing_ok=True)
            saved.replace(target)

    def _capture_home(self, _dt):
        """Capture home screen and proceed to Tristar viewer."""
        home_target = self.screenshot_dir / "01_tristar_home.png"
        home_target.unlink(missing_ok=True)
        self.home_screen.export_to_png(str(home_target))

        # Open Tristar viewer
        self.viewer = self.TristarDatabasesViewerRoot(
            settings_store=self.store,
            on_back=lambda: None
        )
        self.home_screen.add_widget(self.viewer)
        Clock.schedule_once(self._capture_viewer, 0.8)

    def _capture_viewer(self, _dt):
        """Capture main viewer and proceed to filter popup."""
        self._take("02_tristar_viewer_main.png")
        Clock.schedule_once(self._capture_filter_popup, 0.3)

    def _capture_filter_popup(self, _dt):
        """Capture filter date range popup."""
        self.filter_popup = self.ListTimeframeFilterPopup(
            title="Filter by Date Range",
            current_items=[],
            on_apply=lambda items: None,
        )
        self.filter_popup.open()
        Clock.schedule_once(self._after_filter_popup, 0.5)

    def _after_filter_popup(self, _dt):
        """Capture filter and proceed to provisioning."""
        self._take("03_tristar_filter_popup.png")
        if self.filter_popup:
            self.filter_popup.dismiss()
        Clock.schedule_once(self._capture_provisioning_popup, 0.3)

    def _capture_provisioning_popup(self, _dt):
        """Capture backplate provisioning popup."""
        self.provisioning_popup = self.BackplateProvisioningPopup(
            settings_store=self.store
        )
        self.provisioning_popup.open()
        Clock.schedule_once(self._finish_capture, 1.0)

    def _finish_capture(self, _dt):
        """Take final screenshot and stop app."""
        self._take("05_backplate_provisioning_popup.png")
        if self.provisioning_popup:
            self.provisioning_popup.dismiss()
        Clock.schedule_once(lambda _: self.stop(), 0.3)


def capture_screenshots(clean: bool = True) -> list[Path]:
    """
    Capture deterministic Tristar Viewer UI screenshots.

    Args:
        clean: Delete existing screenshot PNG files before capturing.

    Returns:
        Sorted list of screenshot paths after capture.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for path in SCREENSHOT_DIR.glob("*.png"):
            path.unlink(missing_ok=True)

    TristarDocCaptureApp(screenshot_dir=SCREENSHOT_DIR).run()

    # Keep expected order
    files_by_name = {path.name: path for path in SCREENSHOT_DIR.glob("*.png")}
    ordered = [files_by_name[name] for name in SCREEN_SEQUENCE if name in files_by_name]
    return ordered


def _build_markdown(title: str, image_paths: list[Path]) -> str:
    """
    Create comprehensive Markdown documentation for Tristar Databases Viewer.
    Includes inline screenshots and complete user workflows.

    Args:
        title: Main document title.
        image_paths: Sorted list of screenshot file paths.

    Returns:
        Full Markdown text for the output file.
    """
    lines: list[str] = []
    screenshot_map = {path.stem: path.name for path in image_paths}

    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(
        "The Tristar Databases Viewer is a unified read-only interface for monitoring "
        "Serial Number/Firmware (SN/FW) testing data and MAC address provisioning status. "
        "It also provides automated MAC address provisioning for spare backplate units."
    )
    lines.append("")
    lines.append("### Key Features")
    lines.append("")
    lines.append("- **Unified View**: Combine data from two databases (SN/FW and MAC addresses)")
    lines.append("- **Real-time Monitoring**: View test results, part configurations, and MAC status")
    lines.append("- **Date Range Filtering**: Filter units by test completion timeframe")
    lines.append("- **Serial Lookup**: Quick search for specific device serial numbers")
    lines.append("- **CSV Export**: Export complete unit and parts data with MAC information")
    lines.append("- **Backplate Provisioning**: Automatic MAC address assignment for new backplate units")
    lines.append("")
    lines.append("## Prerequisites")
    lines.append("")
    lines.append("Before using the Tristar Viewer, ensure:")
    lines.append("")
    lines.append("- Both SN/FW and MAC databases are accessible via Settings")
    lines.append("- For Backplate Provisioning: OCA devices are reachable on the network")
    lines.append("- For Backplate Provisioning: MAC pool is configured with available addresses")
    lines.append("")
    lines.append("## Quick Start")
    lines.append("")
    lines.append("1. **From Home**: Click the Tristar Databases tile")
    lines.append("2. **View Data**: Browse all units with their test results and MAC status")
    lines.append("3. **Filter**: Click Filter to narrow results by date range (optional)")
    lines.append("4. **Search**: Use Serial Lookup to find a specific device")
    lines.append("5. **Export**: Click Export CSV to save data to file")
    lines.append("6. **Provision**: Click Provision Backplate for automated MAC assignment")
    lines.append("")
    lines.append("## Home Screen")
    lines.append("")
    if "01_tristar_home" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "tristar-viewer" / screenshot_map["01_tristar_home"]
        lines.append(f"![Home Screen]({rel_path.as_posix()})")
        lines.append("")
    lines.append("The home screen displays the Tristar Databases tile along with other DataTools features.")
    lines.append("")
    lines.append("## Tristar Viewer Main Window")
    lines.append("")
    if "02_tristar_viewer_main" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "tristar-viewer" / screenshot_map["02_tristar_viewer_main"]
        lines.append(f"![Tristar Viewer Main]({rel_path.as_posix()})")
        lines.append("")
    lines.append("### Header Section")
    lines.append("")
    lines.append("- **Title Bar**: Shows 'Tristar Databases' with Back to Home button")
    lines.append("- **Database Path**: Displays the SN/FW database location")
    lines.append("")
    lines.append("### Toolbar Buttons")
    lines.append("")
    lines.append("| Button | Function |")
    lines.append("| --- | --- |")
    lines.append("| Refresh | Reload data from databases |")
    lines.append("| Filter | Open date range filter popup |")
    lines.append("| Export CSV | Save unit and parts data to CSV file |")
    lines.append("| Provision Backplate | Auto-assign MAC to spare backplate units |")
    lines.append("")
    lines.append("### Summary Panel")
    lines.append("")
    lines.append("Displays aggregate statistics:")
    lines.append("- **Total Units**: Count of unique serial numbers")
    lines.append("- **With MAC**: Units that have been MAC provisioned")
    lines.append("- **Parts Complete**: Units with all expected parts scanned")
    lines.append("")
    lines.append("### MAC Pool Status")
    lines.append("")
    lines.append("Shows provisioning pool statistics:")
    lines.append("- **Range**: MAC address start and end")
    lines.append("- **Next MAC**: Next available address to assign")
    lines.append("- **Remaining**: Count of unassigned MACs")
    lines.append("- **Provisioned**: Count of already-assigned MACs")
    lines.append("")
    lines.append("### Units List")
    lines.append("")
    lines.append("Two-row layout per unit:")
    lines.append("- **Row 1**: Serial number and current MAC (or '-' if not yet provisioned)")
    lines.append("- **Row 2**: Test result, timestamp, parts status (green = complete, red = incomplete)")
    lines.append("")
    lines.append("Click a unit row to view its scanned parts and serial numbers.")
    lines.append("")
    lines.append("## Date Range Filter")
    lines.append("")
    if "03_tristar_filter_popup" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "tristar-viewer" / screenshot_map["03_tristar_filter_popup"]
        lines.append(f"![Filter Popup]({rel_path.as_posix()})")
        lines.append("")
    lines.append("### Supported Date Formats")
    lines.append("")
    lines.append("| Format | Example |")
    lines.append("| --- | --- |")
    lines.append("| Date only | YYYY-MM-DD (2026-06-29) |")
    lines.append("| Date + Time (ISO) | YYYY-MMTHH:MM (2026-06-29T14:30) |")
    lines.append("| Date + Time (Space) | YYYY-MM-DD HH:MM (2026-06-29 14:30) |")
    lines.append("| Full timestamp | YYYY-MM-DD HH:MM:SS (2026-06-29 14:30:45) |")
    lines.append("")
    lines.append("### Workflow")
    lines.append("")
    lines.append("1. Click **Filter** button in toolbar")
    lines.append("2. Enter **Start Date** (default: 30 days ago)")
    lines.append("3. Enter **End Date** (default: today)")
    lines.append("4. Click **Apply** to filter units")
    lines.append("5. Results update to show only units in date range")
    lines.append("")
    lines.append("## Backplate Provisioning")
    lines.append("")
    if "05_backplate_provisioning_popup" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "tristar-viewer" / screenshot_map["05_backplate_provisioning_popup"]
        lines.append(f"![Backplate Provisioning]({rel_path.as_posix()})")
        lines.append("")
    lines.append("### Overview")
    lines.append("")
    lines.append(
        "The Backplate Provisioning feature enables automatic MAC address assignment "
        "for spare units without manual intervention. Suitable for production assembly lines."
    )
    lines.append("")
    lines.append("### Automatic Workflow")
    lines.append("")
    lines.append("1. **Connect Device**: Connect OCA-enabled device to network")
    lines.append("2. **Auto-Discovery**: Popup searches for device (every 2 seconds)")
    lines.append("3. **Auto-Read**: Serial number and current MAC read from device")
    lines.append("4. **Auto-Validate**:")
    lines.append("   - If MAC = Default → Ready to provision")
    lines.append("   - If MAC ≠ Default & in DB → Already provisioned (no action)")
    lines.append("   - If MAC ≠ Default & unknown → Error (manual investigation)")
    lines.append("5. **Auto-Unlock**: Device factory settings unlocked")
    lines.append("6. **Auto-Provision**: MAC address assigned from pool and written to device")
    lines.append("7. **Verify**: MAC read back and confirmed")
    lines.append("8. **Database Update**: Provisioning logged to database")
    lines.append("9. **Disconnect**: Device can be removed, ready for next unit")
    lines.append("")
    lines.append("### Status Messages")
    lines.append("")
    lines.append("| Status | Meaning | Action |")
    lines.append("| --- | --- | --- |")
    lines.append("| [Searching...] | Looking for OCA device | Wait, check network |")
    lines.append("| [Connected] Device | Device found, reading... | None (automatic) |")
    lines.append("| [OK] Provisioned | MAC successfully assigned | Disconnect device |")
    lines.append("| [ERROR] ... | Problem occurred | Check message, retry |")
    lines.append("")
    lines.append("### Status Panel Fields")
    lines.append("")
    lines.append("- **Device**: Current connection status and device name")
    lines.append("- **Serial**: Current device serial number")
    lines.append("- **MAC**: Current device MAC address (before/after provisioning)")
    lines.append("- **Status**: Detailed message about provisioning state")
    lines.append("")
    lines.append("### Workflow Example")
    lines.append("")
    lines.append("```")
    lines.append("1. [Searching...]  → No device connected yet")
    lines.append("2. [Connected] SubPro-123ABC  → Device found")
    lines.append("   Serial: SP12345  MAC: DE:AD:BE:EF:00:00")
    lines.append("3. Status: Ready to provision. Unlocking device...")
    lines.append("4. Status: Device unlocked. Provisioning MAC...")
    lines.append("5. [OK] Provisioned")
    lines.append("   Serial: SP12345  MAC: 02:00:00:00:00:01")
    lines.append("   Status: [OK] Provisioned. Disconnect to provision next.")
    lines.append("6. (User disconnects device)")
    lines.append("7. [Searching...]  → Ready for next device")
    lines.append("```")
    lines.append("")
    lines.append("### Troubleshooting")
    lines.append("")
    lines.append("| Error | Cause | Solution |")
    lines.append("| --- | --- | --- |")
    lines.append("| [ERROR] Unknown device | MAC on device but SN not in DB | Manual investigation required |")
    lines.append("| [ERROR] MAC mismatch | DB MAC differs from device MAC | Check device and database |")
    lines.append("| [ERROR] duplicate_sn | SN already in DB with different MAC | Remove duplicate SN entry |")
    lines.append("| [ERROR] pool_exhausted | No MACs available in range | Expand MAC pool configuration |")
    lines.append("| [Searching...] (long time) | Device not reachable | Check network, firewall, IP |")
    lines.append("")
    lines.append("## Export to CSV")
    lines.append("")
    lines.append("### Workflow")
    lines.append("")
    lines.append("1. Click **Export CSV** button")
    lines.append("2. Choose save location and filename")
    lines.append("3. File is saved with all filtered units and their parts")
    lines.append("")
    lines.append("### CSV Structure")
    lines.append("")
    lines.append("```")
    lines.append("Serial,Test_Result,Timestamp,MAC_Address,Parts_Complete")
    lines.append("SP001,PASS,2026-06-29 14:30:00,02:00:00:00:00:01,YES")
    lines.append("SP002,FAIL,2026-06-28 10:15:00,-,NO")
    lines.append("```")
    lines.append("")
    lines.append("### Parts Consolidation")
    lines.append("")
    lines.append("All scanned parts for each unit are consolidated with:")
    lines.append("- Part name (e.g., 'Driver_Left')")
    lines.append("- Part serial number (e.g., 'DRV12345')")
    lines.append("")
    lines.append("## Settings Integration")
    lines.append("")
    lines.append("### Backplate Configuration")
    lines.append("")
    lines.append("Backplate provisioning defaults are configured via Settings:")
    lines.append("")
    lines.append("| Setting | Default | Purpose |")
    lines.append("| --- | --- | --- |")
    lines.append("| Backplate Default Serial | 123456 | Device serial before provisioning |")
    lines.append("| Backplate Default MAC | DE:AD:BE:EF:00:00 | Device MAC before provisioning |")
    lines.append("| Backplate Workstation ID | DataTools | Audit trail identifier |")
    lines.append("")
    lines.append("### How to Configure")
    lines.append("")
    lines.append("1. From Home, click **Settings**")
    lines.append("2. Enter password to unlock")
    lines.append("3. Scroll to 'Backplate Default Serial'")
    lines.append("4. Click **Edit** to change values")
    lines.append("5. Confirm changes (stored in DataTools database)")
    lines.append("")
    lines.append("## Support & Resources")
    lines.append("")
    lines.append("For issues, error messages, or feature requests, see:")
    lines.append("- DataTools README")
    lines.append("- Workstation SN/FW documentation")
    lines.append("- MAC Provisioning documentation")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point: parse arguments and generate documentation."""
    parser = argparse.ArgumentParser(
        description="Generate DataTools Tristar Viewer user manual",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Tristar Databases Viewer Manual",
        help="Document title (default: 'Tristar Databases Viewer Manual')",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Skip screenshot capture (use existing files)",
    )

    args = parser.parse_args()

    if not args.skip_screenshots:
        print("🎬 Capturing Tristar Viewer screenshots...")
        image_paths = capture_screenshots(clean=True)
    else:
        # Use existing screenshots in sorted order
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        files_by_name = {path.name: path for path in SCREENSHOT_DIR.glob("*.png")}
        image_paths = [files_by_name[name] for name in SCREEN_SEQUENCE if name in files_by_name]

    print(f"✏️ Generating Markdown: {OUTPUT_FILE}")
    markdown_content = _build_markdown(args.title, image_paths)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(markdown_content, encoding="utf-8")

    print(f"✅ Documentation complete: {OUTPUT_FILE}")
    print(f"   Screenshots: {len(image_paths)} images")


if __name__ == "__main__":
    main()
