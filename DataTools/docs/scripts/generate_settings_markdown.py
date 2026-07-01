"""
DataTools Documentation Generator
================================

This script generates a Markdown document for the DataTools Settings menu.
It is designed for repeatable documentation updates with auto screenshots.

Default behavior:
- Captures fresh screenshots from the Kivy UI flow
- Creates/overwrites docs/generated/settings-menu-manual.md
- Embeds each image directly in Markdown so it is rendered in preview

Usage examples:
- python DataTools/docs/scripts/generate_settings_markdown.py
- python DataTools/docs/scripts/generate_settings_markdown.py --title "Settings Menu (v0.2)"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window


# Relative root from this file:
# docs/scripts/generate_settings_markdown.py -> docs
DOCS_ROOT = Path(__file__).resolve().parent.parent
DATATOOLS_ROOT = DOCS_ROOT.parent
SCREENSHOT_DIR = DOCS_ROOT / "screenshots" / "settings-menu"
OUTPUT_FILE = DOCS_ROOT / "generated" / "settings-menu-manual.md"

# Keep names explicit for predictable markdown ordering.
SCREEN_SEQUENCE = [
    "01_home.png",
    "02_enter_password_dialog.png",
    "03_settings_popup.png",
    "04_value_edit_dialog.png",
    "05_change_password_dialog.png",
]


def _import_app_modules():
    """Import DataTools app modules after adding DataTools root to sys.path."""
    if str(DATATOOLS_ROOT) not in sys.path:
        sys.path.insert(0, str(DATATOOLS_ROOT))

    from app.main import HomeScreen, PasswordChangePopup, PasswordPopup, SettingsPopup, ValueEditPopup
    from app.settings_store import DataToolsSettingsStore

    return HomeScreen, PasswordChangePopup, PasswordPopup, SettingsPopup, ValueEditPopup, DataToolsSettingsStore


class SettingsDocCaptureApp(App):
    """
    Small capture app for deterministic Settings documentation screenshots.

    It opens the relevant dialogs in sequence and stores PNG snapshots.
    """

    title = "DataTools Settings Doc Capture"

    def __init__(self, screenshot_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = screenshot_dir
        self.store = None
        self.home_screen = None
        self.unlock_popup = None
        self.settings_popup = None
        self.edit_popup = None
        self.change_popup = None

        (
            self.HomeScreen,
            self.PasswordChangePopup,
            self.PasswordPopup,
            self.SettingsPopup,
            self.ValueEditPopup,
            self.DataToolsSettingsStore,
        ) = _import_app_modules()

    def build(self):
        """Build the DataTools home screen for screenshot capture."""
        self.store = self.DataToolsSettingsStore(DATATOOLS_ROOT)

        # Stable sample data for predictable screenshots.
        self.store.set(
            "default_export_folder",
            str(DATATOOLS_ROOT / "Exports"),
        )
        self.store.set(
            "matching_db_path",
            str(DATATOOLS_ROOT / "Matching_App" / "Data" / "db" / "matcher.db"),
        )
        self.store.set(
            "sn_fw_db_path",
            str(DATATOOLS_ROOT / "SubPro_SN_FW_Workstation" / "Data" / "subpro_workstation.db"),
        )
        self.store.set(
            "mac_db_path",
            str(DATATOOLS_ROOT / "SubProMACAddresses" / "db" / "mac_addresses.db"),
        )
        self.home_screen = self.HomeScreen(settings_store=self.store)
        return self.home_screen

    def on_start(self):
        """Start the timed screenshot sequence when UI is ready."""
        Window.size = (1920, 1080)
        Clock.schedule_once(self._prepare_home, 1.0)

    def _prepare_home(self, _dt):
        """Force full layout on the home screen before capturing."""
        self.home_screen.size = Window.size
        self.home_screen.pos = (0, 0)
        self.home_screen.do_layout()
        Clock.schedule_once(self._capture_home, 0.35)

    def _take(self, filename: str):
        """Take one screenshot of the current window state."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        target = self.screenshot_dir / filename
        saved = Path(Window.screenshot(name=str(target)))

        # Kivy may append a counter like 0001 before .png. Normalize to stable names.
        if saved.exists() and saved != target:
            target.unlink(missing_ok=True)
            saved.replace(target)

    def _capture_home(self, _dt):
        """Capture home screen and proceed to password unlock dialog."""
        self._take("01_home.png")

        self.unlock_popup = self.PasswordPopup(self.store, on_success=lambda: None)
        self.unlock_popup.open()
        Clock.schedule_once(self._capture_unlock, 0.5)

    def _capture_unlock(self, _dt):
        """Capture unlock dialog and proceed to settings popup."""
        self._take("02_enter_password_dialog.png")
        if self.unlock_popup:
            self.unlock_popup.dismiss()

        self.settings_popup = self.SettingsPopup(self.store)
        self.settings_popup.open()
        Clock.schedule_once(self._capture_settings, 0.6)

    def _capture_settings(self, _dt):
        """Capture settings popup and proceed to value edit dialog."""
        self._take("03_settings_popup.png")

        self.edit_popup = self.ValueEditPopup(
            title="Edit Backplate Default Serial",
            initial_value=self.store.get("backplate_default_serial", "123456"),
            on_confirm=lambda _value: None,
        )
        self.edit_popup.open()
        Clock.schedule_once(self._capture_edit_dialog, 0.5)

    def _capture_edit_dialog(self, _dt):
        """Capture value edit dialog and proceed to password change dialog."""
        self._take("04_value_edit_dialog.png")
        if self.edit_popup:
            self.edit_popup.dismiss()

        self.change_popup = self.PasswordChangePopup(self.store)
        self.change_popup.open()
        Clock.schedule_once(self._capture_password_change, 0.5)

    def _capture_password_change(self, _dt):
        """Capture password change dialog and finish the app run."""
        self._take("05_change_password_dialog.png")
        if self.change_popup:
            self.change_popup.dismiss()
        if self.settings_popup:
            self.settings_popup.dismiss()
        Clock.schedule_once(lambda _inner_dt: self.stop(), 0.2)


def capture_screenshots(clean: bool = True) -> list[Path]:
    """
    Capture deterministic Settings UI screenshots.

    Args:
        clean: Delete existing screenshot PNG files before capturing.

    Returns:
        Sorted list of screenshot paths after capture.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for path in SCREENSHOT_DIR.glob("*.png"):
            path.unlink(missing_ok=True)

    SettingsDocCaptureApp(screenshot_dir=SCREENSHOT_DIR).run()

    # Keep expected order and ignore unrelated images.
    files_by_name = {path.name: path for path in SCREENSHOT_DIR.glob("*.png")}
    ordered = [files_by_name[name] for name in SCREEN_SEQUENCE if name in files_by_name]
    return ordered


def _build_markdown(title: str, image_paths: list[Path]) -> str:
    """
    Create markdown content for the Settings menu documentation.
    Includes inline screenshots embedded in relevant sections.

    Args:
        title: Main document title.
        image_paths: Sorted list of screenshot file paths.

    Returns:
        Full Markdown text for the output file.
    """
    lines: list[str] = []

    # Build a lookup map for screenshots by stem
    screenshot_map = {path.stem: path.name for path in image_paths}

    lines.append(f"# {title}")
    lines.append("")
    lines.append("This guide provides comprehensive documentation for the DataTools Settings menu.")
    lines.append("It covers configuration tasks, user workflows, troubleshooting, and UI features.")
    lines.append("")
    lines.append("## Purpose and Scope")
    lines.append("")
    lines.append("This manual documents all configuration options accessible through the Settings menu:")
    lines.append("")
    lines.append("- Password-protected access control")
    lines.append("- CSV delimiter and decimal separator configuration")
    lines.append("- Export folder and database path management")
    lines.append("- Settings password change and security")
    lines.append("")
    lines.append("## Prerequisites")
    lines.append("")
    lines.append("Before using the Settings menu, ensure the following:")
    lines.append("")
    lines.append("- DataTools is running and the home screen is visible.")
    lines.append("- You know the current settings password.")
    lines.append("- All required target folders and database files exist on your system.")
    lines.append("")
    lines.append("## Quick Start")
    lines.append("")
    lines.append("1. Select the Settings tile on the home screen.")
    lines.append("2. Enter the correct password and click Unlock.")
    lines.append("3. Modify settings using the Edit or Browse buttons.")
    lines.append("4. Click Apply to save your changes.")
    lines.append("5. Click Close to exit the Settings menu.")
    lines.append("")
    lines.append("## Home Screen")
    lines.append("")
    if "01_home" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "settings-menu" / screenshot_map["01_home"]
        lines.append(f"![Home Screen]({rel_path.as_posix()})")
        lines.append("")
    lines.append("The home screen displays feature tiles for different DataTools functions.")
    lines.append("Click the Settings tile to access the configuration area.")
    lines.append("")
    lines.append("## Accessing the Settings Menu")
    lines.append("")
    if "02_enter_password_dialog" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "settings-menu" / screenshot_map["02_enter_password_dialog"]
        lines.append(f"![Enter Password Dialog]({rel_path.as_posix()})")
        lines.append("")
    lines.append("The Settings menu requires authentication for security.")
    lines.append("Enter your password and click Unlock to proceed.")
    lines.append("")
    lines.append("## Field Reference")
    lines.append("")
    lines.append("| Field | Purpose | Edit Method |")
    lines.append("| --- | --- | --- |")
    lines.append("| Measurements Root Folder | Root folder with Measurements/, References/ and DefaultReferences/ subfolders | Browse |")
    lines.append("| Matching DB path | Path to Matching database | Browse |")
    lines.append("| SN FW Workstation DB path | Path to SN/FW Workstation database | Browse |")
    lines.append("| MAC addresses DB path | Path to MAC addresses database | Browse |")
    lines.append("| Backplate Default Serial | Device serial number placeholder before MAC provisioning | Edit |")
    lines.append("| Backplate Default MAC | Device MAC address placeholder before provisioning | Edit |")
    lines.append("| Backplate Workstation ID | Identifier for audit trail in provisioning logs | View |")
    lines.append("| Settings password | Password for Settings menu access | Change |")
    lines.append("")
    lines.append("## The Settings Panel")
    lines.append("")
    if "03_settings_popup" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "settings-menu" / screenshot_map["03_settings_popup"]
        lines.append(f"![Settings Panel]({rel_path.as_posix()})")
        lines.append("")
    lines.append("The Settings panel displays all configuration parameters.")
    lines.append("Each field shows its current value and an action button:")
    lines.append("- **Browse**: Select file or folder paths using native file dialogs")
    lines.append("- **Change**: Modify the Settings password securely")
    lines.append("- **View**: Display read-only field values")
    lines.append("- **Edit**: Modify text values via a large-text input dialog")
    lines.append("")
    lines.append("## Detailed Workflows")
    lines.append("")
    lines.append("### Configuring Paths")
    lines.append("")
    lines.append("To set database or folder paths:")
    lines.append("")
    lines.append("1. Click Browse next to the path field.")
    lines.append("2. A native file or folder selection dialog opens.")
    lines.append("3. Navigate to and select the desired file or folder.")
    lines.append("4. The new path is immediately displayed and stored.")
    lines.append("")
    lines.append("### Editing Text Values")
    lines.append("")
    lines.append("Some fields (e.g. Backplate Default Serial, Backplate Default MAC) are edited via a text input dialog:")
    lines.append("")
    lines.append("1. Click **Edit** next to the field.")
    lines.append("2. Enter the new value in the text box.")
    lines.append("3. Click **Save** to apply or **Cancel** to discard.")
    lines.append("")
    if "04_value_edit_dialog" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "settings-menu" / screenshot_map["04_value_edit_dialog"]
        lines.append(f"![Text Edit Dialog]({rel_path.as_posix()})")
        lines.append("")
    lines.append("### Changing the Settings Password")
    lines.append("")
    if "05_change_password_dialog" in screenshot_map:
        rel_path = Path("..") / "screenshots" / "settings-menu" / screenshot_map["05_change_password_dialog"]
        lines.append(f"![Change Password Dialog]({rel_path.as_posix()})")
        lines.append("")
    lines.append("To update your Settings password:")
    lines.append("")
    lines.append("1. In the Settings password row, click Change.")
    lines.append("2. Enter your current password in the first field.")
    lines.append("3. Enter your new password in the second field.")
    lines.append("4. Re-enter the new password in the confirmation field.")
    lines.append("5. Click Update Password to save the change.")
    lines.append("")
    lines.append("## User Interface Features")
    lines.append("")
    lines.append("- **Path Truncation**: Long file paths are displayed on one line, truncated intelligently")
    lines.append("  to keep the filename and relevant directory components visible.")
    lines.append("- **Auto Focus**: When a dialog opens with multiple input fields, focus automatically")
    lines.append("  moves to the first field for faster data entry.")
    lines.append("- **Password Security**: Passwords are never displayed in clear text—always masked with asterisks.")
    lines.append("- **Error Highlighting**: Validation errors are shown in red to make failures immediately visible.")
    lines.append("- **Immediate Persistence**: All changes are immediately written to the database.")
    lines.append("")
    lines.append("## Troubleshooting")
    lines.append("")
    lines.append("### Password is rejected")
    lines.append("")
    lines.append("- The error text is highlighted in red for clear feedback.")
    lines.append("- Verify that CAPS LOCK is not enabled (passwords are case-sensitive).")
    lines.append("- Ensure you are entering the correct password.")
    lines.append("- Contact your system administrator if you cannot remember your password.")
    lines.append("")
    lines.append("### Cannot select a path")
    lines.append("")
    lines.append("- Verify that the drive or network location is accessible and connected.")
    lines.append("- Check that you have read permissions for the selected folder or file.")
    lines.append("- For network paths, ensure the resource is online and reachable.")
    lines.append("")
    lines.append("### Changes are not saved")
    lines.append("")
    lines.append("- Click Apply in the Settings panel to ensure changes are persisted.")
    lines.append("")
    lines.append("## Backplate Provisioning Settings")
    lines.append("")
    lines.append("The Backplate Provisioning feature allows automatic MAC address assignment to spare units.")
    lines.append("Three settings control this workflow:")
    lines.append("")
    lines.append("### Backplate Default Serial")
    lines.append("")
    lines.append("- **Purpose**: Reference serial number of a spare backplate unit before MAC provisioning")
    lines.append("- **Default**: `123456`")
    lines.append("- **Edit Method**: Click Edit to change the value")
    lines.append("- **Used By**: Backplate Provisioning popup for device state comparison")
    lines.append("")
    lines.append("### Backplate Default MAC")
    lines.append("")
    lines.append("- **Purpose**: Reference MAC address of a spare backplate unit before provisioning")
    lines.append("- **Default**: `DE:AD:BE:EF:00:00` (placeholder/reserved range)")
    lines.append("- **Edit Method**: Click Edit to change the value")
    lines.append("- **Format**: Standard MAC address notation: `XX:XX:XX:XX:XX:XX` (colon-separated hexadecimal)")
    lines.append("- **Used By**: Backplate Provisioning popup for device state validation")
    lines.append("")
    lines.append("### Backplate Workstation ID")
    lines.append("")
    lines.append("- **Purpose**: Identifier used in provisioning audit logs to track which workstation performed provisioning")
    lines.append("- **Default**: `DataTools`")
    lines.append("- **Edit Method**: View only (read-only field)")
    lines.append("- **Used By**: MAC provisioning database for audit trail")
    lines.append("")
    lines.append("### Configuration Workflow")
    lines.append("")
    lines.append("To adjust Backplate Provisioning defaults:")
    lines.append("")
    lines.append("1. In the Settings panel, scroll to find the three Backplate settings")
    lines.append("2. For **Backplate Default Serial**: Click Edit and enter the device serial number")
    lines.append("3. For **Backplate Default MAC**: Click Edit and enter the MAC address (format: `XX:XX:XX:XX:XX:XX`)")
    lines.append("4. **Backplate Workstation ID** cannot be edited (read-only)")
    lines.append("5. Click Apply in the Settings panel to save changes")
    lines.append("")

    return "\n".join(lines)


def generate(title: str, embed: bool = False, html: bool = False, docx: bool = False) -> Path:
    """
    Generate the settings markdown document.

    Args:
        title: Document title used in the generated markdown.
        embed: If True, embed screenshots as base64 data URIs.
        html:  If True, also write a self-contained HTML file.
        docx:  If True, also write a Word .docx file (for Confluence import).

    Returns:
        Path to the generated markdown file.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(SCREENSHOT_DIR.glob("*.png"))
    markdown = _build_markdown(title=title, image_paths=image_paths)
    if embed or html:
        from docs_utils import embed_images_in_markdown
        embedded = embed_images_in_markdown(markdown, DOCS_ROOT)
    else:
        embedded = markdown
    if embed:
        OUTPUT_FILE.write_text(embedded, encoding="utf-8")
    else:
        OUTPUT_FILE.write_text(markdown, encoding="utf-8")
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
    """Parse command-line arguments for the documentation generator."""
    parser = argparse.ArgumentParser(description="Generate DataTools Settings markdown documentation.")
    parser.add_argument(
        "--title",
        default="DataTools Settings Menu",
        help="Title used as the top-level markdown heading.",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Do not capture screenshots, only generate markdown from existing PNG files.",
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
    """Run the markdown generation workflow and print result path."""
    args = _parse_args()

    if not args.skip_screenshots:
        captured = capture_screenshots(clean=not args.keep_existing)
        print(f"Captured screenshots: {len(captured)}")

    output_path = generate(title=args.title, embed=args.embed_images, html=args.html, docx=args.docx)
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
