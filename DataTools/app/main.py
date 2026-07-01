"""
DataTools App - Main UI Entry Point
===================================

Purpose
-------
This module provides the primary UI composition for DataTools and wires together
the high-level navigation between the home screen, settings dialogs, and the
in-app read-only Matching viewer.

Architecture at a glance
------------------------
1. `DataToolsApp` initializes the window and creates the top-level root widget.
2. `DataToolsRoot` acts as a simple view switcher (home <-> matching).
3. `HomeScreen` contains feature tiles and forwards actions.
4. Settings are guarded by `PasswordPopup` and edited in dedicated dialogs.

Security and UX decisions
-------------------------
- Settings are protected by password verification.
- Password change is isolated in a dedicated popup.
- Settings values are edited through focused input masks instead of inline edits.
- Path values are selected using native OS dialogs (Tkinter) for operator safety.

Current scope
-------------
- Home screen with feature tiles
- Password-protected settings popup
- Edit-mask driven settings flow (no direct inline editing)
- Persistent SQLite settings foundation for future database workflows
- In-app read-only Matching viewer with back navigation
"""

from pathlib import Path
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from app.matching_viewer import MatchingViewerRoot, DelayedTooltipManager
from app.measurements_viewer import MeasurementsViewerRoot
from app.tristar_databases_viewer import TristarDatabasesViewerRoot
from app.settings_store import DataToolsSettingsStore


# ---------------------------------------------------------------------------
# Settings Access and Edit Popups
# ---------------------------------------------------------------------------
# The following popup classes define the complete settings access flow:
# 1) unlock (password), 2) value editing, 3) password rotation.
# Keeping this flow in one file makes UI behavior easier to trace.


class PasswordPopup(Popup):
    """
    PasswordPopup
    =============

    Small modal dialog used to gate access to sensitive actions.
    In this stage it protects the settings area.
    """

    def __init__(self, settings_store: DataToolsSettingsStore, on_success, **kwargs):
        """
        Create the password popup.

        Args:
            settings_store: Persistent settings backend.
            on_success: Callback executed when password validation succeeds.
        """
        super().__init__(**kwargs)
        self.settings_store = settings_store
        self.on_success = on_success
        self.title = "Enter Password"
        self.size_hint = (0.45, 0.3)
        self.auto_dismiss = True

        root = BoxLayout(orientation="vertical", spacing=10, padding=12)

        self.password_input = TextInput(
            hint_text="Password",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=42,
        )
        self.password_input.bind(on_text_validate=self._validate)
        root.add_widget(self.password_input)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            color=(1, 0.5, 0.5, 1),
        )
        root.add_widget(self.info_label)

        validate_button = Button(text="Unlock", size_hint_y=None, height=42)
        validate_button.bind(on_release=self._validate)
        root.add_widget(validate_button)

        self.content = root
        Clock.schedule_once(lambda _dt: setattr(self.password_input, "focus", True), 0.05)

    def _validate(self, *_args):
        """Validate password and call success callback when accepted."""
        candidate = self.password_input.text.strip()
        if self.settings_store.verify_password(candidate):
            self.dismiss()
            self.on_success()
            return

        self.info_label.text = "Invalid password"
        self.password_input.text = ""


class ValueEditPopup(Popup):
    """
    ValueEditPopup
    ==============

    Generic edit popup for textual settings values.
    It uses larger text input to improve readability during editing.
    """

    def __init__(self, title: str, initial_value: str, on_confirm, **kwargs):
        """
        Create a generic value edit popup.

        Args:
            title: Popup title text.
            initial_value: Current value prefilled in the input field.
            on_confirm: Callback receiving the confirmed string.
        """
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.65, 0.38)
        self.auto_dismiss = True
        self.on_confirm = on_confirm

        root = BoxLayout(orientation="vertical", spacing=12, padding=14)

        self.value_input = TextInput(
            text=initial_value,
            multiline=False,
            font_size="24sp",
            size_hint_y=None,
            height=58,
        )
        self.value_input.bind(on_text_validate=self._save)
        root.add_widget(self.value_input)

        controls = BoxLayout(size_hint_y=None, height=42, spacing=10)
        save_button = Button(text="Save")
        save_button.bind(on_release=self._save)
        cancel_button = Button(text="Cancel")
        cancel_button.bind(on_release=lambda *_: self.dismiss())
        controls.add_widget(save_button)
        controls.add_widget(cancel_button)

        root.add_widget(controls)
        self.content = root
        Clock.schedule_once(lambda _dt: setattr(self.value_input, "focus", True), 0.05)

    def _save(self, *_args):
        """Commit the edited value and close the popup."""
        self.on_confirm(self.value_input.text.strip())
        self.dismiss()


class PasswordChangePopup(Popup):
    """
    PasswordChangePopup
    ===================

    Dedicated password change screen for settings protection.
    This popup is opened from the Settings screen when the user selects
    the "Settings password" entry.
    """

    def __init__(self, settings_store: DataToolsSettingsStore, **kwargs):
        """
        Create and configure the password change popup.

        Args:
            settings_store: Persistent settings backend.
        """
        super().__init__(**kwargs)
        self.settings_store = settings_store
        self.title = "Change Settings Password"
        self.size_hint = (0.6, 0.52)
        self.auto_dismiss = True

        root = BoxLayout(orientation="vertical", spacing=10, padding=14)

        self.current_password = TextInput(
            hint_text="Current password",
            password=True,
            multiline=False,
            font_size="20sp",
            size_hint_y=None,
            height=52,
        )
        root.add_widget(self.current_password)

        self.new_password = TextInput(
            hint_text="New password",
            password=True,
            multiline=False,
            font_size="20sp",
            size_hint_y=None,
            height=52,
        )
        root.add_widget(self.new_password)

        self.confirm_password = TextInput(
            hint_text="Confirm new password",
            password=True,
            multiline=False,
            font_size="20sp",
            size_hint_y=None,
            height=52,
        )
        root.add_widget(self.confirm_password)

        self.result_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            color=(1, 0.6, 0.6, 1),
        )
        root.add_widget(self.result_label)

        controls = BoxLayout(size_hint_y=None, height=42, spacing=10)
        save_button = Button(text="Update Password")
        save_button.bind(on_release=self._update_password)
        cancel_button = Button(text="Cancel")
        cancel_button.bind(on_release=lambda *_: self.dismiss())
        controls.add_widget(save_button)
        controls.add_widget(cancel_button)
        root.add_widget(controls)

        self.content = root
        Clock.schedule_once(lambda _dt: setattr(self.current_password, "focus", True), 0.05)

    def _update_password(self, *_args):
        """Validate password change form and persist the new password."""
        current_value = self.current_password.text.strip()
        new_value = self.new_password.text.strip()
        confirm_value = self.confirm_password.text.strip()

        if not self.settings_store.verify_password(current_value):
            self.result_label.text = "Current password is invalid"
            return

        if not new_value:
            self.result_label.text = "New password must not be empty"
            return

        if new_value != confirm_value:
            self.result_label.text = "New password confirmation does not match"
            return

        self.settings_store.update_password(new_value)
        self.dismiss()


class SettingsPopup(Popup):
    """
    SettingsPopup
    =============

    Minimal required settings view for DataTools.
    This popup edits only the currently required settings set.
    """

    def __init__(self, settings_store: DataToolsSettingsStore, **kwargs):
        """
        Create the settings popup and bind form fields.

        Args:
            settings_store: Persistent settings backend.
        """
        super().__init__(**kwargs)
        self.settings_store = settings_store
        self.title = "Settings"
        self.size_hint = (0.75, 0.85)
        self.auto_dismiss = True

        # Snapshot current values once for initial row construction.
        # Dynamic updates later use _refresh_values() and _update_value_label().
        values = self.settings_store.get_all()

        outer = BoxLayout(orientation="vertical", spacing=10, padding=10)
        scroll = ScrollView(size_hint=(1, 1))
        form = GridLayout(cols=1, spacing=8, size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        self.value_labels = {}
        self.path_keys = {
            "measurements_root_path",
            "default_export_folder",
            "matching_db_path",
            "sn_fw_db_path",
            "mac_db_path",
        }

        _settings_tips = {
            "measurements_root_path": "Root folder containing the Measurements/, References/ and DefaultReferences/ subfolders.",
            "matching_db_path":       "SQLite database file used by the matching viewer.",
            "sn_fw_db_path":          "SQLite database file for serial number and firmware workstation data.",
            "mac_db_path":            "SQLite database file for MAC address pool management.",
            "backplate_default_serial": "Default serial number pre-filled when provisioning a backplate.",
            "backplate_default_mac":    "Default MAC address pre-filled when provisioning a backplate.",
            "backplate_workstation_id": "Workstation identifier written to provisioning records (read-only).",
            "app_password":             "Password required to open the Settings screen.",
        }
        _tips = DelayedTooltipManager(delay_seconds=0.6)

        def create_row(label_text: str, key: str, value: str, button_text: str, on_click):
            """Create one settings row with label, value preview, and action button."""
            row = BoxLayout(size_hint_y=None, height=44, spacing=8)

            name_label = Label(text=label_text, size_hint_x=0.35, halign="left", valign="middle")
            name_label.bind(size=lambda instance, value_size: setattr(instance, "text_size", value_size))
            row.add_widget(name_label)

            value_label = Label(
                text=self._format_value_preview(key, value),
                size_hint_x=0.45,
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="left",
                max_lines=1,
            )
            value_label.bind(
                size=lambda instance, _value_size: setattr(instance, "text_size", (instance.width, None))
            )
            value_label.bind(size=lambda *_: self._update_value_label(key))
            row.add_widget(value_label)
            self.value_labels[key] = value_label

            # Action button is intentionally compact and contextual:
            # Edit / Browse / Change / View depending on the setting type.
            action_button = Button(text=button_text, size_hint_x=0.2)
            action_button.bind(on_release=on_click)
            if key in _settings_tips:
                _tips.register(action_button, _settings_tips[key])
            row.add_widget(action_button)

            form.add_widget(row)

            # Refresh after first layout pass so dynamic truncation uses real widget width.
            Clock.schedule_once(lambda _dt: self._update_value_label(key), 0.05)

        # Measurements root folder is browsable and persists across restarts.
        create_row(
            "Measurements Root Folder",
            "measurements_root_path",
            values.get("measurements_root_path", ""),
            "Browse",
            lambda *_: self._browse_folder("measurements_root_path"),
        )

        # Path values are selected via Tkinter file/folder dialogs.
        create_row(
            "Matching DB path",
            "matching_db_path",
            values.get("matching_db_path", ""),
            "Browse",
            lambda *_: self._browse_db_file("matching_db_path"),
        )
        create_row(
            "SN FW Workstation DB path",
            "sn_fw_db_path",
            values.get("sn_fw_db_path", ""),
            "Browse",
            lambda *_: self._browse_db_file("sn_fw_db_path"),
        )
        create_row(
            "MAC addresses DB path",
            "mac_db_path",
            values.get("mac_db_path", ""),
            "Browse",
            lambda *_: self._browse_db_file("mac_db_path"),
        )

        # Backplate Provisioning Settings
        create_row(
            "Backplate Default Serial",
            "backplate_default_serial",
            values.get("backplate_default_serial", "123456"),
            "Edit",
            lambda *_: self._open_text_edit("Backplate Default Serial", "backplate_default_serial"),
        )
        create_row(
            "Backplate Default MAC",
            "backplate_default_mac",
            values.get("backplate_default_mac", "DE:AD:BE:EF:00:00"),
            "Edit",
            lambda *_: self._open_text_edit("Backplate Default MAC", "backplate_default_mac"),
        )
        create_row(
            "Backplate Workstation ID",
            "backplate_workstation_id",
            values.get("backplate_workstation_id", "DataTools"),
            "View",
            lambda *_: None,
        )

        # Password gets a dedicated change screen.
        create_row(
            "Settings password",
            "app_password",
            "********",
            "Change",
            lambda *_: PasswordChangePopup(self.settings_store).open(),
        )

        scroll.add_widget(form)
        outer.add_widget(scroll)

        controls = BoxLayout(size_hint_y=None, height=42, spacing=10)
        save_button = Button(text="Apply")
        save_button.bind(on_release=self._apply)
        close_button = Button(text="Close")
        close_button.bind(on_release=lambda *_: self.dismiss())
        _tips.register(save_button, "Apply and persist the current settings values.")
        _tips.register(close_button, "Close the settings dialog.")

        self.result_label = Label(text="", size_hint_x=1.5, color=(0.6, 0.9, 0.6, 1))

        controls.add_widget(save_button)
        controls.add_widget(close_button)
        controls.add_widget(self.result_label)
        outer.add_widget(controls)

        self.content = outer

    def _open_text_edit(self, display_title: str, key: str):
        """
        Open the large-input edit mask for one textual setting.

        Args:
            display_title: Human-readable field title shown in popup.
            key: Settings key to update.
        """
        current_value = self.settings_store.get(key, "")

        def on_confirm(value: str):
            normalized_value = value
            if key == "csv_delimiter" and not normalized_value:
                normalized_value = ","
            if key == "decimal_separator":
                # Current product requirement: decimal separator is always dot.
                normalized_value = "."
            self.settings_store.set(key, normalized_value)
            self._refresh_values()

        ValueEditPopup(
            title=f"Edit {display_title}",
            initial_value=current_value,
            on_confirm=on_confirm,
        ).open()

    def _browse_folder(self, key: str):
        """Open a Tkinter folder selection dialog for a folder path setting."""
        selected = self._select_folder_path(self.settings_store.get(key, ""))
        if selected:
            self.settings_store.set(key, selected)
            self._refresh_values()

    def _browse_db_file(self, key: str):
        """Open a Tkinter file dialog for selecting a SQLite database path."""
        selected = self._select_db_file_path(self.settings_store.get(key, ""))
        if selected:
            self.settings_store.set(key, selected)
            self._refresh_values()

    @staticmethod
    def _select_folder_path(initial_path: str) -> str:
        """
        Show a native Tkinter folder chooser.

        Args:
            initial_path: Preselected starting path if available.

        Returns:
            Selected folder path or an empty string.
        """
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(initialdir=initial_path or None)
        root.destroy()
        return chosen or ""

    @staticmethod
    def _select_db_file_path(initial_path: str) -> str:
        """
        Show a native Tkinter DB file chooser.

        Args:
            initial_path: Preselected starting file path if available.

        Returns:
            Selected file path or an empty string.
        """
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askopenfilename(
            initialdir=str(Path(initial_path).parent) if initial_path else None,
            filetypes=[("SQLite database", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")],
        )
        root.destroy()
        return chosen or ""

    def _refresh_values(self):
        """Refresh value previews in the settings grid after updates."""
        keys = [
            "measurements_root_path",
            "matching_db_path",
            "sn_fw_db_path",
            "mac_db_path",
        ]
        for key in keys:
            self._update_value_label(key)
        if "app_password" in self.value_labels:
            # Never expose password material in the preview column.
            self.value_labels["app_password"].text = "********"

    def _update_value_label(self, key: str):
        """Update one value label with current data and width-aware truncation."""
        if key not in self.value_labels:
            return

        if key == "app_password":
            self.value_labels[key].text = "********"
            return

        raw_value = self.settings_store.get(key, "")
        label = self.value_labels[key]
        label.text = self._format_value_preview(key, raw_value, label.width)

    def _format_value_preview(self, key: str, value: str, width_px: float = 0) -> str:
        """
        Return a cleaner one-line preview for settings values.

        Long paths are shortened from the left so filenames and trailing
        path parts remain visible, which is usually the most useful part.
        """
        if not value:
            return ""

        if key in self.path_keys:
            # Approximate number of visible monospace-like characters for current label width.
            # This keeps previews adaptive when the window or popup size changes.
            estimated_chars = int(width_px / 8.5) if width_px else 0
            max_chars = max(20, estimated_chars) if estimated_chars else 52
            if len(value) > max_chars:
                return f"...{value[-(max_chars - 3):]}"

        return value

    def _apply(self, *_args):
        """Apply button handler for explicit user feedback."""
        # Enforce product rule once more when user presses Apply.
        self.settings_store.set("decimal_separator", ".")
        self._refresh_values()
        self.result_label.text = "Applied"


# ---------------------------------------------------------------------------
# Home and View Routing
# ---------------------------------------------------------------------------
# HomeScreen represents operator entry navigation.
# DataToolsRoot provides deterministic switching between app masks.


class HomeScreen(BoxLayout):
    """
    HomeScreen
    ==========

    Main start page for DataTools.
    Displays a short header and a grid of feature tiles.
    """

    def __init__(self, settings_store: DataToolsSettingsStore, on_open_matching=None, on_open_tristar_databases=None, on_open_measurements=None, **kwargs):
        super().__init__(orientation="vertical", spacing=12, padding=16, **kwargs)
        self.settings_store = settings_store
        self.on_open_matching = on_open_matching
        self.on_open_tristar_databases = on_open_tristar_databases
        self.on_open_measurements = on_open_measurements

        # Header: app name and short purpose statement.
        title = Label(
            text="DataTools",
            font_size="28sp",
            bold=True,
            size_hint_y=None,
            height=44,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda instance, value: setattr(instance, "text_size", value))

        self.add_widget(title)

        # Grid with four feature tiles.
        # Settings opens a password-protected popup, other tiles open full viewers.
        tiles = GridLayout(cols=2, spacing=12, size_hint_y=1)

        feature_names = [
            "Matching",
            "Tristar Databases",
            "Measurements",
            "Settings",
        ]

        _tile_tips = {
            "Matching":           "View and explore module matching data from the production database.",
            "Tristar Databases":  "Browse Tristar test records and provision backplates.",
            "Measurements":       "Load APx CSV measurements, view frequency-response charts and generate reference/limit files.",
            "Settings":           "Configure database paths, CSV format and app password (password protected).",
        }
        _tips = DelayedTooltipManager(delay_seconds=0.6)

        for feature_name in feature_names:
            tile = Button(
                text=feature_name,
                font_size="18sp",
                bold=True,
                background_normal="",
                background_color=(0.18, 0.32, 0.54, 1),
            )
            tile.bind(on_release=self._on_tile_pressed)
            _tips.register(tile, _tile_tips.get(feature_name, feature_name))
            tiles.add_widget(tile)

        self.add_widget(tiles)

        self.status_line = Label(
            text="Select a feature.",
            font_size="14sp",
            size_hint_y=None,
            height=28,
            color=(0.85, 0.85, 0.85, 1),
            halign="left",
            valign="middle",
        )
        self.status_line.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.add_widget(self.status_line)

        # Footer hint for the current app phase.
        footer = Label(
            text="",
            font_size="14sp",
            size_hint_y=None,
            height=28,
            color=(0.75, 0.75, 0.75, 1),
            halign="left",
            valign="middle",
        )
        footer.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.add_widget(footer)

    def _on_tile_pressed(self, button_instance):
        """
        Tile click handler.

        Settings are password-protected and open a dedicated popup.
        Matching and Tristar Databases open full-screen viewers.
        Other tiles remain placeholders for upcoming modules.
        """
        if button_instance.text == "Settings":
            PasswordPopup(
                settings_store=self.settings_store,
                on_success=lambda: SettingsPopup(self.settings_store).open(),
            ).open()
            return

        if button_instance.text == "Matching":
            if self.on_open_matching is not None:
                self.on_open_matching()
            else:
                self.status_line.text = "Matching: view is unavailable"
            return

        if button_instance.text == "Tristar Databases":
            if self.on_open_tristar_databases is not None:
                self.on_open_tristar_databases()
            else:
                self.status_line.text = "Tristar Databases: view is unavailable"
            return

        if button_instance.text == "Measurements":
            if self.on_open_measurements is not None:
                self.on_open_measurements()
            else:
                self.status_line.text = "Measurements: view is unavailable"
            return

        self.status_line.text = f"{button_instance.text}: coming soon"


class DataToolsRoot(BoxLayout):
    """Top-level container that switches between Home and Matching views."""

    def __init__(self, settings_store: DataToolsSettingsStore, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.settings_store = settings_store
        self.current_view = None
        self._measurements_view: Optional[MeasurementsViewerRoot] = None
        self.show_home()

    def _set_view(self, widget: BoxLayout) -> None:
        """Replace the current content view with the requested widget."""
        self.clear_widgets()
        self.current_view = widget
        self.add_widget(widget)

    def show_home(self) -> None:
        """Show the DataTools home mask."""
        self._set_view(
            HomeScreen(
                settings_store=self.settings_store,
                on_open_matching=self.show_matching,
                on_open_tristar_databases=self.show_tristar_databases,
                on_open_measurements=self.show_measurements,
            )
        )

    def show_matching(self) -> None:
        """Show the read-only Matching viewer mask."""
        self._set_view(
            MatchingViewerRoot(
                settings_store=self.settings_store,
                on_back=self.show_home,
            )
        )

    def show_tristar_databases(self) -> None:
        """Show the Tristar Databases unified viewer mask."""
        self._set_view(
            TristarDatabasesViewerRoot(
                settings_store=self.settings_store,
                on_back=self.show_home,
            )
        )

    def show_measurements(self) -> None:
        """Show the Measurements viewer mask, reusing the existing instance if available."""
        if self._measurements_view is None:
            self._measurements_view = MeasurementsViewerRoot(
                settings_store=self.settings_store,
                on_back=self.show_home,
            )
        else:
            self._measurements_view.on_enter()
        self._set_view(self._measurements_view)


class DataToolsApp(App):
    """Kivy application entry class for DataTools."""

    title = "DataTools"

    def build(self):
        """
        Build and return the start page widget tree.

        Window setup is intentionally minimal for now:
        - dark neutral background
        - practical default desktop size
        """
        datatools_root = Path(__file__).resolve().parent.parent
        settings_store = DataToolsSettingsStore(datatools_root)

        Window.clearcolor = (0.1, 0.1, 0.12, 1)
        Window.size = (1400, 860)
        return DataToolsRoot(settings_store=settings_store)
