"""
DataTools Matching Viewer
=========================

This module implements the complete in-app read-only Matching viewer experience.

Design goals
------------
1. Inspect data safely: no write operations to matcher DB.
2. Keep operations fast: short-lived SQLite connections per query.
3. Support operator workflows: serial scan, mode switching, curve overlays.
4. Provide robust feedback: explicit status/error messages in the UI.

What the viewer does
--------------------
- Reads matcher database content via `MatchingRepository`
- Shows pool, matched, and paired lists
- Renders single or paired frequency response plots
- Provides timeframe overlay plotting in a popup
- Exports read-only CSV snapshots

Boundary
--------
The matcher database itself remains external to DataTools settings storage.
DataTools only persists the path to that external matcher DB and UI preferences.
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
import statistics
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
from kivy_garden.graph import Graph, LinePlot

from app.settings_store import DataToolsSettingsStore


# ---------------------------------------------------------------------------
# Data Access Layer (Read-Only)
# ---------------------------------------------------------------------------
# `MatchingRepository` is intentionally isolated from UI widgets so queries,
# parsing, and storage format assumptions remain testable and easier to refactor.


class MatchingRepository:
    """
    Read-only helper for the external matcher SQLite database.

    The repository reads all view data from the path configured in the
    DataTools settings store.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve() if db_path else None

    def is_configured(self) -> bool:
        """Return True when a database path is configured."""
        return self.db_path is not None

    def exists(self) -> bool:
        """Return True when the configured database file exists."""
        return bool(self.db_path and self.db_path.exists())

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived SQLite connection to the matcher DB."""
        if not self.db_path:
            raise FileNotFoundError("Matching database path is not configured")
        if not self.db_path.exists():
            raise FileNotFoundError(f"Matching database not found: {self.db_path}")

        connection = sqlite3.connect(str(self.db_path))
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def get_summary(self) -> Dict[str, int]:
        """Return counts for pool, matched, paired drivers, and assembled systems."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM drivers WHERE status = 'unmatched'")
            pool_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM drivers WHERE status = 'matched'")
            matched_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM drivers WHERE status = 'paired'")
            paired_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM system_builds")
            assembled_count = cursor.fetchone()[0]

        return {
            "pool": pool_count,
            "matched": matched_count,
            "paired": paired_count,
            "assembled": assembled_count,
        }

    def get_assembled_items(self) -> List[Dict[str, str]]:
        """Return system_builds rows for the Assembled list."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT system_serial, module_1, module_2, built_at
                FROM system_builds
                ORDER BY built_at DESC, system_serial
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "system_serial": row[0],
                "module_1": row[1] or "",
                "module_2": row[2] or "",
                "built_at": row[3] or "",
                "label": f"{row[0]}  ({row[1]} / {row[2]})",
            }
            for row in rows
        ]

    def get_pool_items(self) -> List[Dict[str, str]]:
        """Return unmatched drivers for the pool list."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT serial, side, loaded_at
                FROM drivers
                WHERE status = 'unmatched'
                ORDER BY side, serial
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "serial": row[0],
                "side": row[1],
                "loaded_at": row[2] or "",
                "label": f"{row[1].title()}: {row[0]}",
            }
            for row in rows
        ]

    def get_pair_items(self, status: str) -> List[Dict[str, str]]:
        """
        Return left/right pair rows for one pair-like driver status.

        Args:
            status: Either 'matched' or 'paired'.
        """
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT serial, partner, matched_at
                FROM drivers
                WHERE status = ? AND side = 'left'
                ORDER BY COALESCE(matched_at, ''), serial
                """,
                (status,),
            )
            rows = cursor.fetchall()

        return [
            {
                "left_serial": row[0],
                "right_serial": row[1] or "",
                "matched_at": row[2] or "",
                "label": f"{row[0]}  <->  {row[1] or '-'}",
            }
            for row in rows
        ]

    def get_frequency_vector(self) -> Optional[List[float]]:
        """Return the stored frequency axis or None."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT frequencies FROM frequency_vector WHERE id = 1")
            row = cursor.fetchone()

        if not row:
            return None
        return json.loads(row[0])

    def get_driver_levels(self, serial: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
        """Return frequency vector and curve levels for one serial."""
        frequency_vector = self.get_frequency_vector()
        if frequency_vector is None:
            return None, None

        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT levels FROM drivers WHERE serial = ?", (serial,))
            row = cursor.fetchone()

        if not row:
            return None, None
        return frequency_vector, json.loads(row[0])

    def get_all_drivers(self) -> List[Dict[str, str]]:
        """Return all driver rows for CSV export."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT serial, side, status, partner, loaded_at, matched_at
                FROM drivers
                ORDER BY status, side, serial
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "serial": row[0],
                "side": row[1],
                "status": row[2],
                "partner": row[3] or "",
                "loaded_at": row[4] or "",
                "matched_at": row[5] or "",
            }
            for row in rows
        ]

    def lookup_driver(self, serial: str) -> Optional[Dict[str, str]]:
        """Return one driver row including side, status, and partner."""
        normalized_serial = (serial or "").strip().upper()
        if not normalized_serial:
            return None

        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT serial, side, status, partner, loaded_at, matched_at
                FROM drivers
                WHERE serial = ?
                """,
                (normalized_serial,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return {
            "serial": row[0],
            "side": row[1],
            "status": row[2],
            "partner": row[3] or "",
            "loaded_at": row[4] or "",
            "matched_at": row[5] or "",
        }

    def get_curves_in_period(self, start_iso: str, end_iso_exclusive: str) -> Tuple[List[float], List[Dict[str, object]]]:
        """
        Return all module curves loaded within the requested time range.

        Args:
            start_iso: Inclusive start timestamp as ISO string.
            end_iso_exclusive: Exclusive end timestamp as ISO string.

        Returns:
            Tuple of (frequency_vector, curve_rows). Each curve row includes
            serial, side, loaded_at, and levels.
        """
        frequency_vector = self.get_frequency_vector() or []
        if not frequency_vector:
            return [], []

        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT serial, side, loaded_at, levels
                FROM drivers
                WHERE loaded_at >= ? AND loaded_at < ?
                ORDER BY loaded_at, serial
                """,
                (start_iso, end_iso_exclusive),
            )
            rows = cursor.fetchall()

        curve_rows = [
            {
                "serial": row[0],
                "side": row[1],
                "loaded_at": row[2] or "",
                "levels": json.loads(row[3]) if row[3] else [],
            }
            for row in rows
        ]
        return frequency_vector, curve_rows


class CurveChart(BoxLayout):
    """Read-only frequency response chart for one driver or one pair."""

    LEFT_COLOR = [0.2, 0.6, 1, 1]
    RIGHT_COLOR = [1, 0.4, 0.2, 1]

    def __init__(self, repository: MatchingRepository, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.repository = repository
        self._graph = Graph(
            xlabel="Frequency (Hz)",
            ylabel="Level (dB SPL)",
            xlog=True,
            x_ticks_major=1,
            x_ticks_minor=10,
            y_ticks_major=10,
            x_grid=True,
            y_grid=True,
            x_grid_label=True,
            y_grid_label=True,
            xmin=10,
            xmax=20000,
            ymin=50,
            ymax=110,
            padding=5,
            border_color=[0.3, 0.3, 0.3, 1],
            label_options={"color": [0.7, 0.7, 0.7, 1], "bold": False},
            background_color=[0.1, 0.1, 0.1, 1],
            tick_color=[0.3, 0.3, 0.3, 1],
        )
        self._plot_left = LinePlot(color=self.LEFT_COLOR, line_width=1.5)
        self._plot_right = LinePlot(color=self.RIGHT_COLOR, line_width=1.5)
        self._graph.add_plot(self._plot_left)
        self._graph.add_plot(self._plot_right)
        self.add_widget(self._graph)

    def clear(self) -> None:
        """Clear both plots."""
        self._plot_left.points = []
        self._plot_right.points = []

    def show_driver(self, serial: str, side: str) -> bool:
        """Render one single driver curve."""
        freqs, levels = self.repository.get_driver_levels(serial)
        if not freqs or not levels:
            return False

        points = list(zip(freqs, levels))
        if side == "left":
            self._plot_left.points = points
            self._plot_right.points = []
        else:
            self._plot_right.points = points
            self._plot_left.points = []

        self._auto_range(freqs, levels)
        return True

    def show_pair(self, left_serial: str, right_serial: str) -> bool:
        """Render one matched or paired left/right overlay."""
        freqs_left, levels_left = self.repository.get_driver_levels(left_serial)
        freqs_right, levels_right = self.repository.get_driver_levels(right_serial)
        if not freqs_left or not levels_left or not freqs_right or not levels_right:
            return False

        self._plot_left.points = list(zip(freqs_left, levels_left))
        self._plot_right.points = list(zip(freqs_right, levels_right))
        all_levels = levels_left + levels_right
        all_freqs = freqs_left if len(freqs_left) >= len(freqs_right) else freqs_right
        self._auto_range(all_freqs, all_levels)
        return True

    def _auto_range(self, freqs: List[float], levels: List[float]) -> None:
        """Adjust chart axis range to visible data."""
        self._graph.xmin = max(min(freqs), 10)
        self._graph.xmax = max(freqs)

        raw_min = min(levels)
        raw_max = max(levels)
        value_range = max(raw_max - raw_min, 0.5)
        padding = max(0.8, value_range * 0.12)

        ymin = raw_min - padding
        ymax = raw_max + padding

        # Keep a minimum visible span so nearly identical traces remain readable.
        min_span = 6.0
        if (ymax - ymin) < min_span:
            center = (raw_min + raw_max) / 2
            half_span = min_span / 2
            ymin = center - half_span
            ymax = center + half_span

        self._graph.ymin = math.floor(ymin)
        self._graph.ymax = math.ceil(ymax)
        y_range = self._graph.ymax - self._graph.ymin

        if y_range <= 12:
            self._graph.y_ticks_major = 1
        elif y_range <= 24:
            self._graph.y_ticks_major = 2
        else:
            self._graph.y_ticks_major = 5


class ListSection(BoxLayout):
    """Reusable scrollable list panel for pool, matched, and paired entries."""

    def __init__(self, title: str, show_title: bool = True, **kwargs):
        super().__init__(orientation="vertical", spacing=6, **kwargs)
        self._on_select = None
        self._items: List[Dict[str, str]] = []

        if show_title:
            title_label = Label(
                text=title,
                bold=True,
                size_hint_y=None,
                height=30,
                halign="left",
                valign="middle",
            )
            title_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            self.add_widget(title_label)

        self._scroll = ScrollView(size_hint=(1, 1))
        self._content = GridLayout(cols=1, spacing=6, size_hint_y=None)
        self._content.bind(minimum_height=self._content.setter("height"))
        self._scroll.add_widget(self._content)
        self.add_widget(self._scroll)

    def set_items(self, items: List[Dict[str, str]], on_select) -> None:
        """Rebuild the section button list with fresh read-only items."""
        self._on_select = on_select
        self._items = items
        self._content.clear_widgets()

        if not items:
            empty = Label(
                text="No entries",
                size_hint_y=None,
                height=34,
                color=(0.7, 0.7, 0.7, 1),
            )
            self._content.add_widget(empty)
            return

        for item in items:
            button = Button(
                text=item["label"],
                size_hint_y=None,
                height=40,
                halign="left",
                valign="middle",
                text_size=(0, 0),
            )
            button.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width - dp(16), instance.height)))
            button.bind(on_release=lambda _button, selected=item: self._on_select(selected))
            self._content.add_widget(button)


class ExportInfoPopup(Popup):
    """Small feedback popup used after CSV export."""

    def __init__(self, title: str, message: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.45, 0.28)
        self.auto_dismiss = True

        layout = BoxLayout(orientation="vertical", spacing=10, padding=12)
        label = Label(text=message)
        close_button = Button(text="Close", size_hint_y=None, height=42)
        close_button.bind(on_release=lambda *_: self.dismiss())
        layout.add_widget(label)
        layout.add_widget(close_button)
        self.content = layout


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


class ListTimeframeFilterPopup(Popup):
    """
    Generic popup for filtering list items by date range.
    Used for Pool (loaded_at), Matched (loaded_at), and Paired (matched_at).
    """

    def __init__(
        self,
        title: str,
        settings_store: DataToolsSettingsStore,
        items: List[Dict[str, str]],
        date_field: str,
        on_apply,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.settings_store = settings_store
        self.items = items
        self.date_field = date_field
        self.on_apply = on_apply
        self.title = title
        self.size_hint = (0.65, 0.38)
        self.auto_dismiss = True

        settings_key_start = f"filter_{date_field}_start"
        settings_key_end = f"filter_{date_field}_end"
        self.settings_key_start = settings_key_start
        self.settings_key_end = settings_key_end

        root = BoxLayout(orientation="vertical", spacing=10, padding=12)

        hint = Label(
            text="Date range format: YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]",
            size_hint_y=None,
            height=22,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        hint.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(hint)

        default_start, default_end = self._get_initial_range()

        controls = BoxLayout(size_hint_y=None, height=40, spacing=8)
        self.start_input = TextInput(text=default_start, multiline=False, size_hint_x=0.32)
        self.end_input = TextInput(text=default_end, multiline=False, size_hint_x=0.32)
        self.start_input.bind(on_text_validate=self._apply_filter)
        self.end_input.bind(on_text_validate=self._apply_filter)

        apply_button = Button(text="Apply", size_hint_x=0.2)
        apply_button.bind(on_release=self._apply_filter)
        close_button = Button(text="Close", size_hint_x=0.16)
        close_button.bind(on_release=lambda *_: self.dismiss())

        controls.add_widget(Label(text="Start:", size_hint_x=0.08))
        controls.add_widget(self.start_input)
        controls.add_widget(Label(text="End:", size_hint_x=0.08))
        controls.add_widget(self.end_input)
        controls.add_widget(apply_button)
        controls.add_widget(close_button)
        root.add_widget(controls)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=22,
            halign="left",
            valign="middle",
            color=(0.75, 0.75, 0.75, 1),
        )
        self.info_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(self.info_label)

        self.content = root
        Clock.schedule_once(lambda _dt: setattr(self.start_input, "focus", True), 0.05)

    def _get_initial_range(self) -> Tuple[str, str]:
        """Load saved range from settings or fall back to last 30 days."""
        now = datetime.now()
        fallback_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        fallback_end = now.strftime("%Y-%m-%d")

        saved_start = self.settings_store.get(self.settings_key_start, fallback_start).strip()
        saved_end = self.settings_store.get(self.settings_key_end, fallback_end).strip()
        return saved_start or fallback_start, saved_end or fallback_end

    def _save_range(self, start_value: str, end_value: str) -> None:
        """Persist current range."""
        self.settings_store.set(self.settings_key_start, (start_value or "").strip())
        self.settings_store.set(self.settings_key_end, (end_value or "").strip())

    def _parse_input_datetime(self, value: str, is_end: bool) -> Optional[datetime]:
        """Parse date input with flexible formats."""
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
        """Filter items by date range and call on_apply."""
        start_dt = self._parse_input_datetime(self.start_input.text, is_end=False)
        end_dt = self._parse_input_datetime(self.end_input.text, is_end=True)

        if not start_dt or not end_dt:
            self.info_label.text = "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]."
            self.info_label.color = (1.0, 0.45, 0.45, 1)
            return

        if end_dt < start_dt:
            self.info_label.text = "End must be greater than or equal to Start."
            self.info_label.color = (1.0, 0.45, 0.45, 1)
            return

        self._save_range(self.start_input.text, self.end_input.text)

        start_str = start_dt.isoformat(timespec="seconds")
        end_str = end_dt.isoformat(timespec="seconds")

        filtered = [
            item for item in self.items
            if start_str <= (item.get(self.date_field) or "") <= end_str
        ]

        self.info_label.text = f"Filtered: {len(filtered)} of {len(self.items)} items in range."
        self.info_label.color = (0.75, 0.75, 0.75, 1)
        self.on_apply(filtered)
        self.dismiss()


class TimeframeOverlayPopup(Popup):
    """
    Popup for plotting all module curves from one selected time window.

    Curves are overlaid in one chart using thin, semi-transparent lines.
    Blue is used for left modules and red for right modules.
    """

    LEFT_COLOR = [0.2, 0.6, 1.0, 0.26]
    RIGHT_COLOR = [1.0, 0.25, 0.2, 0.26]
    INFO_COLOR = (0.8, 0.8, 0.8, 1)
    ERROR_COLOR = (1.0, 0.45, 0.45, 1)

    SETTINGS_KEY_START = "matching_overlay_start"
    SETTINGS_KEY_END = "matching_overlay_end"

    def __init__(self, repository: MatchingRepository, settings_store: DataToolsSettingsStore, **kwargs):
        super().__init__(**kwargs)
        self.repository = repository
        self.settings_store = settings_store
        self.title = "Timeframe Curve Overlay"
        self.size_hint = (0.86, 0.88)
        self.auto_dismiss = True
        self._plots: List[LinePlot] = []

        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        hint = Label(
            text="Date range format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        hint.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(hint)

        default_start, default_end = self._get_initial_range()

        controls = BoxLayout(size_hint_y=None, height=40, spacing=8)
        self.start_input = TextInput(text=default_start, multiline=False, size_hint_x=0.28)
        self.end_input = TextInput(text=default_end, multiline=False, size_hint_x=0.28)
        self.start_input.bind(on_text_validate=self._render_overlay)
        self.end_input.bind(on_text_validate=self._render_overlay)
        self.export_button = Button(text="Export PNG", size_hint_x=0.15)
        self.export_button.bind(on_release=lambda *_: self.export_overlay_plot())
        close_button = Button(text="Close", size_hint_x=0.15)
        close_button.bind(on_release=lambda *_: self.dismiss())

        controls.add_widget(Label(text="Start:", size_hint_x=0.07))
        controls.add_widget(self.start_input)
        controls.add_widget(Label(text="End:", size_hint_x=0.07))
        controls.add_widget(self.end_input)
        controls.add_widget(self.export_button)
        controls.add_widget(close_button)
        root.add_widget(controls)

        self.info_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=self.INFO_COLOR,
        )
        self.info_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        root.add_widget(self.info_label)

        self.graph = Graph(
            xlabel="Frequency (Hz)",
            ylabel="Level (dB SPL)",
            xlog=True,
            x_ticks_major=1,
            x_ticks_minor=10,
            y_ticks_major=10,
            x_grid=True,
            y_grid=True,
            x_grid_label=True,
            y_grid_label=True,
            xmin=10,
            xmax=20000,
            ymin=50,
            ymax=110,
            padding=5,
            border_color=[0.3, 0.3, 0.3, 1],
            label_options={"color": [0.7, 0.7, 0.7, 1], "bold": False},
            background_color=[0.1, 0.1, 0.1, 1],
            tick_color=[0.3, 0.3, 0.3, 1],
        )
        root.add_widget(self.graph)
        self.content = root

        Clock.schedule_once(lambda _dt: setattr(self.start_input, "focus", True), 0.05)
        Clock.schedule_once(self._render_overlay, 0.08)

    def _get_initial_range(self) -> Tuple[str, str]:
        """Load saved range from settings or fall back to the last 7 days."""
        now = datetime.now()
        fallback_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        fallback_end = now.strftime("%Y-%m-%d")

        saved_start = self.settings_store.get(self.SETTINGS_KEY_START, fallback_start).strip()
        saved_end = self.settings_store.get(self.SETTINGS_KEY_END, fallback_end).strip()
        return saved_start or fallback_start, saved_end or fallback_end

    def _save_range(self, start_value: str, end_value: str) -> None:
        """Persist current range so it is restored after app restart."""
        self.settings_store.set(self.SETTINGS_KEY_START, (start_value or "").strip())
        self.settings_store.set(self.SETTINGS_KEY_END, (end_value or "").strip())

    def _parse_input_datetime(self, value: str, is_end: bool) -> Optional[datetime]:
        """Parse one start/end input value in a user-friendly way."""
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

    def _clear_overlay(self) -> None:
        """Remove all currently rendered overlay plots."""
        for plot in self._plots:
            self.graph.remove_plot(plot)
        self._plots.clear()

    def _set_info_message(self, message: str, is_error: bool = False) -> None:
        """Set overlay feedback text and color, highlighting errors in red."""
        self.info_label.text = message
        self.info_label.color = self.ERROR_COLOR if is_error else self.INFO_COLOR

    def export_overlay_plot(self) -> None:
        """Export currently rendered overlay curves as PNG without opening a window."""
        if not self._plots:
            self._set_info_message("No plot to export. Render a valid overlay first.", is_error=True)
            return

        default_folder = self._get_export_folder()
        target_path = self._choose_png_export_target(default_folder)
        if not target_path:
            self._set_info_message("Export canceled.")
            return

        try:
            # Create matplotlib figure with light mode styling
            fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
            ax.set_xscale('log')
            ax.set_xlabel('Frequency (Hz)', fontsize=11, color='#000000')
            ax.set_ylabel('Level (dB SPL)', fontsize=11, color='#000000')
            ax.set_xlim(self.graph.xmin, self.graph.xmax)
            ax.set_ylim(self.graph.ymin, self.graph.ymax)
            ax.grid(True, which='both', alpha=0.3, color='#cccccc')
            ax.set_facecolor('#ffffff')
            fig.patch.set_facecolor('#ffffff')
            ax.tick_params(colors='#000000')
            for spine in ax.spines.values():
                spine.set_color('#000000')

            # Add title with timeframe
            start_text = self.start_input.text.strip()
            end_text = self.end_input.text.strip()
            fig.suptitle(f'Overlay Plot: {start_text} to {end_text}', fontsize=12, color='#000000', weight='bold')

            # Collect curves by side for averaging
            left_curves = []
            right_curves = []
            left_color = (0.2, 0.6, 1.0)
            right_color = (1.0, 0.25, 0.2)

            # Re-plot all curves using the same data and colors
            for plot in self._plots:
                # Extract x,y from plot points: [(x1,y1), (x2,y2), ...]
                if plot.points:
                    points = list(plot.points)
                    freqs = [p[0] for p in points]
                    levels = [p[1] for p in points]
                    # Convert Kivy RGBA to matplotlib RGB
                    color = plot.color
                    mpl_color = (color[0], color[1], color[2])
                    alpha = color[3] if len(color) > 3 else 1.0
                    ax.plot(freqs, levels, color=mpl_color, alpha=alpha, linewidth=0.8)
                    
                    # Classify by side for averaging
                    if abs(mpl_color[0] - left_color[0]) < 0.1 and abs(mpl_color[1] - left_color[1]) < 0.1 and abs(mpl_color[2] - left_color[2]) < 0.1:
                        left_curves.append((freqs, levels))
                    else:
                        right_curves.append((freqs, levels))

            # Calculate and plot median curves (dotted lines for robust outlier handling)
            if left_curves:
                avg_freqs = left_curves[0][0]  # All curves should have same freqs
                median_levels = [statistics.median(curve[1][i] for curve in left_curves) for i in range(len(avg_freqs))]
                ax.plot(avg_freqs, median_levels, color=left_color, linewidth=2.5, linestyle=':', label='Left median', zorder=10)

            if right_curves:
                avg_freqs = right_curves[0][0]  # All curves should have same freqs
                median_levels = [statistics.median(curve[1][i] for curve in right_curves) for i in range(len(avg_freqs))]
                ax.plot(avg_freqs, median_levels, color=right_color, linewidth=2.5, linestyle=':', label='Right median', zorder=10)

            # Create legend
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], color=left_color, lw=2, label='Left module'),
                Line2D([0], [0], color=right_color, lw=2, label='Right module'),
            ]
            if left_curves:
                legend_elements.append(Line2D([0], [0], color=left_color, lw=2.5, linestyle=':', label='Left median'))
            if right_curves:
                legend_elements.append(Line2D([0], [0], color=right_color, lw=2.5, linestyle=':', label='Right median'))
            
            ax.legend(handles=legend_elements, loc='best', fontsize=10, framealpha=0.95, edgecolor='#000000')
            
            plt.tight_layout()
            plt.savefig(target_path, facecolor='#ffffff', edgecolor='none', dpi=100)
            plt.close(fig)

            self._set_info_message(
                f"Exported overlay plot ({len(self._plots)} curves) to {Path(target_path).name}",
                is_error=False
            )
        except Exception as e:
            self._set_info_message(f"Export failed: {str(e)}", is_error=True)

    @staticmethod
    def _get_export_folder() -> str:
        """Get default export folder from DataTools settings or home directory."""
        from app.settings_store import DataToolsSettingsStore
        store = DataToolsSettingsStore(Path(__file__).parent.parent)
        return store.get("default_export_folder", str(Path.home()))

    @staticmethod
    def _choose_png_export_target(default_folder: str) -> str:
        """Open a native save dialog for PNG overlay export."""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.asksaveasfilename(
            initialdir=default_folder or None,
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile="overlay_plot.png",
        )
        root.destroy()
        return selected or ""

    def _render_overlay(self, *_args) -> None:
        """Render all curves for the selected period in one chart."""
        # Validation is performed before any database query so operators
        # get immediate feedback and DB load stays minimal on invalid input.
        start_dt = self._parse_input_datetime(self.start_input.text, is_end=False)
        end_dt = self._parse_input_datetime(self.end_input.text, is_end=True)
        if not start_dt or not end_dt:
            self._set_info_message("Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS].", is_error=True)
            return

        if end_dt < start_dt:
            self._set_info_message("End must be greater than or equal to Start.", is_error=True)
            return

        self._save_range(self.start_input.text, self.end_input.text)

        # The DB stores timestamps with microseconds; use an exclusive upper bound
        # so entries within the selected final second are not accidentally dropped.
        end_exclusive = end_dt + timedelta(seconds=1)
        freqs, curve_rows = self.repository.get_curves_in_period(
            start_dt.isoformat(timespec="seconds"),
            end_exclusive.isoformat(timespec="seconds"),
        )
        self._clear_overlay()

        if not freqs or not curve_rows:
            self._set_info_message("No curves found in the selected period.", is_error=True)
            return

        y_values: List[float] = []
        left_count = 0
        right_count = 0

        for row in curve_rows:
            levels = row["levels"]
            if not levels:
                continue

            side = row["side"]
            color = self.LEFT_COLOR if side == "left" else self.RIGHT_COLOR
            if side == "left":
                left_count += 1
            else:
                right_count += 1

            plot = LinePlot(color=color, line_width=0.9)
            plot.points = list(zip(freqs, levels))
            self.graph.add_plot(plot)
            self._plots.append(plot)
            y_values.extend(levels)

        if not y_values or not self._plots:
            self._set_info_message("No plottable curve data found in the selected period.", is_error=True)
            return

        self.graph.xmin = max(min(freqs), 10)
        self.graph.xmax = max(freqs)

        raw_min = min(y_values)
        raw_max = max(y_values)
        value_range = max(raw_max - raw_min, 0.5)
        padding = max(0.8, value_range * 0.12)

        minimum = raw_min - padding
        maximum = raw_max + padding
        min_span = 6.0
        if (maximum - minimum) < min_span:
            center = (raw_min + raw_max) / 2
            half_span = min_span / 2
            minimum = center - half_span
            maximum = center + half_span

        self.graph.ymin = math.floor(minimum)
        self.graph.ymax = math.ceil(maximum)
        y_range = self.graph.ymax - self.graph.ymin
        if y_range <= 12:
            self.graph.y_ticks_major = 1
        elif y_range <= 24:
            self.graph.y_ticks_major = 2
        else:
            self.graph.y_ticks_major = 5

        self._set_info_message(
            f"Rendered {len(self._plots)} curves in one plot "
            f"(left: {left_count}, right: {right_count})."
        )


class MatchingViewerRoot(BoxLayout):
    """Main read-only Matching viewer layout."""

    STATUS_INFO_COLOR = (0.75, 0.75, 0.75, 1)
    STATUS_SUCCESS_COLOR = (0.6, 0.9, 0.6, 1)
    STATUS_ERROR_COLOR = (1.0, 0.45, 0.45, 1)
    RMSE_INFO_COLOR = (0.78, 0.78, 0.78, 1)

    def __init__(self, settings_store: DataToolsSettingsStore, on_back=None, **kwargs):
        super().__init__(orientation="vertical", spacing=10, padding=12, **kwargs)
        # Settings drive DB path resolution and export defaults.
        self.settings_store = settings_store
        self.on_back = on_back
        self.repository = MatchingRepository(settings_store.get("matching_db_path", ""))
        self.current_mode = "pool"
        self.mode_buttons: Dict[str, Button] = {}
        self.pool_items: List[Dict[str, str]] = []
        self.matched_items: List[Dict[str, str]] = []
        self.paired_items: List[Dict[str, str]] = []
        self.assembled_items: List[Dict[str, str]] = []
        self.pool_items_filtered: List[Dict[str, str]] = []
        self.matched_items_filtered: List[Dict[str, str]] = []
        self.paired_items_filtered: List[Dict[str, str]] = []
        self.assembled_items_filtered: List[Dict[str, str]] = []
        self.current_plot_selection = ""
        self.current_rmse_value: Optional[float] = None
        self.tooltip_manager = DelayedTooltipManager(delay_seconds=1.2)

        header = BoxLayout(size_hint_y=None, height=42, spacing=8)
        title = Label(
            text="Matching Viewer",
            font_size="26sp",
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        header.add_widget(title)

        if self.on_back is not None:
            back_button = Button(text="Back to Home", size_hint_x=None, width=150)
            back_button.bind(on_release=lambda *_: self.on_back())
            header.add_widget(back_button)

        self.add_widget(header)

        self.db_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        self.db_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.add_widget(self.db_label)

        toolbar = BoxLayout(size_hint_y=None, height=42, spacing=8)
        refresh_button = Button(text="Refresh")
        refresh_button.bind(on_release=lambda *_: self.refresh())
        export_button = Button(text="Export CSV")
        export_button.bind(on_release=lambda *_: self.export_csv_snapshot())
        overlay_button = Button(text="Timeframe Overlay")
        overlay_button.bind(on_release=lambda *_: self.open_timeframe_overlay())
        toolbar.add_widget(refresh_button)
        toolbar.add_widget(export_button)
        toolbar.add_widget(overlay_button)
        self.add_widget(toolbar)

        self.tooltip_manager.register(refresh_button, "Reload lists and summary from the current matching database.")
        self.tooltip_manager.register(export_button, "Export current read-only driver rows to a CSV snapshot.")
        self.tooltip_manager.register(overlay_button, "Open timeframe overlay and render many curves in one plot.")

        self.summary_row = GridLayout(cols=4, spacing=8, size_hint_y=None, height=56)
        self.pool_label = Label(text="Pool: 0")
        self.matched_label = Label(text="Matched: 0")
        self.paired_label = Label(text="Paired: 0")
        self.assembled_label = Label(text="Assembled: 0")
        self.summary_row.add_widget(self.pool_label)
        self.summary_row.add_widget(self.matched_label)
        self.summary_row.add_widget(self.paired_label)
        self.summary_row.add_widget(self.assembled_label)
        self.add_widget(self.summary_row)

        content = BoxLayout(spacing=10)

        left_panel = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.42)

        mode_bar = BoxLayout(size_hint_y=None, height=38, spacing=6)
        self.mode_hint_label = Label(
            text="Showing: Pool",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        self.mode_hint_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))

        for mode_key, mode_text in [("pool", "Pool"), ("matched", "Matched"), ("paired", "Paired"), ("assembled", "Assembled")]:
            mode_button = Button(text=mode_text)
            mode_button.bind(on_release=lambda _button, key=mode_key: self._set_mode(key))
            self.mode_buttons[mode_key] = mode_button
            mode_bar.add_widget(mode_button)

        self.tooltip_manager.register(self.mode_buttons["pool"], "Show unmatched single modules awaiting matching.")
        self.tooltip_manager.register(self.mode_buttons["matched"], "Show left/right pairs suggested by the matching tool but not yet confirmed for installation.")
        self.tooltip_manager.register(self.mode_buttons["paired"], "Show confirmed pairs sorted for installation: worker scanned both modules, marking them as a set.")
        self.tooltip_manager.register(self.mode_buttons["assembled"], "Show assembled systems: each entry links a system serial to two installed driver modules.")

        left_panel.add_widget(mode_bar)

        # Filter button (visible for all modes: pool, matched, paired).
        self.paired_filter_bar = BoxLayout(size_hint_y=None, height=36, spacing=6)
        filter_button = Button(text="Filter")
        filter_button.bind(on_release=self._open_paired_timeframe_filter)
        clear_button = Button(text="Clear Filter")
        clear_button.bind(on_release=self._clear_paired_filter)
        self.paired_filter_bar.add_widget(filter_button)
        self.paired_filter_bar.add_widget(clear_button)
        self.paired_filter_bar.size_hint_y = None
        self.paired_filter_bar.height = 36
        left_panel.add_widget(self.paired_filter_bar)

        self.tooltip_manager.register(
            filter_button,
            "Filter list by date.\nPool/Matched: by measurement date.\nPaired: by pairing date.",
        )
        self.tooltip_manager.register(clear_button, "Remove active date filter.")

        self.selection_list = ListSection("Selection", show_title=False)
        left_panel.add_widget(self.selection_list)

        scan_bar = BoxLayout(size_hint_y=None, height=42, spacing=8)
        scan_label = Label(
            text="Serial:",
            size_hint_x=None,
            width=62,
            halign="left",
            valign="middle",
        )
        scan_label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        scan_bar.add_widget(scan_label)

        self.serial_input = TextInput(
            hint_text="Scan or enter module serial",
            multiline=False,
            size_hint_x=1,
        )
        self.serial_input.bind(on_text_validate=self._show_serial_lookup)
        scan_bar.add_widget(self.serial_input)
        self.tooltip_manager.register(self.serial_input, "Scan or type one serial and press Enter to render it.")
        left_panel.add_widget(scan_bar)

        left_panel.add_widget(self.mode_hint_label)

        content.add_widget(left_panel)

        detail_panel = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.58)
        self.plot_selection_label = Label(
            text="",
            size_hint_y=None,
            height=30,
            halign="center",
            valign="middle",
            color=(0.86, 0.86, 0.86, 1),
            shorten=False,
        )
        # Bind only width, not height, so long text is not vertically clipped.
        self.plot_selection_label.bind(
            size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None))
        )
        detail_panel.add_widget(self.plot_selection_label)

        self.chart = CurveChart(self.repository)
        detail_panel.add_widget(self.chart)
        content.add_widget(detail_panel)

        self.add_widget(content)

        self.status_line = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=self.STATUS_INFO_COLOR,
        )
        self.status_line.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        self.add_widget(self.status_line)

        self.refresh()
        Clock.schedule_once(lambda _dt: setattr(self.serial_input, "focus", True), 0.05)

    def _set_status_message(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        """Set status text and use red color for errors consistently."""
        self.status_line.text = message
        if is_error:
            self.status_line.color = self.STATUS_ERROR_COLOR
            return
        if is_success:
            self.status_line.color = self.STATUS_SUCCESS_COLOR
            return
        self.status_line.color = self.STATUS_INFO_COLOR

    def refresh(self) -> None:
        """Reload current data from the configured matcher database."""
        # Reset visual state before reload to avoid stale chart/selection remnants
        # when DB access fails or returns an empty set.
        self.chart.clear()
        self._set_plot_selection_text("")
        self._set_rmse_text(None)

        db_path = self.repository.db_path
        self.db_label.text = f"Database: {db_path}" if db_path else "Database: not configured"

        if not self.repository.is_configured():
            self._set_empty_state("Matching database path is not configured in DataTools settings.")
            return

        if not self.repository.exists():
            self._set_empty_state("Configured Matching database file does not exist.")
            return

        try:
            summary = self.repository.get_summary()
            self.pool_label.text = f"Pool: {summary['pool']}"
            self.matched_label.text = f"Matched: {summary['matched']}"
            self.paired_label.text = f"Paired: {summary['paired']}"
            self.assembled_label.text = f"Assembled: {summary['assembled']}"

            self.pool_items = self.repository.get_pool_items()
            self.matched_items = self.repository.get_pair_items("matched")
            self.paired_items = self.repository.get_pair_items("paired")
            self.assembled_items = self.repository.get_assembled_items()
            self.pool_items_filtered = []
            self.matched_items_filtered = []
            self.paired_items_filtered = []
            self.assembled_items_filtered = []
            self._set_mode(self.current_mode)
            self._set_status_message("Matching data loaded in read-only mode.")
        except (sqlite3.DatabaseError, OSError, ValueError) as exc:
            self._set_empty_state(f"Could not read matching database: {exc}")

    def _set_empty_state(self, message: str) -> None:
        """Show an empty viewer state with status feedback."""
        self.pool_label.text = "Pool: -"
        self.matched_label.text = "Matched: -"
        self.paired_label.text = "Paired: -"
        self.assembled_label.text = "Assembled: -"
        self.pool_items = []
        self.matched_items = []
        self.paired_items = []
        self.assembled_items = []
        self.selection_list.set_items([], lambda _item: None)
        self._set_rmse_text(None)
        self._set_status_message(message, is_error=True)

    def _set_mode(self, mode: str) -> None:
        """Switch between pool, matched, and paired list views."""
        self.current_mode = mode

        for key, button in self.mode_buttons.items():
            if key == mode:
                button.background_normal = ""
                button.background_color = (0.16, 0.46, 0.74, 1)
            else:
                button.background_normal = ""
                button.background_color = (0.38, 0.38, 0.38, 1)

        # All modes now support filtering. Show filter buttons always.
        self.paired_filter_bar.opacity = 1
        self.paired_filter_bar.disabled = False

        if mode == "pool":
            self.selection_list.set_items(
                self.pool_items_filtered if self.pool_items_filtered else self.pool_items,
                self._select_pool_item,
            )
            self.mode_hint_label.text = "Showing: Pool (single modules)"
        elif mode == "matched":
            self.selection_list.set_items(
                self.matched_items_filtered if self.matched_items_filtered else self.matched_items,
                self._select_matched_pair,
            )
            self.mode_hint_label.text = "Showing: Matched pairs"
        elif mode == "paired":
            self.selection_list.set_items(
                self.paired_items_filtered if self.paired_items_filtered else self.paired_items,
                self._select_paired_pair,
            )
            self.mode_hint_label.text = "Showing: Paired sets"
        else:  # assembled
            self.selection_list.set_items(
                self.assembled_items_filtered if self.assembled_items_filtered else self.assembled_items,
                self._select_assembled_item,
            )
            self.mode_hint_label.text = "Showing: Assembled systems"

    def _show_serial_lookup(self, *_args) -> None:
        """Resolve one serial and render it alone or with its partner."""
        if not self.repository.exists():
            self._set_status_message("Matching database is not available.", is_error=True)
            return

        requested_serial = self.serial_input.text.strip().upper()
        if not requested_serial:
            self._set_status_message("Enter or scan a module serial first.", is_error=True)
            return

        driver = self.repository.lookup_driver(requested_serial)
        if not driver:
            self._set_status_message(
                f"Serial {requested_serial} was not found in the matching database.",
                is_error=True,
            )
            self.chart.clear()
            self._set_plot_selection_text(f"Not found: {requested_serial}")
            self._set_rmse_text(None)
            return

        status = driver["status"]
        partner = driver["partner"]
        serial = driver["serial"]
        side = driver["side"]

        if status == "unmatched":
            self._set_mode("pool")
            self._select_pool_item({
                "serial": serial,
                "side": side,
                "label": f"{side.title()}: {serial}",
            })
            self.serial_input.text = ""
        elif status == "matched" and partner:
            self._set_mode("matched")
            self._select_matched_pair({
                "left_serial": serial if side == "left" else partner,
                "right_serial": partner if side == "left" else serial,
                "label": "",
            })
            self.serial_input.text = ""
        elif status == "paired" and partner:
            self._set_mode("paired")
            self._select_paired_pair({
                "left_serial": serial if side == "left" else partner,
                "right_serial": partner if side == "left" else serial,
                "label": "",
            })
            self.serial_input.text = ""
        else:
            self._set_status_message(
                f"Serial {serial} has no renderable partner information.",
                is_error=True,
            )
            self.chart.clear()
            self._set_plot_selection_text(f"{serial} ({status})")
            self._set_rmse_text(None)

        self.serial_input.focus = True

    def _select_pool_item(self, item: Dict[str, str]) -> None:
        """Render a single pool driver curve."""
        if self.chart.show_driver(item["serial"], item["side"]):
            self._set_plot_selection_text(f"Pool: {item['serial']} ({item['side']})")
            self._set_rmse_text(None)
            self._set_status_message(f"Rendered pool curve for {item['serial']}.", is_success=True)
            return

        self._set_plot_selection_text(f"Pool: {item['serial']} ({item['side']})")
        self._set_rmse_text(None)
        self._set_status_message(f"Curve data for {item['serial']} is unavailable.", is_error=True)

    def _select_matched_pair(self, item: Dict[str, str]) -> None:
        """Render one matched left/right pair."""
        left_serial = item["left_serial"]
        right_serial = item["right_serial"]
        if right_serial and self.chart.show_pair(left_serial, right_serial):
            self._set_plot_selection_text(f"Matched: {left_serial} <-> {right_serial}")
            self._update_pair_rmse(left_serial, right_serial)
            self._set_status_message(
                f"Rendered matched pair curves: {left_serial} <-> {right_serial}.",
                is_success=True,
            )
            return

        self._set_plot_selection_text(f"Matched: {left_serial} <-> {right_serial or '-'}")
        self._set_rmse_text(None)
        self._set_status_message("Curve data for this matched pair is unavailable.", is_error=True)

    def _select_paired_pair(self, item: Dict[str, str]) -> None:
        """Render one confirmed paired left/right pair."""
        left_serial = item["left_serial"]
        right_serial = item["right_serial"]
        if right_serial and self.chart.show_pair(left_serial, right_serial):
            self._set_plot_selection_text(f"Paired: {left_serial} <-> {right_serial}")
            self._update_pair_rmse(left_serial, right_serial)
            self._set_status_message(
                f"Rendered paired set curves: {left_serial} <-> {right_serial}.",
                is_success=True,
            )
            return

        self._set_plot_selection_text(f"Paired: {left_serial} <-> {right_serial or '-'}")
        self._set_rmse_text(None)
        self._set_status_message("Curve data for this paired set is unavailable.", is_error=True)

    def _set_plot_selection_text(self, text: str) -> None:
        """Update centered selection text shown above the chart."""
        self.current_plot_selection = text or ""
        self._refresh_plot_header()

    def _set_rmse_text(self, rmse_value: Optional[float]) -> None:
        """Update RMSE value shown in the same header line as selection text."""
        self.current_rmse_value = rmse_value
        self._refresh_plot_header()

    def _refresh_plot_header(self) -> None:
        """Render one compact header line: selection + RMSE (only when data is shown)."""
        selection = self.current_plot_selection.strip()
        if not selection:
            # No curve selected – show nothing.
            self.plot_selection_label.text = ""
            return
        if self.current_rmse_value is not None:
            self.plot_selection_label.text = (
                f"{selection} | RMSE: {self.current_rmse_value:.3f} dB"
            )
        else:
            self.plot_selection_label.text = selection

    def _update_pair_rmse(self, left_serial: str, right_serial: str) -> None:
        """Compute and show RMSE between left/right curves for one pair."""
        _freq_l, levels_l = self.repository.get_driver_levels(left_serial)
        _freq_r, levels_r = self.repository.get_driver_levels(right_serial)
        if not levels_l or not levels_r:
            self._set_rmse_text(None)
            return

        sample_count = min(len(levels_l), len(levels_r))
        if sample_count <= 0:
            self._set_rmse_text(None)
            return

        squared_sum = 0.0
        for idx in range(sample_count):
            delta = levels_l[idx] - levels_r[idx]
            squared_sum += delta * delta

        rmse = math.sqrt(squared_sum / sample_count)
        self._set_rmse_text(rmse)

    def _open_paired_timeframe_filter(self, *_args) -> None:
        """Open timeframe filter popup for the current mode."""
        if self.current_mode == "pool":
            ListTimeframeFilterPopup(
                title="Filter Pool by Measurement Date",
                settings_store=self.settings_store,
                items=self.pool_items,
                date_field="loaded_at",
                on_apply=self._apply_pool_filter,
            ).open()
        elif self.current_mode == "matched":
            ListTimeframeFilterPopup(
                title="Filter Matched by Measurement Date",
                settings_store=self.settings_store,
                items=self.matched_items,
                date_field="loaded_at",
                on_apply=self._apply_matched_filter,
            ).open()
        elif self.current_mode == "paired":
            ListTimeframeFilterPopup(
                title="Filter Paired by Pairing Date",
                settings_store=self.settings_store,
                items=self.paired_items,
                date_field="matched_at",
                on_apply=self._apply_paired_filter,
            ).open()
        else:  # assembled
            ListTimeframeFilterPopup(
                title="Filter Assembled by Assembly Date",
                settings_store=self.settings_store,
                items=self.assembled_items,
                date_field="built_at",
                on_apply=self._apply_assembled_filter,
            ).open()

    def _apply_pool_filter(self, filtered_items: List[Dict[str, str]]) -> None:
        """Apply filtered pool list and refresh view."""
        self.pool_items_filtered = filtered_items
        if self.current_mode == "pool":
            self.selection_list.set_items(
                self.pool_items_filtered if self.pool_items_filtered else self.pool_items,
                self._select_pool_item,
            )

    def _apply_matched_filter(self, filtered_items: List[Dict[str, str]]) -> None:
        """Apply filtered matched list and refresh view."""
        self.matched_items_filtered = filtered_items
        if self.current_mode == "matched":
            self.selection_list.set_items(
                self.matched_items_filtered if self.matched_items_filtered else self.matched_items,
                self._select_matched_pair,
            )

    def _apply_paired_filter(self, filtered_items: List[Dict[str, str]]) -> None:
        """Apply filtered paired list and refresh view."""
        self.paired_items_filtered = filtered_items
        if self.current_mode == "paired":
            self.selection_list.set_items(
                self.paired_items_filtered if self.paired_items_filtered else self.paired_items,
                self._select_paired_pair,
            )

    def _select_assembled_item(self, item: Dict[str, str]) -> None:
        """Render the two module curves for one assembled system."""
        system_serial = item["system_serial"]
        module_1 = item["module_1"]
        module_2 = item["module_2"]

        # Determine sides from module serials (IA prefix = left, IB prefix = right).
        if module_1.upper().startswith("IA"):
            left_serial, right_serial = module_1, module_2
        elif module_1.upper().startswith("IB"):
            left_serial, right_serial = module_2, module_1
        else:
            left_serial, right_serial = module_1, module_2

        if right_serial and self.chart.show_pair(left_serial, right_serial):
            self._set_plot_selection_text(f"Assembled: {system_serial}  ({left_serial} / {right_serial})")
            self._update_pair_rmse(left_serial, right_serial)
            self._set_status_message(
                f"Rendered assembled system {system_serial}: {left_serial} / {right_serial}.",
                is_success=True,
            )
            return

        self._set_plot_selection_text(f"Assembled: {system_serial}  ({module_1} / {module_2})")
        self._set_rmse_text(None)
        self._set_status_message("Curve data for this assembled system is unavailable.", is_error=True)

    def _apply_assembled_filter(self, filtered_items: List[Dict[str, str]]) -> None:
        """Apply filtered assembled list and refresh view."""
        self.assembled_items_filtered = filtered_items
        if self.current_mode == "assembled":
            self.selection_list.set_items(
                self.assembled_items_filtered if self.assembled_items_filtered else self.assembled_items,
                self._select_assembled_item,
            )

    def _clear_paired_filter(self, *_args) -> None:
        """Clear active filter for current mode and show all."""
        if self.current_mode == "pool":
            self.pool_items_filtered = []
            self.selection_list.set_items(self.pool_items, self._select_pool_item)
        elif self.current_mode == "matched":
            self.matched_items_filtered = []
            self.selection_list.set_items(self.matched_items, self._select_matched_pair)
        elif self.current_mode == "paired":
            self.paired_items_filtered = []
            self.selection_list.set_items(self.paired_items, self._select_paired_pair)
        else:  # assembled
            self.assembled_items_filtered = []
            self.selection_list.set_items(self.assembled_items, self._select_assembled_item)

    def export_csv_snapshot(self) -> None:
        """Export drivers and assembled systems to one CSV file with two sections."""
        if not self.repository.exists():
            self._set_status_message("Export failed: matching database is not available.", is_error=True)
            return

        default_folder = self.settings_store.get("default_export_folder", "")
        target_path = self._choose_export_target(default_folder)
        if not target_path:
            self._set_status_message("Export canceled.")
            return

        driver_rows = self.repository.get_all_drivers()
        assembled_rows = self.repository.get_assembled_items()

        with Path(target_path).open("w", newline="", encoding="utf-8") as handle:
            # Section 1: Drivers
            handle.write("# DRIVERS\n")
            driver_writer = csv.DictWriter(
                handle,
                fieldnames=["serial", "side", "status", "partner", "loaded_at", "matched_at"],
                extrasaction="ignore",
            )
            driver_writer.writeheader()
            driver_writer.writerows(driver_rows)

            # Section 2: Assembled systems
            handle.write("\n# ASSEMBLED\n")
            assembled_writer = csv.DictWriter(
                handle,
                fieldnames=["system_serial", "module_1", "module_2", "built_at"],
                extrasaction="ignore",
            )
            assembled_writer.writeheader()
            assembled_writer.writerows(assembled_rows)

        total = len(driver_rows) + len(assembled_rows)
        self._set_status_message(f"Exported {len(driver_rows)} drivers + {len(assembled_rows)} systems to {target_path}", is_success=True)
        ExportInfoPopup("Export Complete", f"Exported {len(driver_rows)} drivers and {len(assembled_rows)} assembled systems to:\n{target_path}").open()

    def open_timeframe_overlay(self) -> None:
        """Open popup for rendering all curves in one selected period."""
        if not self.repository.exists():
            self._set_status_message("Overlay unavailable: matching database is not available.", is_error=True)
            return

        TimeframeOverlayPopup(repository=self.repository, settings_store=self.settings_store).open()

    @staticmethod
    def _choose_export_target(default_folder: str) -> str:
        """Open a native save dialog for the read-only CSV export."""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.asksaveasfilename(
            initialdir=default_folder or None,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="matching_snapshot.csv",
        )
        root.destroy()
        return selected or ""


class MatchingViewerApp(App):
    """Standalone read-only Matching viewer window inside the DataTools release."""

    title = "DataTools Matching Viewer"

    def build(self):
        """Build the dedicated Matching viewer UI."""
        datatools_root = Path(__file__).resolve().parent.parent
        settings_store = DataToolsSettingsStore(datatools_root)

        Window.clearcolor = (0.08, 0.08, 0.1, 1)
        Window.size = (1450, 860)
        Window.minimum_width = 1200
        Window.minimum_height = 760
        return MatchingViewerRoot(settings_store=settings_store)