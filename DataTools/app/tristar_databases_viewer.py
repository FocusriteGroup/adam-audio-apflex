"""
DataTools Tristar Databases Viewer
===================================

This module implements the unified read-only viewer for Tristar system data
spanning two databases: SubPro Workstation (units + parts) and MAC Addresses.

Design goals
------------
1. Inspect unified Tristar data safely: no write operations to either DB.
2. Cross-database joins: match units with MAC addresses by serial number.
3. Keep operations fast: short-lived SQLite connections per query.
4. Provide operator-friendly feedback: explicit status/error messages.

What the viewer does
--------------------
- Reads subpro_workstation.db (units, parts_scanned, parts_config)
- Reads mac_addresses.db (mac_range, provisioning_log)
- Shows units with parts status and assigned MAC addresses
- Renders detailed views per unit with all scanned parts
- Displays MAC address pool status and allocation summary
- Exports unified CSV snapshot with timeframe filtering
- Provisions spare backplate units with serial number and MAC address
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from app.settings_store import DataToolsSettingsStore


# ---------------------------------------------------------------------------
# Tooltip Support
# ---------------------------------------------------------------------------


class TooltipWidget(BoxLayout):
    """
    Lightweight tooltip widget added directly to the Window (no Popup overhead).
    This avoids Kivy Popup title/separator padding that clips short tooltips.
    """

    def __init__(self, text: str, pos, **kwargs):
        super().__init__(padding=(10, 5, 10, 5), **kwargs)
        self.size_hint = (None, None)

        # Dark semi-transparent background drawn via canvas.
        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.14, 0.14, 0.16, 0.93)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])

        self.bind(
            pos=lambda *_: setattr(self._bg_rect, "pos", self.pos),
            size=lambda *_: setattr(self._bg_rect, "size", self.size),
        )

        label = Label(
            text=text,
            font_size="12sp",
            halign="left",
            valign="middle",
            color=(0.95, 0.95, 0.95, 1),
            size_hint=(1, 1),
        )
        label.bind(size=lambda instance, _v: setattr(instance, "text_size", (instance.width, None)))
        self.add_widget(label)

        # Size the widget after label is added.
        width = max(200, min(560, int(len(text) * 7.2) + 24))
        self.size = (width, 32)
        self.pos = pos


class DelayedTooltipManager:
    """Show tooltips when the mouse stays over a widget for a short time."""

    def __init__(self, delay_seconds: float = 1.2):
        self.delay_seconds = delay_seconds
        self._entries: List[Tuple[Widget, str]] = []
        self._hover_widget: Optional[Widget] = None
        self._scheduled_event = None
        self._tooltip_widget = None
        self._mouse_pos = (0, 0)

        Window.bind(mouse_pos=self._on_mouse_pos)

    def register(self, widget: Widget, text: str) -> None:
        """Register one widget tooltip entry."""
        if not widget or not text:
            return
        self._entries.append((widget, text))

    def _find_hover_widget(self, x: float, y: float) -> Optional[Tuple[Widget, str]]:
        """Return the top-most registered widget currently under mouse."""
        for widget, text in reversed(self._entries):
            if widget.get_root_window() is None:
                continue
            local_x, local_y = widget.to_widget(x, y, relative=False)
            if widget.collide_point(local_x, local_y):
                return widget, text
        return None

    def _on_mouse_pos(self, _window, pos) -> None:
        """Track hover state and schedule or hide tooltip popups."""
        x, y = pos
        self._mouse_pos = pos
        hit = self._find_hover_widget(x, y)

        if not hit:
            self._cancel_schedule()
            self._hover_widget = None
            self._hide_popup()
            return

        widget, text = hit
        if widget is self._hover_widget:
            return

        self._cancel_schedule()
        self._hide_popup()
        self._hover_widget = widget
        self._scheduled_event = Clock.schedule_once(lambda _dt: self._show_popup(text), self.delay_seconds)

    def _show_popup(self, text: str) -> None:
        """Create and attach tooltip widget near mouse cursor."""
        self._scheduled_event = None
        if not self._hover_widget:
            return

        mouse_x, mouse_y = self._mouse_pos
        tip = TooltipWidget(text=text, pos=(0, 0))
        x = min(mouse_x + 12, Window.width - tip.width - 8)
        y = min(mouse_y + 16, Window.height - tip.height - 8)
        tip.pos = (max(8, x), max(8, y))

        Window.add_widget(tip)
        self._tooltip_widget = tip

    def _cancel_schedule(self) -> None:
        """Cancel pending tooltip show event if any."""
        if self._scheduled_event is not None:
            self._scheduled_event.cancel()
            self._scheduled_event = None

    def _hide_popup(self) -> None:
        """Remove active tooltip widget from window if visible."""
        if self._tooltip_widget is not None:
            Window.remove_widget(self._tooltip_widget)
            self._tooltip_widget = None


class TristarRepository:
    """
    Read-only data access for unified Tristar system views.
    
    Queries both subpro_workstation.db and mac_addresses.db and
    provides cross-database results (units with MAC and parts info).
    """

    def __init__(self, sn_fw_db_path: str, mac_db_path: str):
        """
        Initialize the repository with paths to both databases.
        
        Args:
            sn_fw_db_path: Path to subpro_workstation.db (SN/FW database)
            mac_db_path: Path to mac_addresses.db (MAC provisioning database)
        """
        self.sn_fw_db_path = sn_fw_db_path
        self.mac_db_path = mac_db_path

    def _connect_sn_fw(self) -> sqlite3.Connection:
        """Create and return connection to SN/FW database."""
        conn = sqlite3.connect(self.sn_fw_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_mac(self) -> sqlite3.Connection:
        """Create and return connection to MAC database."""
        conn = sqlite3.connect(self.mac_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def sn_fw_exists(self) -> bool:
        """Check if SN/FW database file exists and is readable."""
        try:
            path = Path(self.sn_fw_db_path)
            return path.exists() and path.is_file()
        except (OSError, ValueError):
            return False

    def mac_exists(self) -> bool:
        """Check if MAC database file exists and is readable."""
        try:
            path = Path(self.mac_db_path)
            return path.exists() and path.is_file()
        except (OSError, ValueError):
            return False

    def get_all_units(self) -> List[Dict[str, str]]:
        """
        Get latest version of each unit (deduplicated by product_sn).
        
        Returns:
            List of dicts with keys: id, product_sn, mac, parts_complete, 
            fw_version_final, result, timestamp
        """
        try:
            # Query latest unit per product_sn
            with self._connect_sn_fw() as sn_conn:
                sn_cursor = sn_conn.cursor()
                sn_cursor.execute(
                    """
                    SELECT id, product_sn, fw_version_final, result, timestamp
                    FROM units
                    WHERE id IN (
                        SELECT id FROM units u1
                        WHERE timestamp = (
                            SELECT MAX(timestamp) FROM units u2 
                            WHERE u2.product_sn = u1.product_sn
                        )
                    )
                    ORDER BY timestamp DESC
                    """
                )
                units = [dict(row) for row in sn_cursor.fetchall()]

            # For each unit, check if all configured parts were scanned
            for unit in units:
                unit["parts_complete"] = self._check_parts_complete(unit["id"])

            # Enrich with MAC addresses from mac_addresses.db
            mac_by_serial = self._get_mac_by_serial()
            for unit in units:
                unit["mac"] = mac_by_serial.get(unit["product_sn"], "")

            return units
        except Exception as e:
            print(f"Error fetching units: {e}")
            return []

    def _check_parts_complete(self, unit_id: int) -> bool:
        """
        Check if all configured parts were scanned for a unit.
        
        Returns:
            True if scanned parts match configured parts, False otherwise.
        """
        try:
            with self._connect_sn_fw() as conn:
                cursor = conn.cursor()
                # Get configured part count
                cursor.execute("SELECT COUNT(*) FROM parts_config WHERE required = 1")
                required_count = cursor.fetchone()[0]

                # Get scanned part count for this unit
                cursor.execute(
                    "SELECT COUNT(*) FROM parts_scanned WHERE unit_id = ?",
                    (unit_id,)
                )
                scanned_count = cursor.fetchone()[0]

            return scanned_count >= required_count
        except Exception:
            return False

    def _get_mac_by_serial(self) -> Dict[str, str]:
        """
        Get mapping of serial number to MAC address from provisioning_log.
        
        Returns:
            Dict: {serial -> mac} for all provisioned units
        """
        try:
            with self._connect_mac() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT serial, mac FROM provisioning_log WHERE status = 'verified' OR status = 'written'"
                )
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception:
            return {}

    def get_unit_by_serial(self, serial: str) -> Optional[Dict[str, str]]:
        """
        Get detailed unit information by serial number.
        
        Returns:
            Dict with keys: id, product_sn, variant, fw_version_found, 
            fw_flashed, fw_version_final, result, timestamp, mac
        """
        try:
            with self._connect_sn_fw() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM units WHERE product_sn = ?",
                    (serial,)
                )
                row = cursor.fetchone()
                if not row:
                    return None

                unit = dict(row)
                unit["parts_complete"] = self._check_parts_complete(unit["id"])

            # Get MAC address
            mac_by_serial = self._get_mac_by_serial()
            unit["mac"] = mac_by_serial.get(serial, "")

            return unit
        except Exception as e:
            print(f"Error fetching unit {serial}: {e}")
            return None

    def get_unit_parts(self, unit_id: int) -> List[Dict[str, str]]:
        """
        Get all parts scanned for a specific unit.
        
        Returns:
            List of dicts with keys: id, part_name, part_sn, previous_unit_id, timestamp
        """
        try:
            with self._connect_sn_fw() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, part_name, part_sn, previous_unit_id, timestamp FROM parts_scanned WHERE unit_id = ? ORDER BY timestamp",
                    (unit_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_mac_status(self) -> Optional[Dict[str, str]]:
        """
        Get MAC address pool status from mac_range table.
        
        Returns:
            Dict with keys: start_mac, end_mac, next_mac, warn_threshold, 
            remaining_count, total_count, provisioned_count
        """
        try:
            with self._connect_mac() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT start_mac, end_mac, next_mac, warn_threshold FROM mac_range WHERE id = 1"
                )
                range_row = cursor.fetchone()
                if not range_row:
                    return None

                status = dict(range_row)

                # Calculate remaining and total
                def mac_to_int(mac_str: str) -> int:
                    """Convert MAC address string to integer."""
                    parts = mac_str.split(':')
                    return int(''.join(parts), 16)

                start_int = mac_to_int(status["start_mac"])
                end_int = mac_to_int(status["end_mac"])
                next_int = mac_to_int(status["next_mac"])

                status["total_count"] = end_int - start_int + 1
                status["remaining_count"] = max(0, end_int - next_int + 1)

                # Count provisioned entries
                cursor.execute(
                    "SELECT COUNT(*) FROM provisioning_log WHERE status IN ('verified', 'written')"
                )
                status["provisioned_count"] = cursor.fetchone()[0]

                return status
        except Exception as e:
            print(f"Error fetching MAC status: {e}")
            return None

    def get_summary(self) -> Dict[str, int]:
        """
        Get summary counts for the dashboard.
        
        Returns:
            Dict with keys: total_units, units_with_mac, units_with_complete_parts
        """
        try:
            with self._connect_sn_fw() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM units")
                total_units = cursor.fetchone()[0]

            mac_by_serial = self._get_mac_by_serial()
            units_with_mac = len(mac_by_serial)

            # Count units with complete parts
            all_units = self.get_all_units()
            units_with_complete_parts = sum(1 for u in all_units if u["parts_complete"])

            return {
                "total_units": total_units,
                "units_with_mac": units_with_mac,
                "units_with_complete_parts": units_with_complete_parts,
            }
        except Exception:
            return {"total_units": 0, "units_with_mac": 0, "units_with_complete_parts": 0}

    def get_units_in_period(self, start_dt: str, end_dt: str) -> List[Dict[str, str]]:
        """
        Get latest units within a timestamp range (deduplicated by product_sn).
        
        Args:
            start_dt: ISO format start datetime (inclusive)
            end_dt: ISO format end datetime (exclusive)
        
        Returns:
            List of latest units per product_sn with MAC and parts status
        """
        try:
            with self._connect_sn_fw() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, product_sn, fw_version_final, result, timestamp
                    FROM units
                    WHERE timestamp >= ? AND timestamp < ?
                    AND id IN (
                        SELECT id FROM units u1
                        WHERE timestamp = (
                            SELECT MAX(timestamp) FROM units u2 
                            WHERE u2.product_sn = u1.product_sn
                            AND u2.timestamp >= ?
                            AND u2.timestamp < ?
                        )
                    )
                    ORDER BY timestamp DESC
                    """,
                    (start_dt, end_dt, start_dt, end_dt)
                )
                units = [dict(row) for row in cursor.fetchall()]

            # For each unit, check if all configured parts were scanned
            for unit in units:
                unit["parts_complete"] = self._check_parts_complete(unit["id"])

            mac_by_serial = self._get_mac_by_serial()
            for unit in units:
                unit["mac"] = mac_by_serial.get(unit["product_sn"], "")

            return units
        except Exception:
            return []
        except Exception:
            return []


class ListTimeframeFilterPopup(Popup):
    """Generic timeframe filter popup for Tristar units list."""

    SETTINGS_KEY_START = "tristar_filter_start"
    SETTINGS_KEY_END = "tristar_filter_end"

    def __init__(self, items: List[Dict[str, str]], settings_store: DataToolsSettingsStore, on_apply=None, **kwargs):
        super().__init__(**kwargs)
        self.title = "Filter Units by Date Range"
        self.size_hint = (0.7, 0.35)
        self.auto_dismiss = True
        self.settings_store = settings_store
        self.items = items
        self.on_apply = on_apply

        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        default_start, default_end = self._get_initial_range()

        controls = BoxLayout(size_hint_y=None, height=40, spacing=8)
        self.start_input = TextInput(text=default_start, multiline=False, size_hint_x=0.35)
        self.end_input = TextInput(text=default_end, multiline=False, size_hint_x=0.35)
        self.start_input.bind(on_text_validate=self._apply_filter)
        self.end_input.bind(on_text_validate=self._apply_filter)
        
        apply_button = Button(text="Apply", size_hint_x=0.15)
        apply_button.bind(on_release=self._apply_filter)
        clear_button = Button(text="Clear", size_hint_x=0.15)
        clear_button.bind(on_release=self._clear_filter)

        controls.add_widget(Label(text="Start:", size_hint_x=0.08))
        controls.add_widget(self.start_input)
        controls.add_widget(Label(text="End:", size_hint_x=0.08))
        controls.add_widget(self.end_input)
        controls.add_widget(apply_button)
        controls.add_widget(clear_button)
        root.add_widget(controls)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        self.info_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(self.info_label)

        close_button = Button(text="Close", size_hint_y=None, height=40)
        close_button.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close_button)

        self.content = root
        Clock.schedule_once(lambda _dt: setattr(self.start_input, "focus", True), 0.05)

    def _get_initial_range(self) -> Tuple[str, str]:
        """Load saved range or default to last 30 days."""
        now = datetime.now()
        fallback_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        fallback_end = now.strftime("%Y-%m-%d")

        saved_start = self.settings_store.get(self.SETTINGS_KEY_START, fallback_start).strip()
        saved_end = self.settings_store.get(self.SETTINGS_KEY_END, fallback_end).strip()
        return saved_start or fallback_start, saved_end or fallback_end

    def _parse_input_datetime(self, value: str, is_end: bool) -> Optional[datetime]:
        """Parse flexible date/datetime input."""
        text = (value or "").strip()
        if not text:
            return None

        patterns = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for pattern in patterns:
            try:
                parsed = datetime.strptime(text, pattern)
                if pattern == "%Y-%m-%d" and is_end:
                    return parsed.replace(hour=23, minute=59, second=59)
                return parsed
            except ValueError:
                continue
        return None

    def _apply_filter(self, *_args) -> None:
        """Apply the timeframe filter."""
        start_dt = self._parse_input_datetime(self.start_input.text, is_end=False)
        end_dt = self._parse_input_datetime(self.end_input.text, is_end=True)

        if not start_dt or not end_dt:
            self.info_label.text = "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]."
            self.info_label.color = (1.0, 0.45, 0.45, 1)
            return

        if end_dt < start_dt:
            self.info_label.text = "End must be >= Start."
            self.info_label.color = (1.0, 0.45, 0.45, 1)
            return

        # Save range
        self.settings_store.set(self.SETTINGS_KEY_START, self.start_input.text)
        self.settings_store.set(self.SETTINGS_KEY_END, self.end_input.text)

        # Filter items
        end_exclusive = end_dt + timedelta(seconds=1)
        filtered = [
            item for item in self.items
            if self._item_in_range(item, start_dt, end_exclusive)
        ]

        self.info_label.text = f"Filtered: {len(filtered)} of {len(self.items)} items in range."
        self.info_label.color = (0.6, 0.9, 0.6, 1)

        if self.on_apply:
            self.on_apply(filtered)

    def _item_in_range(self, item: Dict[str, str], start_dt: datetime, end_dt: datetime) -> bool:
        """Check if item timestamp is within range."""
        ts_str = item.get("timestamp", "")
        if not ts_str:
            return False
        try:
            item_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return start_dt <= item_dt < end_dt
        except (ValueError, TypeError):
            return False

    def _clear_filter(self, *_args) -> None:
        """Clear the filter and show all items."""
        self.settings_store.set(self.SETTINGS_KEY_START, "")
        self.settings_store.set(self.SETTINGS_KEY_END, "")
        self.info_label.text = "Filter cleared. Showing all items."
        self.info_label.color = (0.8, 0.8, 0.8, 1)
        if self.on_apply:
            self.on_apply(self.items)


class PartDetailsPopup(Popup):
    """Popup showing detailed information for all parts of a unit."""

    def __init__(self, parts: List[Dict[str, str]], serial: str, **kwargs):
        super().__init__(**kwargs)
        self.title = f"Parts for {serial}"
        self.size_hint = (0.8, 0.6)
        self.auto_dismiss = True

        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        # Parts list
        parts_container = ScrollView()
        parts_layout = GridLayout(cols=1, spacing=8, size_hint_y=None, padding=8)
        parts_layout.bind(minimum_height=parts_layout.setter('height'))

        if not parts:
            no_parts_label = Label(
                text="No parts scanned.",
                size_hint_y=None,
                height=40,
                font_size='14sp',
                color=(0.7, 0.7, 0.7, 1)
            )
            parts_layout.add_widget(no_parts_label)
        else:
            for part in parts:
                part_row = BoxLayout(size_hint_y=None, height=50, orientation="vertical", spacing=4, padding=8)
                
                name = part.get("part_name", "?")
                sn = part.get("part_sn", "-")
                
                # Part name
                name_label = Label(
                    text=f"Name: {name}",
                    halign="left",
                    valign="middle",
                    font_size='14sp',
                    bold=True,
                    color=(0.95, 0.95, 0.95, 1),
                    size_hint_y=0.5
                )
                name_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
                part_row.add_widget(name_label)
                
                # Part serial
                sn_label = Label(
                    text=f"SN: {sn}",
                    halign="left",
                    valign="middle",
                    font_size='12sp',
                    color=(0.85, 0.85, 0.85, 1),
                    size_hint_y=0.5
                )
                sn_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
                part_row.add_widget(sn_label)
                
                parts_layout.add_widget(part_row)

        parts_container.add_widget(parts_layout)
        root.add_widget(parts_container)

        # Close button
        close_button = Button(text="Close", size_hint_y=None, height=40, font_size='14sp')
        close_button.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close_button)

        self.content = root


class BackplateProvisioningPopup(Popup):
    """Popup for automatic provisioning of spare backplate units.
    
    Workflow:
    1. Auto-discover device
    2. Read SN + MAC
    3. Validate state (already_provisioned | ready_to_provision | error)
    4. If ready: Auto-unlock + Auto-provision MAC
    5. Show result
    6. Auto-detect device disconnect
    """

    def __init__(self, settings_store: DataToolsSettingsStore, **kwargs):
        super().__init__(**kwargs)
        self.title = "Provision Backplate Unit"
        self.size_hint = (0.85, 0.65)
        self.auto_dismiss = False
        self.settings_store = settings_store

        # Get defaults from settings
        self.default_serial = settings_store.get("backplate_default_serial", "123456")
        self.default_mac = settings_store.get("backplate_default_mac", "DE:AD:BE:EF:00:00")
        self.workstation_id = settings_store.get("backplate_workstation_id", "DataTools")
        self.mac_db_path = settings_store.get("mac_db_path", "")

        self.device = None
        self.discovered_target = None
        self.discovery_task = None
        self.current_serial = None
        self.current_mac = None

        # Setup module path once for this popup instance (isolated, not global)
        import sys
        from pathlib import Path
        workspace_root = Path(__file__).parent.parent.parent
        if str(workspace_root) not in sys.path:
            sys.path.insert(0, str(workspace_root))

        root = BoxLayout(orientation="vertical", spacing=12, padding=15)

        # --- Device Discovery Status ---
        discovery_row = BoxLayout(size_hint_y=None, height=50, spacing=10)
        discovery_row.add_widget(Label(text="Device:", size_hint_x=0.15, font_size='15sp', bold=True))
        self.discovery_label = Label(
            text="[Searching...]",
            size_hint_x=0.85,
            halign="left",
            valign="middle",
            font_size='14sp',
            color=(0.85, 0.85, 0.85, 1)
        )
        self.discovery_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        discovery_row.add_widget(self.discovery_label)
        root.add_widget(discovery_row)

        # --- Current SN / MAC Display ---
        info_row = BoxLayout(size_hint_y=None, height=70, spacing=10, orientation="vertical")
        
        self.current_serial_label = Label(
            text="Serial: -",
            size_hint_y=0.5,
            halign="left",
            valign="middle",
            font_size='13sp',
            color=(0.8, 0.8, 0.8, 1)
        )
        self.current_serial_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        info_row.add_widget(self.current_serial_label)
        
        self.current_mac_label = Label(
            text="MAC: -",
            size_hint_y=0.5,
            halign="left",
            valign="middle",
            font_size='13sp',
            color=(0.8, 0.8, 0.8, 1)
        )
        self.current_mac_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        info_row.add_widget(self.current_mac_label)
        root.add_widget(info_row)

        # --- Status Message ---
        self.status_label = Label(
            text="Waiting for device...",
            size_hint_y=None,
            height=80,
            halign="left",
            valign="top",
            font_size='13sp',
            markup=True,
            color=(0.85, 0.85, 0.85, 1)
        )
        self.status_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(self.status_label)

        # --- Close Button ---
        close_btn = Button(text="Close", size_hint_y=None, height=50, font_size='14sp', background_color=(0.7, 0.3, 0.3, 1))
        close_btn.bind(on_release=self._on_close)
        root.add_widget(close_btn)

        self.content = root

        # Start device discovery on popup open
        self.bind(on_open=self._start_discovery)
        self.bind(on_dismiss=self._stop_discovery)

    def _start_discovery(self, *_):
        """Start background device discovery task."""
        if self.discovery_task is None:
            self.discovery_task = Clock.schedule_interval(self._discover_device, 2.0)
            self._discover_device()  # Run once immediately

    def _stop_discovery(self, *_):
        """Stop background device discovery task."""
        if self.discovery_task:
            self.discovery_task.cancel()
            self.discovery_task = None

    def _discover_device(self, *_):
        """Discover available OCA devices and auto-connect."""
        try:
            from oca.oca_device import OCADevice
            temp_device = OCADevice(target=None)
            discover_result = temp_device.discover(timeout=1)
            devices = self._parse_discover_result(discover_result)
            
            if devices:
                target = devices[0]
                if target != self.discovered_target:
                    self.discovered_target = target
                    self._connect_device(target)
                return
            else:
                if self.discovered_target:
                    self.discovered_target = None
                    self._disconnect_device()
                self.discovery_label.text = "[Searching...]"
                self.discovery_label.color = (0.85, 0.85, 0.85, 1)
        except Exception as e:
            self.discovery_label.text = "[Searching...]"
            self.discovery_label.color = (0.85, 0.85, 0.85, 1)

    def _parse_discover_result(self, result):
        """Extract device targets from OCA discover result."""
        try:
            if isinstance(result, dict):
                if "devices" in result:
                    devices = result.get("devices", [])
                    if isinstance(devices, list) and len(devices) > 0:
                        targets = []
                        for dev in devices:
                            if isinstance(dev, dict):
                                # Prefer explicit "target", fall back to "name" or "ip"
                                t = dev.get("target") or dev.get("name") or dev.get("ip")
                                if t:
                                    targets.append(t)
                            elif isinstance(dev, str):
                                targets.append(dev)
                        return targets if targets else []
                if isinstance(result, list) and len(result) > 0:
                    return [d if isinstance(d, str) else d.get("target") or d.get("name") or d.get("ip", "") for d in result if d]
            if isinstance(result, str):
                lines = result.split('\n')
                targets = [line.strip() for line in lines if line.strip() and not line.startswith('[')]
                return targets if targets else []
        except Exception:
            pass
        return []

    def _connect_device(self, target):
        """Connect to device, read SN+MAC, and auto-validate + auto-provision if ready."""
        from oca.oca_device import OCADevice
        
        try:
            self.device = OCADevice(target=target, port=50001, timeout=5)
            
            # Read current SN + MAC
            serial_result = self.device.get_serial_number()
            mac_result = self.device.get_mac_address()
            
            self.current_serial = str(serial_result.get("value") or serial_result.get("raw") or "-").strip()
            self.current_mac = str(mac_result.get("value") or mac_result.get("raw") or "-").strip()
            
            self.current_serial_label.text = f"Serial: {self.current_serial}"
            self.current_mac_label.text = f"MAC: {self.current_mac}"
            
            self.discovery_label.text = f"[Connected] {target}"
            self.discovery_label.color = (0.6, 0.9, 0.6, 1)
            
            # Auto-validate and auto-provision if ready
            self._validate_and_auto_provision()
            
        except Exception as e:
            self.discovery_label.text = f"[Read failed]"
            self.discovery_label.color = (1.0, 0.7, 0.45, 1)
            self.status_label.text = f"Error reading device: {str(e)[:60]}"
            self.status_label.color = (1.0, 0.7, 0.45, 1)
            self.device = None

    def _validate_and_auto_provision(self):
        """Validate device state and auto-provision MAC if ready."""
        import SubProMACAddresses.mac_database as _mac_db
        _mac_db.DB_PATH = self.mac_db_path
        from SubProMACAddresses.mac_database import get_assigned_mac
        
        if not self.device or not self.current_serial or not self.current_mac:
            self.status_label.text = "Device not fully connected"
            self.status_label.color = (1.0, 0.7, 0.45, 1)
            return
        
        # CRITICAL: Check if device has default/invalid serial
        if self.current_serial.upper() == self.default_serial.upper():
            self.status_label.text = f"[ERROR] Device has default serial '{self.default_serial}' - not registered. Cannot provision."
            self.status_label.color = (1.0, 0.45, 0.45, 1)
            return
        
        # Normalize MACs for comparison
        current_mac_norm = self.current_mac.upper()
        default_mac_norm = self.default_mac.upper()
        
        # Case 1: Device has default MAC → Ready to provision
        if current_mac_norm == default_mac_norm:
            self.status_label.text = "Status: Ready to provision. Unlocking device..."
            self.status_label.color = (0.85, 0.85, 0.85, 1)
            
            # Auto-unlock
            try:
                unlock_result = self.device.unlock_factory_settings('DEADBEEF')
                self.status_label.text = "Status: Device unlocked. Provisioning MAC..."
                self.status_label.color = (0.85, 0.85, 0.85, 1)
                
                # Auto-provision
                self._auto_provision_mac()
            except Exception as e:
                self.status_label.text = f"Unlock failed: {str(e)[:70]}"
                self.status_label.color = (1.0, 0.45, 0.45, 1)
            
            return
        
        # Case 2: Device has unique MAC → Check if already provisioned
        db_mac = get_assigned_mac(self.current_serial)
        
        if db_mac is None:
            # Unknown device with unique MAC
            self.status_label.text = f"[ERROR] Unknown device: has MAC {current_mac_norm} but SN not in DB"
            self.status_label.color = (1.0, 0.45, 0.45, 1)
            return
        
        if current_mac_norm != db_mac.upper():
            # MAC mismatch
            self.status_label.text = f"[ERROR] MAC mismatch: DB={db_mac}, device={current_mac_norm}"
            self.status_label.color = (1.0, 0.45, 0.45, 1)
            return
        
        # Already provisioned - success state
        self.status_label.text = (
            f"[b][size=18sp]✓  RE-TEST OK[/size][/b]\n"
            f"MAC: {current_mac_norm}\n"
            f"Disconnect to provision next unit."
        )
        self.status_label.height = 110
        self.status_label.color = (0.3, 1.0, 0.45, 1)

    def _auto_provision_mac(self):
        """Auto-provision MAC without manual input."""
        import SubProMACAddresses.mac_database as _mac_db
        _mac_db.DB_PATH = self.mac_db_path
        from SubProMACAddresses.mac_provisioner import provision_mac
        
        try:
            prov_result = provision_mac(
                device=self.device,
                serial=self.current_serial,
                workstation_id=self.workstation_id,
                default_mac=self.default_mac,
                arp_delay=3.0
            )
            
            if prov_result.get("status") in ("success", "retest_ok"):
                assigned_mac = prov_result.get("mac", "?")
                low_pool = prov_result.get("low_pool", False)
                warning = "  [b][color=ff8800]LOW POOL[/color][/b]" if low_pool else ""
                self.status_label.text = (
                    f"[b][size=18sp]✓  PROVISIONED{warning}[/size][/b]\n"
                    f"Serial: {self.current_serial}\n"
                    f"MAC: {assigned_mac}\n"
                    f"Disconnect to provision next unit."
                )
                self.status_label.height = 130
                self.status_label.color = (0.3, 1.0, 0.45, 1)
                self.current_mac_label.text = f"MAC: {assigned_mac}"
            else:
                reason = prov_result.get("reason", "unknown")
                detail = prov_result.get("detail", "")
                self.status_label.text = f"[ERROR] {reason.upper()}: {detail[:60]}"
                self.status_label.color = (1.0, 0.45, 0.45, 1)
        
        except Exception as e:
            self.status_label.text = f"[ERROR] Provisioning failed: {str(e)[:70]}"
            self.status_label.color = (1.0, 0.45, 0.45, 1)

    def _disconnect_device(self):
        """Disconnect current device and reset UI."""
        self.device = None
        self.current_serial = None
        self.current_mac = None
        self.current_serial_label.text = "Serial: -"
        self.current_mac_label.text = "MAC: -"
        self.status_label.text = "Waiting for device..."
        self.status_label.color = (0.85, 0.85, 0.85, 1)
        self.discovery_label.text = "[Searching...]"
        self.discovery_label.color = (0.85, 0.85, 0.85, 1)

    def _on_close(self, *_):
        """Close popup."""
        self.dismiss()


class TristarDatabasesViewerRoot(BoxLayout):
    """Main read-only Tristar Databases unified viewer layout."""

    STATUS_INFO_COLOR = (0.75, 0.75, 0.75, 1)
    STATUS_SUCCESS_COLOR = (0.6, 0.9, 0.6, 1)
    STATUS_ERROR_COLOR = (1.0, 0.45, 0.45, 1)

    def __init__(self, settings_store: DataToolsSettingsStore, on_back=None, **kwargs):
        super().__init__(orientation="vertical", spacing=10, padding=12, **kwargs)
        self.settings_store = settings_store
        self.on_back = on_back
        
        # Initialize tooltip manager
        self.tooltip_manager = DelayedTooltipManager(delay_seconds=1.2)
        
        sn_fw_path = settings_store.get("sn_fw_db_path", "")
        mac_path = settings_store.get("mac_db_path", "")
        self.repository = TristarRepository(sn_fw_path, mac_path)
        
        self.units: List[Dict[str, str]] = []
        self.filtered_units: List[Dict[str, str]] = []
        self.mac_status: Optional[Dict[str, str]] = None

        # --- Header: Title + Back Button ---
        header = BoxLayout(size_hint_y=None, height=42, spacing=8)
        title = Label(
            text="Tristar Databases",
            font_size="26sp",
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        header.add_widget(title)

        if self.on_back is not None:
            back_button = Button(text="Back to Home", size_hint_x=None, width=150)
            back_button.bind(on_release=lambda *_: self._on_back())
            header.add_widget(back_button)
            self.tooltip_manager.register(back_button, "Return to the home screen.")

        self.add_widget(header)

        # --- Database Paths Label ---
        self.db_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
            font_size="12sp"
        )
        self.db_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        if sn_fw_path or mac_path:
            self.db_label.text = f"Database: {sn_fw_path or 'N/A'}"
        self.add_widget(self.db_label)

        # --- Toolbar ---
        toolbar = BoxLayout(size_hint_y=None, height=42, spacing=8)
        refresh_button = Button(text="Refresh")
        refresh_button.bind(on_release=lambda *_: self._refresh_data())
        filter_button = Button(text="Filter")
        filter_button.bind(on_release=lambda *_: self._open_timeframe_filter())
        export_button = Button(text="Export CSV")
        export_button.bind(on_release=lambda *_: self.export_csv_snapshot())
        backplate_button = Button(text="Provision Backplate", background_color=(0.3, 0.6, 0.8, 1))
        backplate_button.bind(on_release=lambda *_: self._open_backplate_provisioning())
        toolbar.add_widget(refresh_button)
        toolbar.add_widget(filter_button)
        toolbar.add_widget(export_button)
        toolbar.add_widget(backplate_button)
        
        # Register tooltips for toolbar buttons
        self.tooltip_manager.register(refresh_button, "Reload data from databases")
        self.tooltip_manager.register(filter_button, "Filter units by date range")
        self.tooltip_manager.register(export_button, "Export current units and parts to CSV file")
        self.tooltip_manager.register(backplate_button, "Automatically provision MAC addresses for spare units")
        
        self.add_widget(toolbar)

        # Summary row
        summary_layout = BoxLayout(size_hint_y=None, height=60, spacing=20, padding=(15, 10))
        self.summary_label = Label(
            text="Loading...",
            size_hint_y=None,
            height=60,
            halign="left",
            valign="middle",
            color=(0.9, 0.9, 0.9, 1),
            font_size='18sp',
            bold=True
        )
        self.summary_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        summary_layout.add_widget(self.summary_label)
        self.add_widget(summary_layout)

        # MAC Status Panel - Grid Layout for better readability
        mac_panel = BoxLayout(orientation="vertical", size_hint_y=None, height=135, spacing=10, padding=(15, 12))
        
        # Title
        mac_title = Label(
            text="MAC Address Pool Status",
            size_hint_y=None,
            height=30,
            font_size='17sp',
            bold=True,
            color=(0.9, 0.9, 0.9, 1),
            halign="left",
            valign="middle"
        )
        mac_title.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        mac_panel.add_widget(mac_title)
        
        # Pool info grid (top row)
        pool_row = BoxLayout(size_hint_y=None, height=35, spacing=20)
        self.mac_pool_label = Label(
            text="Pool: Loading...",
            size_hint_x=0.5,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
            font_size='15sp'
        )
        self.mac_pool_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        pool_row.add_widget(self.mac_pool_label)
        
        self.mac_next_label = Label(
            text="Next: Loading...",
            size_hint_x=0.5,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
            font_size='15sp'
        )
        self.mac_next_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        pool_row.add_widget(self.mac_next_label)
        mac_panel.add_widget(pool_row)
        
        # Stats row (bottom)
        stats_row = BoxLayout(size_hint_y=None, height=35, spacing=20)
        self.mac_remaining_label = Label(
            text="Remaining: Loading...",
            size_hint_x=0.33,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
            font_size='15sp'
        )
        self.mac_remaining_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        stats_row.add_widget(self.mac_remaining_label)
        
        self.mac_provisioned_label = Label(
            text="Provisioned: Loading...",
            size_hint_x=0.33,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
            font_size='15sp'
        )
        self.mac_provisioned_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        stats_row.add_widget(self.mac_provisioned_label)
        
        self.mac_warn_label = Label(
            text="Threshold: Loading...",
            size_hint_x=0.34,
            halign="left",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1),
            font_size='15sp'
        )
        self.mac_warn_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        stats_row.add_widget(self.mac_warn_label)
        mac_panel.add_widget(stats_row)
        
        self.add_widget(mac_panel)

        # Units list
        self.units_container = ScrollView()
        self.units_layout = GridLayout(cols=1, spacing=15, size_hint_y=None, padding=12)
        self.units_layout.bind(minimum_height=self.units_layout.setter('height'))
        self.units_container.add_widget(self.units_layout)
        self.add_widget(self.units_container)

        # Serial input
        serial_layout = BoxLayout(size_hint_y=None, height=50, spacing=10, padding=(10, 5))
        serial_label = Label(
            text="Serial Lookup:",
            size_hint_x=0.15,
            font_size='16sp',
            halign="right",
            valign="middle",
            color=(0.85, 0.85, 0.85, 1)
        )
        serial_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        serial_layout.add_widget(serial_label)
        self.serial_input = TextInput(
            text="",
            multiline=False,
            size_hint_x=0.70,
            font_size='16sp'
        )
        self.serial_input.bind(on_text_validate=self._show_serial_lookup)
        serial_layout.add_widget(self.serial_input)
        self.add_widget(serial_layout)

        # Status footer
        self.status_label = Label(
            text="Ready.",
            size_hint_y=None,
            height=35,
            halign="left",
            valign="middle",
            color=self.STATUS_INFO_COLOR,
            font_size='14sp'
        )
        self.status_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.add_widget(self.status_label)

        # Load initial data
        Clock.schedule_once(lambda _dt: self._refresh_data(), 0.1)

    def _refresh_data(self) -> None:
        """Reload units and MAC status from databases."""
        self.units = self.repository.get_all_units()
        self.filtered_units = self.units
        self.mac_status = self.repository.get_mac_status()
        self._update_ui()

    def _update_ui(self) -> None:
        """Update all UI elements with current data."""
        self._update_summary()
        self._update_mac_status()
        self._update_units_list()
        self._set_status_message("Data refreshed.", is_error=False)

    def _update_summary(self) -> None:
        """Update the summary row."""
        summary = self.repository.get_summary()
        text = (
            f"Total Units: {summary['total_units']} | "
            f"With MAC: {summary['units_with_mac']} | "
            f"Parts Complete: {summary['units_with_complete_parts']}"
        )
        self.summary_label.text = text

    def _update_mac_status(self) -> None:
        """Update MAC pool status panel with grid layout."""
        if not self.mac_status:
            self.mac_pool_label.text = "Pool: Database unavailable"
            self.mac_next_label.text = "Next: -"
            self.mac_remaining_label.text = "Remaining: -"
            self.mac_provisioned_label.text = "Provisioned: -"
            self.mac_warn_label.text = "Threshold: -"
            return

        status = self.mac_status
        self.mac_pool_label.text = f"Pool: {status['start_mac']} to {status['end_mac']}"
        self.mac_next_label.text = f"Next: {status['next_mac']}"
        self.mac_remaining_label.text = f"Remaining: {status['remaining_count']}/{status['total_count']}"
        self.mac_provisioned_label.text = f"Provisioned: {status['provisioned_count']}"
        self.mac_warn_label.text = f"Threshold: {status['warn_threshold']}"


    def _update_units_list(self) -> None:
        """Update the units list with parts information."""
        self.units_layout.clear_widgets()
        if not self.filtered_units:
            empty_label = Label(
                text="No units found.",
                size_hint_y=None,
                height=40,
                font_size='16sp',
                color=(0.7, 0.7, 0.7, 1)
            )
            self.units_layout.add_widget(empty_label)
            return

        for unit in self.filtered_units:
            # Container for each unit (two rows)
            unit_container = BoxLayout(orientation="vertical", size_hint_y=None, height=70, spacing=4, padding=8)
            
            unit_id = unit.get("id", None)
            serial = unit.get("product_sn", "?")
            mac = unit.get("mac", "-")
            fw = unit.get("fw_version_final", "-")
            timestamp = unit.get("timestamp", "-")
            parts_complete = unit.get("parts_complete", False)
            
            # Get parts for this unit
            parts = self.repository.get_unit_parts(unit_id) if unit_id else []
            parts_text = ", ".join([p.get("part_name", "?") for p in parts]) if parts else "No parts"
            
            # Parts status color and text
            parts_status_text = "Complete" if parts_complete else "Missing Parts!"
            parts_status_color = (0.4, 0.8, 0.4, 1) if parts_complete else (1.0, 0.4, 0.4, 1)
            
            # Row 1: Serial (bold)
            row1 = BoxLayout(size_hint_y=0.35, spacing=10)
            sn_label = Label(
                text=f"SN: {serial}",
                halign="left",
                valign="middle",
                font_size='16sp',
                bold=True,
                color=(0.95, 0.95, 0.95, 1),
                size_hint_x=0.80
            )
            sn_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row1.add_widget(sn_label)
            
            # Parts complete status indicator
            status_label = Label(
                text=parts_status_text,
                halign="center",
                valign="middle",
                font_size='11sp',
                bold=True,
                color=parts_status_color,
                size_hint_x=0.20
            )
            status_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row1.add_widget(status_label)
            unit_container.add_widget(row1)
            
            # Row 2: MAC, Parts (clickable), FW, Date
            row2 = BoxLayout(size_hint_y=0.65, spacing=12)
            
            # MAC
            mac_label = Label(
                text=f"MAC: {mac}",
                halign="left",
                valign="middle",
                font_size='12sp',
                color=(0.85, 0.85, 0.85, 1),
                size_hint_x=0.20
            )
            mac_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row2.add_widget(mac_label)
            
            # Parts (clickable button)
            parts_button = Button(
                text=parts_text if len(parts_text) <= 25 else parts_text[:22] + "...",
                size_hint_x=0.35,
                font_size='11sp'
            )
            parts_button.bind(on_release=lambda *_, u_id=unit_id, s=serial, p=parts: self._show_parts_details(u_id, s, p))
            row2.add_widget(parts_button)
            
            # Firmware
            fw_label = Label(
                text=f"FW: {fw}",
                halign="left",
                valign="middle",
                font_size='12sp',
                color=(0.85, 0.85, 0.85, 1),
                size_hint_x=0.25
            )
            fw_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row2.add_widget(fw_label)
            
            # Date
            date_text = timestamp[:10] if timestamp else "-"
            date_label = Label(
                text=f"Date: {date_text}",
                halign="left",
                valign="middle",
                font_size='12sp',
                color=(0.75, 0.75, 0.75, 1),
                size_hint_x=0.20
            )
            date_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row2.add_widget(date_label)
            unit_container.add_widget(row2)
            
            self.units_layout.add_widget(unit_container)

    def _show_serial_lookup(self, *_args) -> None:
        """Look up a unit by serial and show details."""
        serial = self.serial_input.text.strip()
        if not serial:
            return

        unit = self.repository.get_unit_by_serial(serial)
        if not unit:
            self._set_status_message(f"Serial '{serial}' not found.", is_error=True)
            self.serial_input.text = ""
            return

        self._show_unit_details(unit)
        self.serial_input.text = ""

    def _show_unit_details(self, unit: Dict[str, str]) -> None:
        """Open a popup showing full unit details."""
        UnitDetailsPopup(unit=unit, repository=self.repository).open()

    def _show_parts_details(self, unit_id: int, serial: str, parts: List[Dict[str, str]]) -> None:
        """Open a popup showing all parts for a unit."""
        PartDetailsPopup(parts=parts, serial=serial).open()

    def _on_back(self) -> None:
        """Handle back button."""
        if self.on_back:
            self.on_back()

    def _set_status_message(self, message: str, is_error: bool = False) -> None:
        """Set status footer text and color."""
        self.status_label.text = message
        self.status_label.color = self.STATUS_ERROR_COLOR if is_error else self.STATUS_INFO_COLOR

    def _open_timeframe_filter(self) -> None:
        """Open timeframe filter popup for the units list."""
        if not self.repository.sn_fw_exists():
            self._set_status_message("Cannot filter: SN/FW database unavailable.", is_error=True)
            return

        ListTimeframeFilterPopup(
            items=self.units,
            settings_store=self.settings_store,
            on_apply=self._apply_filter
        ).open()

    def _apply_filter(self, filtered_units: List[Dict[str, str]]) -> None:
        """Apply filtered units list to the UI."""
        self.filtered_units = filtered_units
        self._update_units_list()
        self._set_status_message(f"Showing {len(filtered_units)}/{len(self.units)} units.")

    def export_csv_snapshot(self) -> None:
        """Export units with all parts in one column."""
        if not self.repository.sn_fw_exists():
            self._set_status_message("Export failed: SN/FW database unavailable.", is_error=True)
            return

        default_folder = self.settings_store.get("default_export_folder", "")
        target_path = self._choose_export_target(default_folder)
        if not target_path:
            self._set_status_message("Export canceled.")
            return

        # Get current filter dates if any
        start_dt_str = self.settings_store.get(ListTimeframeFilterPopup.SETTINGS_KEY_START, "").strip()
        end_dt_str = self.settings_store.get(ListTimeframeFilterPopup.SETTINGS_KEY_END, "").strip()

        # If no filter dates saved, use all units
        if start_dt_str and end_dt_str:
            # Parse and prepare end date as exclusive
            try:
                start_dt = datetime.fromisoformat(start_dt_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_dt_str.replace("Z", "+00:00"))
                end_dt = end_dt + timedelta(days=1)  # Make end exclusive (full day)
            except (ValueError, TypeError):
                start_dt = None
                end_dt = None
        else:
            start_dt = None
            end_dt = None

        # Get units (filtered or all)
        if start_dt and end_dt:
            units = self.repository.get_units_in_period(
                start_dt.isoformat(timespec="seconds"),
                end_dt.isoformat(timespec="seconds")
            )
        else:
            units = self.repository.get_all_units()

        try:
            with Path(target_path).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["product_sn", "mac", "fw_version_final", "timestamp", "parts_complete", "parts"],
                    extrasaction="ignore",
                )
                writer.writeheader()
                
                for unit in units:
                    unit_id = unit.get("id")
                    parts = self.repository.get_unit_parts(unit_id) if unit_id else []
                    
                    # Build parts string: "Driver (SN_001), Tweeter (SN_002)"
                    parts_str = ", ".join([f"{p.get('part_name')} ({p.get('part_sn')})" for p in parts])
                    
                    row = {
                        "product_sn": unit.get("product_sn"),
                        "mac": unit.get("mac"),
                        "fw_version_final": unit.get("fw_version_final"),
                        "timestamp": unit.get("timestamp"),
                        "parts_complete": "Yes" if unit.get("parts_complete") else "No",
                        "parts": parts_str
                    }
                    writer.writerow(row)

            self._set_status_message(
                f"Exported {len(units)} units to {Path(target_path).name}",
                is_error=False
            )
        except Exception as e:
            self._set_status_message(f"Export failed: {str(e)}", is_error=True)

    def _open_backplate_provisioning(self) -> None:
        """Open the backplate provisioning popup."""
        BackplateProvisioningPopup(settings_store=self.settings_store).open()

    @staticmethod
    def _choose_export_target(default_folder: str) -> str:
        """Open native save dialog for CSV export."""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.asksaveasfilename(
            initialdir=default_folder or None,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="tristar_snapshot.csv",
        )
        root.destroy()
        return selected or ""


class UnitDetailsPopup(Popup):
    """Popup showing full details for one unit."""

    def __init__(self, unit: Dict[str, str], repository: TristarRepository, **kwargs):
        super().__init__(**kwargs)
        self.title = f"Unit Details: {unit.get('product_sn', '?')}"
        self.size_hint = (0.8, 0.9)
        self.auto_dismiss = True

        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        # Unit info
        info_text = (
            f"Serial: {unit.get('product_sn', '?')}\n"
            f"Firmware: {unit.get('fw_version_final', '?')}\n"
            f"Result: {unit.get('result', '?')}\n"
            f"MAC: {unit.get('mac', '-')}\n"
            f"Parts Complete: {'Yes' if unit.get('parts_complete') else 'No'}\n"
            f"Timestamp: {unit.get('timestamp', '?')}"
        )
        info_label = Label(text=info_text, size_hint_y=None, height=120)
        root.add_widget(info_label)

        # Parts list
        root.add_widget(Label(text="Scanned Parts:", size_hint_y=None, height=20))
        parts = repository.get_unit_parts(unit.get("id", 0))
        if not parts:
            root.add_widget(Label(text="No parts scanned.", size_hint_y=None, height=30))
        else:
            parts_scroll = ScrollView()
            parts_layout = GridLayout(cols=1, spacing=4, size_hint_y=None, padding=4)
            parts_layout.bind(minimum_height=parts_layout.setter('height'))
            for part in parts:
                part_text = (
                    f"{part.get('part_name', '?')}: {part.get('part_sn', '?')} "
                    f"({part.get('timestamp', '?')})"
                )
                parts_layout.add_widget(
                    Label(text=part_text, size_hint_y=None, height=20)
                )
            parts_scroll.add_widget(parts_layout)
            root.add_widget(parts_scroll)

        # Close button
        close_btn = Button(text="Close", size_hint_y=None, height=40)
        close_btn.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close_btn)

        self.content = root
