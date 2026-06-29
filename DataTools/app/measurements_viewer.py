"""
DataTools Measurements Viewer
==============================

Provides the Measurements feature: browse a configurable root folder
(e.g. Sub8PRO), select a measurement category (EOL / GoldenSample / Reference)
and one or more result sub-folders, then inspect the imported data.

Architecture
------------
- MeasurementSelectionPopup  : folder/category picker shown on entry
- MeasurementsViewerRoot     : main view, receives the resolved selection
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy_garden.graph import Graph, LinePlot

try:
    from kivy_garden.graph import PointPlot as _PointPlot
    _HAVE_POINT_PLOT = True
except ImportError:
    _HAVE_POINT_PLOT = False

from app.settings_store import DataToolsSettingsStore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_CATEGORIES = ["EOL", "GoldenSample", "Reference"]

CATEGORY_COLORS: Dict[str, tuple] = {
    "EOL":          (0.25, 0.50, 0.30, 1),   # green-ish
    "GoldenSample": (0.45, 0.35, 0.60, 1),   # purple-ish
    "Reference":    (0.55, 0.38, 0.18, 1),   # amber-ish
}

CATEGORY_ACTIVE_COLORS: Dict[str, tuple] = {
    "EOL":          (0.35, 0.70, 0.40, 1),
    "GoldenSample": (0.60, 0.50, 0.80, 1),
    "Reference":    (0.75, 0.55, 0.25, 1),
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _discover_categories(root: Path) -> List[str]:
    """Return which KNOWN_CATEGORIES actually exist under root/Measurements/."""
    measurements_root = root / "Measurements"
    if not measurements_root.is_dir():
        return []
    return [c for c in KNOWN_CATEGORIES if (measurements_root / c).is_dir()]


def _discover_result_folders(root: Path, category: str) -> List[str]:
    """
    Return sorted list of leaf folder names inside root/Measurements/<category>.
    Traverses one year-level if present (e.g. 2026/6_22 → "2026 / 6_22").
    """
    base = root / "Measurements" / category
    if not base.is_dir():
        return []

    folders: List[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        # If the child looks like a year (4-digit), descend one level.
        if child.name.isdigit() and len(child.name) == 4:
            for sub in sorted(child.iterdir()):
                if sub.is_dir():
                    folders.append(f"{child.name} / {sub.name}")
        else:
            folders.append(child.name)
    return folders


def _resolve_folder_path(root: Path, category: str, folder_label: str) -> Path:
    """Turn a folder label (possibly 'YYYY / name') back into an absolute Path."""
    base = root / "Measurements" / category
    if " / " in folder_label:
        year, sub = folder_label.split(" / ", 1)
        return base / year / sub
    return base / folder_label


# ---------------------------------------------------------------------------
# Measurement data model
# ---------------------------------------------------------------------------

# Filename suffixes that are not measurement data (excluded from viewer)
_EXCLUDED_TYPES: Set[str] = {"Waveform", "Report", "RMS_Level_Sub_pre_calibration"}

# Fixed display order for measurement type selector
_TYPE_ORDER = ["RMS_Level", "Phase", "THD", "RnB_CF", "RnB_PR"]

# Type configuration: display_label, ymin, ymax, y_tick_major, ylabel
_TYPE_CONFIG: Dict[str, Tuple[str, float, float, float, str]] = {
    "RMS_Level":     ("RMS Level",      70,   130,  5,  "dBSPL"),
    "Phase":         ("Phase",         -180,  180,  45, "degrees"),
    "THD":           ("THD",             0,    15,   2, "%"),
    "RnB_CF":        ("RnB Crest",       0,    20,   5, "dB"),
    "RnB_PR":        ("RnB Peak Ratio", -80,    0,  10, "dB"),
}

# Color palette for individual runs per serial (RGB, alpha added at render time)
_SERIAL_PALETTE = [
    (0.25, 0.60, 1.00),
    (1.00, 0.50, 0.15),
    (0.25, 0.82, 0.40),
    (0.90, 0.28, 0.75),
    (0.15, 0.85, 0.88),
    (0.75, 0.75, 0.20),
    (0.80, 0.40, 0.20),
    (0.55, 0.55, 1.00),
]

_TIMESTAMP_RE = re.compile(r'^(.+?)_(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})_(.+)$')
_CH_SUFFIX_RE = re.compile(r'^(.+?)_(Ch_[12])$')


@dataclass
class MeasurementFile:
    """Parsed contents of one AP measurement CSV file."""
    serial: str
    timestamp: str
    meas_type: str
    channel: Optional[str]          # None = mono; "Ch_1" / "Ch_2" = stereo input
    col_names: List[str]            # Sub-column labels (e.g. Left-Left, Right-Left)
    frequencies: List[np.ndarray]   # One array per column pair
    levels: List[np.ndarray]        # One array per column pair
    file_path: Path


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class MeasurementLoader:
    """Scans folder(s) and parses all AP measurement CSV files."""

    @staticmethod
    def load_folders(folders: List[Path]) -> List[MeasurementFile]:
        """Return all parseable MeasurementFile objects from the given folders."""
        runs: List[MeasurementFile] = []
        for folder in folders:
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.csv")):
                result = MeasurementLoader._parse_file(path)
                if result is not None:
                    runs.append(result)
        return runs

    @staticmethod
    def _parse_filename(stem: str) -> Optional[Tuple[str, str, str, Optional[str]]]:
        """Extract (serial, timestamp, meas_type, channel) from a filename stem."""
        m = _TIMESTAMP_RE.match(stem)
        if not m:
            return None
        serial, timestamp, type_and_ch = m.group(1), m.group(2), m.group(3)
        ch_m = _CH_SUFFIX_RE.match(type_and_ch)
        if ch_m:
            meas_type, channel = ch_m.group(1), ch_m.group(2)
        else:
            meas_type, channel = type_and_ch, None
        if meas_type in _EXCLUDED_TYPES:
            return None
        return serial, timestamp, meas_type, channel

    @staticmethod
    def _parse_file(path: Path) -> Optional[MeasurementFile]:
        """Parse one AP measurement CSV (4-header-row format)."""
        parsed = MeasurementLoader._parse_filename(path.stem)
        if parsed is None:
            return None
        serial, timestamp, meas_type, channel = parsed

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [ln.strip() for ln in f if ln.strip()]

            if len(lines) < 5:
                return None

            # Row index 1: sub-column names ("Left-Left,,Right-Left,")
            col_name_tokens = [t.strip() for t in lines[1].split(",") if t.strip()]

            # Row index 4+: numeric data
            data_rows: List[List[str]] = []
            for row in csv.reader(lines[4:]):
                stripped = [c.strip() for c in row]
                if any(stripped):
                    data_rows.append(stripped)

            if not data_rows:
                return None

            col_count = len(data_rows[0])
            if col_count == 0 or col_count % 2 != 0:
                return None

            num_pairs = col_count // 2
            frequencies: List[np.ndarray] = []
            levels: List[np.ndarray] = []

            for i in range(num_pairs):
                try:
                    xi, yi = i * 2, i * 2 + 1
                    raw_pairs: List[Tuple[float, float]] = []
                    for r in data_rows:
                        if len(r) > yi:
                            try:
                                raw_pairs.append((float(r[xi]), float(r[yi])))
                            except ValueError:
                                pass
                    if not raw_pairs:
                        continue
                    # Sort by frequency and remove duplicate frequencies
                    # (handles bidirectional AP sweeps: 20→20k→20 Hz)
                    raw_pairs.sort(key=lambda p: p[0])
                    seen: set = set()
                    unique_pairs = []
                    for f, lv in raw_pairs:
                        if f not in seen:
                            seen.add(f)
                            unique_pairs.append((f, lv))
                    freqs = np.array([p[0] for p in unique_pairs])
                    lvls  = np.array([p[1] for p in unique_pairs])
                    frequencies.append(freqs)
                    levels.append(lvls)
                except (ValueError, IndexError):
                    continue

            if not frequencies:
                return None

            col_names = (
                col_name_tokens[:num_pairs]
                if len(col_name_tokens) >= num_pairs
                else [f"Col {i + 1}" for i in range(num_pairs)]
            )

            return MeasurementFile(
                serial=serial,
                timestamp=timestamp,
                meas_type=meas_type,
                channel=channel,
                col_names=col_names,
                frequencies=frequencies,
                levels=levels,
                file_path=path,
            )
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nice_range(
    data_min: float, data_max: float, target_ticks: int = 6
) -> Tuple[float, float, float]:
    """Return (nice_min, nice_max, tick_step) for a readable y-axis scale."""
    if data_min == data_max:
        data_min -= 1.0
        data_max += 1.0
    span = data_max - data_min
    raw_step = span / target_ticks
    magnitude = 10 ** math.floor(math.log10(abs(raw_step) or 1.0))
    step = magnitude
    for nice in [1, 2, 5, 10]:
        step = nice * magnitude
        if step >= raw_step:
            break
    nice_min = math.floor(data_min / step) * step
    nice_max = math.ceil(data_max / step) * step
    if nice_max <= nice_min:
        nice_max = nice_min + step
    return nice_min, nice_max, step


# ---------------------------------------------------------------------------
# Chart widget
# ---------------------------------------------------------------------------

class MeasurementChart(BoxLayout):
    """
    Frequency response chart with type / input-channel / sub-channel selectors.

    Individual runs  → thin semi-transparent lines.
      Stereo: color per L/R channel (blue = Left, red = Right).
      Mono: color per serial from palette.
    Median of runs   → thicker line per sub-column, same L/R color (opaque).
    """

    _INDIVIDUAL_LINE_WIDTH = 1.2
    _INDIVIDUAL_ALPHA = 0.45
    _MEDIAN_ALPHA = 1.0
    _MEDIAN_LINE_WIDTH = 2.5
    # Stereo channel colors (RGB only; alpha added at render time)
    _LEFT_COLOR_RGB  = [0.25, 0.55, 1.0]
    _RIGHT_COLOR_RGB = [1.0, 0.32, 0.25]
    _MONO_MEDIAN_COLOR = [1.0, 0.92, 0.25, 1.0]   # amber fallback for mono
    _ACTIVE_COLOR   = (0.22, 0.48, 0.75, 1)
    _INACTIVE_COLOR = (0.15, 0.17, 0.20, 1)
    _DISPLAY_MODES  = ["raw", "median"]
    _DISPLAY_LABELS = {"raw": "Raw", "median": "Median"}

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=4, **kwargs)

        self._runs: List[MeasurementFile] = []
        self._serial_colors: Dict[str, List[float]] = {}
        self._available_types: List[str] = []
        self._available_channels: List[str] = []
        self._type_yscale: Dict[str, Tuple[float, float, float]] = {}  # mtype → (ymin, ymax, ytick)

        self._sel_type: Optional[str] = None
        self._sel_channel: Optional[str] = None
        self._sel_subcol_indices: Set[int] = set()  # index-based, preserved across channel changes

        self._display_mode: str = "raw"
        self._type_buttons:   Dict[str, ToggleButton] = {}
        self._ch_buttons:     Dict[str, ToggleButton] = {}
        self._mode_buttons:   Dict[str, ToggleButton] = {}
        self._subcol_buttons: Dict[int, ToggleButton] = {}   # col_idx → button
        self._subcol_names:   Dict[int, str] = {}            # col_idx → display name
        self._type_labels: Dict[str, str] = {}
        self._ch_labels:   Dict[str, str] = {}
        self._mode_labels: Dict[str, str] = {}

        self._individual_plots: List = []
        self._median_plots: List = []

        # Controls container (rebuilt on load_data)
        self._controls = BoxLayout(
            orientation="vertical", size_hint_y=None, height=0, spacing=4
        )
        self.add_widget(self._controls)

        # Graph
        self._graph = Graph(
            xlabel="Frequency (Hz)",
            ylabel="Level",
            xlog=True,
            x_ticks_major=1,
            x_ticks_minor=10,
            y_ticks_major=10,
            x_grid=True,
            y_grid=True,
            x_grid_label=True,
            y_grid_label=True,
            xmin=20,
            xmax=20000,
            ymin=70,
            ymax=130,
            padding=5,
            border_color=[0.3, 0.3, 0.3, 1],
            label_options={"color": [0.7, 0.7, 0.7, 1], "bold": False},
            background_color=[0.08, 0.08, 0.10, 1],
            tick_color=[0.3, 0.3, 0.3, 1],
        )
        self.add_widget(self._graph)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_data(self, runs: List[MeasurementFile]) -> None:
        """Load new measurement files, rebuild selectors, and render."""
        self._runs = runs
        self._sel_type = None
        self._sel_channel = None
        self._display_mode = "raw"

        serials = list(dict.fromkeys(r.serial for r in runs))
        self._serial_colors = {
            sn: list(_SERIAL_PALETTE[i % len(_SERIAL_PALETTE)]) + [self._INDIVIDUAL_ALPHA]
            for i, sn in enumerate(serials)
        }
        self._available_types = [
            t for t in _TYPE_ORDER if any(r.meas_type == t for r in runs)
        ]
        # Append any unknown types not in _TYPE_ORDER (future-proof)
        known = set(_TYPE_ORDER)
        for t in dict.fromkeys(r.meas_type for r in runs):
            if t not in known:
                self._available_types.append(t)
        self._available_channels = sorted({r.channel for r in runs if r.channel is not None})
        self._sel_subcol_indices = set()  # reset on fresh data load

        # Pre-compute y-scale per type from ALL data (all channels, inputs, sub-columns).
        # Stored once; stays fixed when switching channels / sub-columns / display mode.
        self._type_yscale = {}
        for mtype in self._available_types:
            all_lvls = [
                lvl
                for r in runs if r.meas_type == mtype
                for lvl in r.levels
            ]
            if all_lvls:
                stacked = np.concatenate(all_lvls)
                ymin, ymax, ytick = _nice_range(float(stacked.min()), float(stacked.max()))
                self._type_yscale[mtype] = (ymin, ymax, ytick)

        self._build_controls()
        self._activate_buttons(self._mode_buttons, self._mode_labels, self._display_mode)

        if self._available_types:
            self._select_type(self._available_types[0], redraw=False)
        if self._available_channels:
            self._select_channel(self._available_channels[0], redraw=False)

        self._update_subcol_row()
        self._redraw()

    # ------------------------------------------------------------------
    # Control building
    # ------------------------------------------------------------------

    def _build_controls(self) -> None:
        """Rebuild all selector rows from scratch."""
        self._controls.clear_widgets()
        self._type_buttons.clear()
        self._ch_buttons.clear()
        self._mode_buttons.clear()
        self._subcol_buttons.clear()
        self._type_labels.clear()
        self._ch_labels.clear()
        self._mode_labels.clear()
        self._subcol_names.clear()
        row_count = 0

        if self._available_types:
            row = self._make_label_row("Measurement:")
            for t in self._available_types:
                display = _TYPE_CONFIG[t][0] if t in _TYPE_CONFIG else t
                self._type_labels[t] = display
                btn = self._make_toggle(display, "mtype", lambda b, tp=t: self._select_type(tp))
                self._type_buttons[t] = btn
                row.add_widget(btn)
            self._controls.add_widget(row)
            row_count += 1

        # Display-mode row (Raw / Median)
        row = self._make_label_row("Display:")
        for mode in self._DISPLAY_MODES:
            label = self._DISPLAY_LABELS[mode]
            self._mode_labels[mode] = label
            btn = self._make_toggle(label, "display", lambda b, m=mode: self._select_mode(m))
            self._mode_buttons[mode] = btn
            row.add_widget(btn)
        self._controls.add_widget(row)
        row_count += 1

        if self._available_channels:
            row = self._make_label_row("Input:")
            for ch in self._available_channels:
                self._ch_labels[ch] = ch
                btn = self._make_toggle(ch, "channel", lambda b, c=ch: self._select_channel(c))
                self._ch_buttons[ch] = btn
                row.add_widget(btn)
            self._controls.add_widget(row)
            row_count += 1

        self._controls.height = row_count * 44

    def _update_subcol_row(self) -> None:
        """Discover sub-columns for current type/channel and rebuild the row."""
        # Remove old subcol row
        if hasattr(self, "_subcol_row") and self._subcol_row.parent:
            self._controls.remove_widget(self._subcol_row)
            self._controls.height = max(0, self._controls.height - 44)
        self._subcol_buttons.clear()
        self._subcol_names.clear()
        self._subcol_names.clear()

        filtered = self._filter_runs()
        subcols = filtered[0].col_names if filtered else []

        if len(subcols) <= 1:
            # Single or no column — trivially select index 0
            self._sel_subcol_indices = {0} if subcols else set()
            return

        # On first call (fresh load): select all indices
        if not self._sel_subcol_indices:
            self._sel_subcol_indices = set(range(len(subcols)))

        row = self._make_label_row("Channel:")
        for i, sc in enumerate(subcols):
            self._subcol_names[i] = sc
            is_active = i in self._sel_subcol_indices
            btn = ToggleButton(
                text=sc,
                font_size="13sp",
                bold=is_active,
                background_normal="",
                background_down="",
                background_color=self._ACTIVE_COLOR if is_active else self._INACTIVE_COLOR,
                color=(1, 1, 1, 1) if is_active else (0.55, 0.55, 0.55, 1),
                state="down" if is_active else "normal",
            )
            btn.bind(on_release=lambda b, idx=i: self._toggle_subcol(idx))
            self._subcol_buttons[i] = btn
            row.add_widget(btn)

        self._subcol_row = row
        self._controls.add_widget(row)
        self._controls.height += 44

    @staticmethod
    def _make_label_row(label_text: str) -> BoxLayout:
        row = BoxLayout(size_hint_y=None, height=40, spacing=6)
        lbl = Label(
            text=label_text,
            size_hint_x=None,
            width=130,
            halign="right",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        row.add_widget(lbl)
        return row

    def _make_toggle(self, text: str, group: str, callback) -> ToggleButton:
        btn = ToggleButton(
            text=text,
            group=group,
            font_size="13sp",
            bold=False,
            background_normal="",
            background_down="",
            background_color=self._INACTIVE_COLOR,
            color=(0.55, 0.55, 0.55, 1),
        )
        btn.bind(on_release=callback)
        return btn

    # ------------------------------------------------------------------
    # Selection handlers
    # ------------------------------------------------------------------

    def _select_mode(self, mode: str) -> None:
        self._display_mode = mode
        self._activate_buttons(self._mode_buttons, self._mode_labels, mode)
        self._redraw()

    def _select_type(self, mtype: str, redraw: bool = True) -> None:
        self._sel_type = mtype
        self._activate_buttons(self._type_buttons, self._type_labels, mtype)
        if mtype in _TYPE_CONFIG:
            self._graph.ylabel = _TYPE_CONFIG[mtype][4]
        else:
            self._graph.ylabel = mtype
        # Apply pre-computed y-scale for this type
        if mtype in self._type_yscale:
            ymin, ymax, ytick = self._type_yscale[mtype]
            self._graph.ymin   = ymin
            self._graph.ymax   = ymax
            self._graph.y_ticks_major = ytick
        self._update_subcol_row()
        if redraw:
            self._redraw()

    def _select_channel(self, channel: str, redraw: bool = True) -> None:
        self._sel_channel = channel
        self._activate_buttons(self._ch_buttons, self._ch_labels, channel)
        self._update_subcol_row()
        if redraw:
            self._redraw()

    def _toggle_subcol(self, idx: int) -> None:
        """Toggle one sub-column index; at least one must remain selected."""
        if idx in self._sel_subcol_indices:
            if len(self._sel_subcol_indices) <= 1:
                # Would leave nothing selected — restore button state and abort
                btn = self._subcol_buttons.get(idx)
                if btn:
                    btn.state = "down"
                return
            self._sel_subcol_indices.discard(idx)
        else:
            self._sel_subcol_indices.add(idx)

        # Update button appearance
        for i, btn in self._subcol_buttons.items():
            active = i in self._sel_subcol_indices
            btn.background_color = self._ACTIVE_COLOR if active else self._INACTIVE_COLOR
            btn.color = (1, 1, 1, 1) if active else (0.55, 0.55, 0.55, 1)
            btn.bold = active
            btn.state = "down" if active else "normal"

        self._redraw()

    def _activate_buttons(
        self,
        buttons: Dict[str, ToggleButton],
        labels: Dict[str, str],
        active_key: str,
    ) -> None:
        for key, btn in buttons.items():
            active = key == active_key
            base = labels.get(key, key)
            btn.text = f"> {base}" if active else base
            btn.state = "down" if active else "normal"
            btn.background_color = self._ACTIVE_COLOR if active else self._INACTIVE_COLOR
            btn.color = (1, 1, 1, 1) if active else (0.55, 0.55, 0.55, 1)
            btn.bold = active

    # ------------------------------------------------------------------
    # Plot rendering
    # ------------------------------------------------------------------

    _MAX_PLOT_POINTS = 800  # max points per LinePlot to avoid kivy rendering artefacts

    def _plot_pts(
        self, freqs: np.ndarray, lvls: np.ndarray
    ) -> List[Tuple[float, float]]:
        """Return a downsampled point list for display only."""
        n = len(freqs)
        if n > self._MAX_PLOT_POINTS:
            step = max(1, n // self._MAX_PLOT_POINTS)
            freqs = freqs[::step]
            lvls  = lvls[::step]
        return list(zip(freqs.tolist(), lvls.tolist()))

    def _lr_color(self, run: "MeasurementFile", col_idx: int, alpha: float) -> List[float]:
        """RGBA: blue (Left) or red (Right) for stereo; palette color for mono."""
        if run.channel is not None and col_idx < len(run.col_names):
            name = run.col_names[col_idx]
            if name.startswith("Left"):
                return self._LEFT_COLOR_RGB + [alpha]
            if name.startswith("Right"):
                return self._RIGHT_COLOR_RGB + [alpha]
        # Mono: use serial palette color
        return self._serial_colors.get(run.serial, [0.8, 0.8, 0.8, alpha])[:3] + [alpha]

    def _filter_runs(self) -> List[MeasurementFile]:
        result = [r for r in self._runs if r.meas_type == self._sel_type]
        if self._sel_channel is not None:
            result = [r for r in result if r.channel == self._sel_channel]
        return result

    def _get_col_indices(self, run: MeasurementFile) -> List[int]:
        """Return column pair indices to render for the current sub-column selection."""
        if not self._sel_subcol_indices:
            return list(range(len(run.frequencies)))
        return [i for i in sorted(self._sel_subcol_indices) if i < len(run.frequencies)]

    def _redraw(self) -> None:
        for p in self._individual_plots:
            self._graph.remove_plot(p)
        self._individual_plots.clear()
        for p in self._median_plots:
            self._graph.remove_plot(p)
        self._median_plots.clear()

        filtered = self._filter_runs()
        if not filtered:
            return

        # Accumulate per-column data (full resolution for median/scaling)
        # col_data[col_idx] = [(freqs, levels), ...]
        col_data: Dict[int, List[Tuple[np.ndarray, np.ndarray]]] = {}
        all_freqs_flat: List[np.ndarray] = []
        all_levels_flat: List[np.ndarray] = []
        col_color: Dict[int, List[float]] = {}  # opaque L/R color per col_idx

        for run in filtered:
            col_indices = self._get_col_indices(run)
            for col_idx in col_indices:
                if col_idx >= len(run.frequencies):
                    continue
                freqs = run.frequencies[col_idx]
                lvls  = run.levels[col_idx]
                if len(freqs) == 0:
                    continue

                col_data.setdefault(col_idx, []).append((freqs, lvls))
                all_freqs_flat.append(freqs)
                all_levels_flat.append(lvls)
                if col_idx not in col_color:
                    col_color[col_idx] = self._lr_color(run, col_idx, self._MEDIAN_ALPHA)

                # Individual curves only in "raw" mode
                if self._display_mode == "raw":
                    ind_color = self._lr_color(run, col_idx, self._INDIVIDUAL_ALPHA)
                    plot = LinePlot(
                        color=ind_color, line_width=self._INDIVIDUAL_LINE_WIDTH
                    )
                    plot.points = self._plot_pts(freqs, lvls)
                    self._graph.add_plot(plot)
                    self._individual_plots.append(plot)

        if not all_freqs_flat:
            return

        # Auto x-range from current filtered data
        min_f = float(min(f[0] for f in all_freqs_flat))
        max_f = float(max(f[-1] for f in all_freqs_flat))
        self._graph.xmin = max(10.0, min_f * 0.85)
        self._graph.xmax = max_f * 1.1
        # Y-scale is fixed per type (set in _select_type); no update here.

        # Median curves — only in "median" display mode
        if self._display_mode == "median":
            for col_idx, pairs in col_data.items():
                if len(pairs) >= 1:
                    self._draw_median(
                        [f for f, _ in pairs],
                        [l for _, l in pairs],
                        col_color.get(col_idx, list(self._MONO_MEDIAN_COLOR)),
                    )

    def _draw_median(
        self,
        all_freqs: List[np.ndarray],
        all_levels: List[np.ndarray],
        color: Optional[List[float]] = None,
    ) -> None:
        if color is None:
            color = list(self._MONO_MEDIAN_COLOR)
        common = all_freqs[0]
        interpolated = []
        for freqs, levels in zip(all_freqs, all_levels):
            if np.array_equal(freqs, common):
                interpolated.append(levels)
            else:
                interpolated.append(np.interp(common, freqs, levels))

        median_lvls = np.median(np.stack(interpolated), axis=0)
        # Downsample for display (same limit as individual plots)
        median_plot = LinePlot(color=color, line_width=self._MEDIAN_LINE_WIDTH)
        median_plot.points = self._plot_pts(common, median_lvls)
        self._graph.add_plot(median_plot)
        self._median_plots.append(median_plot)


# ---------------------------------------------------------------------------
# Selection Popup
# ---------------------------------------------------------------------------

class MeasurementSelectionPopup(Popup):
    """
    Two-step popup:
      1. Pick a measurement category (only shows categories that exist).
      2. Multi-select one or more result sub-folders for that category.

    on_confirm(category: str, folder_paths: List[Path]) is called on confirm.
    """

    def __init__(
        self,
        root_path: Path,
        on_confirm: Callable[[str, List[Path]], None],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.root_path = root_path
        self.on_confirm = on_confirm
        self.title = "Select Measurements"
        self.size_hint = (0.60, 0.72)
        self.auto_dismiss = True

        self._selected_category: Optional[str] = None
        self._selected_folders: Set[str] = set()
        self._folder_buttons: Dict[str, ToggleButton] = {}

        self._available_categories = _discover_categories(root_path)
        self._measurements_subdir_missing = not (root_path / "Measurements").is_dir()

        self._outer = BoxLayout(orientation="vertical", spacing=10, padding=12)
        self.content = self._outer

        self._build_category_row()
        self._build_folder_section()
        self._build_action_row()

        # Pre-select first available category
        if self._available_categories:
            self._select_category(self._available_categories[0])

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _build_category_row(self) -> None:
        """Radio-style category toggles, one per available category."""
        section_label = Label(
            text="Measurement Category",
            bold=True,
            size_hint_y=None,
            height=28,
            halign="left",
            valign="middle",
            color=(0.9, 0.9, 0.9, 1),
        )
        section_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self._outer.add_widget(section_label)

        self._cat_row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        self._outer.add_widget(self._cat_row)

        self._cat_buttons: Dict[str, ToggleButton] = {}
        for cat in self._available_categories:
            btn = ToggleButton(
                text=cat,
                group="category",
                font_size="15sp",
                bold=False,
                background_normal="",
                background_down="",
                background_color=(0.15, 0.17, 0.20, 1),
                color=(0.55, 0.55, 0.55, 1),
            )
            btn.bind(on_release=lambda b, c=cat: self._select_category(c))
            self._cat_buttons[cat] = btn
            self._cat_row.add_widget(btn)

        if not self._available_categories:
            if self._measurements_subdir_missing:
                msg = (
                    f"Expected subfolder not found:\n"
                    f"  {self.root_path / 'Measurements'}\n\n"
                    "Check that the correct root folder is configured in Settings."
                )
            else:
                msg = "No known categories (EOL / GoldenSample / Reference) found in Measurements/."
            self._cat_row.add_widget(Label(
                text=msg,
                color=(1.0, 0.5, 0.5, 1),
                halign="left",
                valign="middle",
            ))

    def _build_folder_section(self) -> None:
        """Scrollable multi-select list of result folders."""
        folder_label = Label(
            text="Result Folders  (multi-select)",
            bold=True,
            size_hint_y=None,
            height=28,
            halign="left",
            valign="middle",
            color=(0.9, 0.9, 0.9, 1),
        )
        folder_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self._outer.add_widget(folder_label)

        scroll = ScrollView(size_hint=(1, 1))
        self._folder_grid = GridLayout(cols=1, spacing=4, size_hint_y=None)
        self._folder_grid.bind(minimum_height=self._folder_grid.setter("height"))
        scroll.add_widget(self._folder_grid)
        self._outer.add_widget(scroll)

    def _build_action_row(self) -> None:
        """Confirm / Cancel buttons at the bottom."""
        action_row = BoxLayout(size_hint_y=None, height=44, spacing=8)

        self._status_label = Label(
            text="",
            size_hint_x=1,
            halign="left",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
        )
        self._status_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        confirm_btn = Button(
            text="Open",
            size_hint_x=None,
            width=110,
            background_normal="",
            background_color=(0.2, 0.55, 0.85, 1),
            disabled=not bool(self._available_categories),
        )
        confirm_btn.bind(on_release=self._on_confirm)

        cancel_btn = Button(
            text="Cancel",
            size_hint_x=None,
            width=90,
        )
        cancel_btn.bind(on_release=lambda *_: self.dismiss())

        action_row.add_widget(self._status_label)
        action_row.add_widget(confirm_btn)
        action_row.add_widget(cancel_btn)
        self._outer.add_widget(action_row)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _select_category(self, category: str) -> None:
        """Switch active category and reload the folder list."""
        self._selected_category = category
        self._selected_folders.clear()

        # Update toggle button states
        for cat, btn in self._cat_buttons.items():
            btn.state = "down" if cat == category else "normal"
            active = cat == category
            btn.background_color = (
                CATEGORY_ACTIVE_COLORS.get(cat, (0.3, 0.55, 0.75, 1))
                if active
                else (0.15, 0.17, 0.20, 1)   # dim/inactive
            )
            btn.color = (1, 1, 1, 1) if active else (0.55, 0.55, 0.55, 1)
            btn.bold = active
            btn.text = f"> {cat}" if active else cat

        # Rebuild folder list
        self._folder_grid.clear_widgets()
        self._folder_buttons.clear()

        folders = _discover_result_folders(self.root_path, category)
        if not folders:
            self._folder_grid.add_widget(Label(
                text="No result folders found.",
                size_hint_y=None,
                height=34,
                color=(0.7, 0.7, 0.7, 1),
            ))
            self._status_label.text = "No folders available."
            return

        for folder_name in folders:
            btn = ToggleButton(
                text=folder_name,
                size_hint_y=None,
                height=38,
                halign="left",
                valign="middle",
                background_normal="",
                background_color=(0.18, 0.22, 0.28, 1),
                background_down="",
            )
            btn.bind(size=lambda i, v: setattr(i, "text_size", (i.width - dp(12), i.height)))
            btn.bind(on_release=lambda b, fn=folder_name: self._toggle_folder(b, fn))
            self._folder_buttons[folder_name] = btn
            self._folder_grid.add_widget(btn)

        self._update_status()

    def _toggle_folder(self, button: ToggleButton, folder_name: str) -> None:
        """Toggle selection state of one folder button."""
        if button.state == "down":
            self._selected_folders.add(folder_name)
            button.background_color = (0.25, 0.45, 0.65, 1)
        else:
            self._selected_folders.discard(folder_name)
            button.background_color = (0.18, 0.22, 0.28, 1)
        self._update_status()

    def _update_status(self) -> None:
        count = len(self._selected_folders)
        if count == 0:
            self._status_label.text = "Select at least one folder."
            self._status_label.color = (0.8, 0.8, 0.8, 1)
        else:
            self._status_label.text = f"{count} folder{'s' if count > 1 else ''} selected."
            self._status_label.color = (0.6, 0.9, 0.6, 1)

    def _on_confirm(self, *_) -> None:
        if not self._selected_category:
            self._status_label.text = "Please select a category."
            self._status_label.color = (1.0, 0.5, 0.5, 1)
            return
        if not self._selected_folders:
            self._status_label.text = "Please select at least one folder."
            self._status_label.color = (1.0, 0.5, 0.5, 1)
            return

        paths = [
            _resolve_folder_path(self.root_path, self._selected_category, fn)
            for fn in sorted(self._selected_folders)
        ]
        self.dismiss()
        self.on_confirm(self._selected_category, paths)


# ---------------------------------------------------------------------------
# Main View (stub — data handling will follow)
# ---------------------------------------------------------------------------

class MeasurementsViewerRoot(BoxLayout):
    """Main Measurements view. Opened after category + folders are confirmed."""

    STATUS_INFO_COLOR = (0.75, 0.75, 0.75, 1)
    STATUS_SUCCESS_COLOR = (0.6, 0.9, 0.6, 1)
    STATUS_ERROR_COLOR = (1.0, 0.45, 0.45, 1)

    def __init__(
        self,
        settings_store: DataToolsSettingsStore,
        on_back: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(orientation="vertical", spacing=6, padding=12, **kwargs)
        self.settings_store = settings_store
        self.on_back = on_back
        self._has_selection = False
        self._chart: Optional[MeasurementChart] = None

        root_path_str = settings_store.get("measurements_root_path", "")
        self.root_path = Path(root_path_str) if root_path_str else None

        # --- Header ---
        header = BoxLayout(size_hint_y=None, height=42, spacing=8)
        title = Label(
            text="Measurements",
            font_size="26sp",
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda i, v: setattr(i, "text_size", v))
        header.add_widget(title)

        if on_back is not None:
            back_btn = Button(text="Back to Home", size_hint_x=None, width=150)
            back_btn.bind(on_release=lambda *_: on_back())
            header.add_widget(back_btn)

        self.add_widget(header)

        # --- Content area (swaps between placeholder and chart) ---
        self._content_area = BoxLayout()
        self._placeholder = Label(
            text="No data loaded. Use 'Select Measurements' to begin.",
            font_size="15sp",
            color=self.STATUS_INFO_COLOR,
            halign="center",
            valign="middle",
        )
        self._placeholder.bind(size=lambda i, v: setattr(i, "text_size", v))
        self._content_area.add_widget(self._placeholder)
        self.add_widget(self._content_area)

        # --- Footer toolbar ---
        toolbar = BoxLayout(size_hint_y=None, height=42, spacing=8)
        select_btn = Button(
            text="Select Measurements",
            background_normal="",
            background_color=(0.2, 0.55, 0.85, 1),
        )
        select_btn.bind(on_release=lambda *_: self._open_selection_popup())
        self._info_label = Label(
            text="",
            size_hint_x=1,
            halign="right",
            valign="middle",
            color=(0.7, 0.7, 0.7, 1),
            font_size="13sp",
        )
        self._info_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        toolbar.add_widget(select_btn)
        toolbar.add_widget(self._info_label)
        self.add_widget(toolbar)

        # Auto-open popup on first entry if root is configured
        if self.root_path and self.root_path.is_dir():
            Clock.schedule_once(lambda _dt: self._open_selection_popup(), 0.2)
        elif not self.root_path:
            self._placeholder.text = (
                "Measurements root folder is not configured.\n"
                "Go to Settings → set 'Measurements Root Path'."
            )

    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Called when returning to this view from Home."""
        root_path_str = self.settings_store.get("measurements_root_path", "")
        new_root = Path(root_path_str) if root_path_str else None

        if new_root != self.root_path:
            self.root_path = new_root
            self._has_selection = False
            self._info_label.text = ""
            self._show_placeholder(
                "No data loaded. Use 'Select Measurements' to begin.",
                self.STATUS_INFO_COLOR,
            )

        if self._has_selection:
            return

        if self.root_path and self.root_path.is_dir():
            Clock.schedule_once(lambda _dt: self._open_selection_popup(), 0.1)
        elif not self.root_path:
            self._placeholder.text = (
                "Measurements root folder is not configured.\n"
                "Go to Settings → set 'Measurements Root Path'."
            )

    # ------------------------------------------------------------------

    def _show_placeholder(self, text: str, color: tuple) -> None:
        self._content_area.clear_widgets()
        self._placeholder.text = text
        self._placeholder.color = color
        self._content_area.add_widget(self._placeholder)

    def _show_chart(self) -> None:
        self._content_area.clear_widgets()
        if self._chart is None:
            self._chart = MeasurementChart()
        self._content_area.add_widget(self._chart)

    def _open_selection_popup(self) -> None:
        if not self.root_path or not self.root_path.is_dir():
            self._show_placeholder(
                "Measurements root folder is not configured or not found.\n"
                "Go to Settings → set 'Measurements Root Path'.",
                self.STATUS_ERROR_COLOR,
            )
            return
        MeasurementSelectionPopup(
            root_path=self.root_path,
            on_confirm=self._on_selection_confirmed,
        ).open()

    def _on_selection_confirmed(self, category: str, folder_paths: List[Path]) -> None:
        self._has_selection = True
        names = ", ".join(p.name for p in folder_paths)
        self._show_placeholder(
            f"Loading {category} — {names}…",
            self.STATUS_INFO_COLOR,
        )
        Clock.schedule_once(
            lambda _dt: self._load_and_show(category, folder_paths), 0.05
        )

    def _load_and_show(self, category: str, folder_paths: List[Path]) -> None:
        runs = MeasurementLoader.load_folders(folder_paths)

        if not runs:
            self._has_selection = False
            self._show_placeholder(
                f"No measurement files found.\nCategory: {category}",
                self.STATUS_ERROR_COLOR,
            )
            return

        self._show_chart()
        self._chart.load_data(runs)

        serials = len({r.serial for r in runs})
        timestamps = len({(r.serial, r.timestamp) for r in runs})
        self._info_label.text = (
            f"{category}  ·  {serials} serial{'s' if serials != 1 else ''}  ·  {timestamps} run{'s' if timestamps != 1 else ''}"
        )
