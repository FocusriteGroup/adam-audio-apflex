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
from kivy_garden.graph import Graph, LinePlot, MeshLinePlot

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
# L-R fixture compensation
# ---------------------------------------------------------------------------

# Default path to the L-R fixture compensation curve CSV
_DEFAULT_LR_DIFF_PATH: Path = Path(__file__).parents[2] / "DefaultReferences" / "L-R-Diff.csv"


def _load_lr_diff(path: Path) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Load a 4-header-row L-R difference CSV; returns (freqs, levels) or None."""
    result = _load_limit_file(path)
    return (result[0], result[1]) if result is not None else None


def _load_limit_file(
    path: Path,
) -> Optional[Tuple[np.ndarray, np.ndarray, str]]:
    """Load a 4-header single-column CSV; returns (freqs, values, y_unit) or None."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if len(lines) < 5:
            return None
        # Unit is in row 3 (index 3), second comma-separated token
        unit_parts = [u.strip() for u in lines[3].split(",")]
        y_unit = unit_parts[1] if len(unit_parts) > 1 else ""
        pairs: List[Tuple[float, float]] = []
        for row in csv.reader(lines[4:]):
            stripped = [c.strip() for c in row]
            if len(stripped) >= 2:
                try:
                    pairs.append((float(stripped[0]), float(stripped[1])))
                except ValueError:
                    pass
        if not pairs:
            return None
        pairs.sort(key=lambda p: p[0])
        freqs  = np.array([p[0] for p in pairs])
        levels = np.array([p[1] for p in pairs])
        return freqs, levels, y_unit
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Category reference curves and limits
# ---------------------------------------------------------------------------

@dataclass
class CategoryRefs:
    """Reference curves and tolerance limits for one measurement category."""
    # Reference curves: list per AP input column (index 0 = Ch1, 1 = Ch2)
    rms_ref:   List[Tuple[np.ndarray, np.ndarray]]   # (freqs, dBSPL)
    phase_ref: List[Tuple[np.ndarray, np.ndarray]]   # (freqs, degrees)
    # Limits
    rms_limit:   Optional[Tuple[np.ndarray, np.ndarray]]  # (freqs, ±dB) symmetric
    phase_upper: Optional[Tuple[np.ndarray, np.ndarray]]  # (freqs, +deg offset from ref)
    phase_lower: Optional[Tuple[np.ndarray, np.ndarray]]  # (freqs, -deg offset from ref)
    thd_limit:   Optional[List[Tuple[np.ndarray, np.ndarray]]]  # per channel: (freqs, absolute limit in %)


def _parse_ap_csv(path: Path) -> Optional[List[Tuple[np.ndarray, np.ndarray]]]:
    """Parse an AP 4-header CSV; returns list of (freqs, levels) per column pair."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if len(lines) < 5:
            return None
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
        result: List[Tuple[np.ndarray, np.ndarray]] = []
        for i in range(col_count // 2):
            xi, yi = i * 2, i * 2 + 1
            pairs: List[Tuple[float, float]] = []
            for r in data_rows:
                if len(r) > yi:
                    try:
                        pairs.append((float(r[xi]), float(r[yi])))
                    except ValueError:
                        pass
            if not pairs:
                continue
            pairs.sort(key=lambda p: p[0])
            seen: set = set()
            unique: List[Tuple[float, float]] = []
            for f, lv in pairs:
                if f not in seen:
                    seen.add(f)
                    unique.append((f, lv))
            result.append((
                np.array([p[0] for p in unique]),
                np.array([p[1] for p in unique]),
            ))
        return result or None
    except Exception:
        return None


def _load_category_refs(root_path: Path, category: str) -> Optional[CategoryRefs]:
    """Load reference curves and limits for a category from the References folder."""
    base    = root_path / "References" / category
    lim_dir = base / "Limits"
    if not base.is_dir():
        return None

    rms_ref   = _parse_ap_csv(base / "RMS.csv")   or []
    phase_ref = _parse_ap_csv(base / "Phase.csv") or []

    rms_limit   = _load_lr_diff(lim_dir / "RMS.csv")
    phase_upper = _load_lr_diff(lim_dir / "PhaseUpper.csv")
    phase_lower = _load_lr_diff(lim_dir / "PhaseLower.csv")

    thd_limit: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None
    thd_ref = _parse_ap_csv(base / "THD.csv") or []
    thd_raw = _load_limit_file(lim_dir / "THD.csv")
    if thd_raw is not None and thd_ref:
        lim_f, lim_v, thd_unit = thd_raw
        thd_limit_cols: List[Tuple[np.ndarray, np.ndarray]] = []
        for ref_f, ref_pct in thd_ref:
            offset_interp = np.interp(ref_f, lim_f, lim_v)
            if thd_unit.strip().lower() == "%":
                # Relative %: 100% = doubling → factor = 1 + pct/100
                abs_limit = ref_pct * (1.0 + offset_interp / 100.0)
            else:
                # dB offset: limit = ref × 10^(dB/20)
                abs_limit = ref_pct * 10.0 ** (offset_interp / 20.0)
            thd_limit_cols.append((ref_f, abs_limit))
        thd_limit = thd_limit_cols

    return CategoryRefs(
        rms_ref=rms_ref,
        phase_ref=phase_ref,
        rms_limit=rms_limit,
        phase_upper=phase_upper,
        phase_lower=phase_lower,
        thd_limit=thd_limit,
    )


# ---------------------------------------------------------------------------
# Measurement data model
# ---------------------------------------------------------------------------

# Filename suffixes that are not measurement data (excluded from viewer)
_EXCLUDED_TYPES: Set[str] = {"Waveform", "Report", "RMS_Level_Sub_pre_calibration"}

# Fixed display order for measurement type selector
_TYPE_ORDER = ["RMS_Level", "Phase", "THD", "RnB_CF", "RnB_PR", "LR_Diff"]

# Type configuration: display_label, ymin, ymax, y_tick_major, ylabel
_TYPE_CONFIG: Dict[str, Tuple[str, float, float, float, str]] = {
    "RMS_Level":     ("RMS Level",      70,   130,  5,  "dBSPL"),
    "Phase":         ("Phase",         -180,  180,  45, "degrees"),
    "THD":           ("THD",             0,    15,   2, "%"),
    "RnB_CF":        ("RnB Crest",       0,    20,   5, "dB"),
    "RnB_PR":        ("RnB Peak Ratio", -80,    0,  10, "dB"),
    "LR_Diff":       ("L-R Compensation", -6,    6,   1, "dB"),
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
    _DISPLAY_MODES  = ["raw", "median", "normalized"]
    _DISPLAY_LABELS = {"raw": "Raw", "median": "Median", "normalized": "Norm."}

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
        self._lr_diff_plots: List = []
        self._limit_plots: List = []
        self._violation_plots: List = []
        self._computed_medians: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}  # col_idx → (freqs, levels)

        # L-R compensation (data set externally by MeasurementsViewerRoot)
        self._lr_diff_data: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._compensate_rms: bool = False
        self._comp_buttons: Dict[str, ToggleButton] = {}
        self._cat_refs: Optional[CategoryRefs] = None
        self._comp_row: Optional[BoxLayout] = None
        self._display_row: Optional[BoxLayout] = None
        self._input_row: Optional[BoxLayout] = None

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
        self._tips = _DelayedTooltipManager(delay=0.6)
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
        # Add L-R Diff "type" if compensation curve is available
        if self._lr_diff_data is not None and "LR_Diff" not in self._available_types:
            self._available_types.append("LR_Diff")
        self._available_channels = sorted({r.channel for r in runs if r.channel is not None})
        self._sel_subcol_indices = set()  # reset on fresh data load
        self._compensate_rms = False

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

        # Expand y-scale to include limit curves so they're always visible
        if self._cat_refs is not None:
            refs = self._cat_refs
            for mtype in list(self._type_yscale):
                limit_vals: List[float] = []
                if mtype == "RMS_Level" and refs.rms_limit is not None:
                    lim_f, lim_v = refs.rms_limit
                    for ch_col in range(max(1, len(refs.rms_ref))):
                        _, ul = self._abs_limit_curve(refs.rms_ref, ch_col, lim_f,  lim_v)
                        _, ll = self._abs_limit_curve(refs.rms_ref, ch_col, lim_f, -lim_v)
                        limit_vals.extend(ul.tolist())
                        limit_vals.extend(ll.tolist())
                elif mtype == "Phase":
                    for ch_col in range(max(1, len(refs.phase_ref))):
                        if refs.phase_upper is not None:
                            _, ul = self._abs_limit_curve(refs.phase_ref, ch_col, *refs.phase_upper)
                            limit_vals.extend(ul.tolist())
                        if refs.phase_lower is not None:
                            _, ll = self._abs_limit_curve(refs.phase_ref, ch_col, *refs.phase_lower)
                            limit_vals.extend(ll.tolist())
                elif mtype == "THD" and refs.thd_limit is not None:
                    for _, lv in refs.thd_limit:
                        limit_vals.extend(lv.tolist())
                if limit_vals:
                    cur_ymin, cur_ymax, _ = self._type_yscale[mtype]
                    new_ymin, new_ymax, new_ytick = _nice_range(
                        min(cur_ymin, min(limit_vals)),
                        max(cur_ymax, max(limit_vals)),
                    )
                    self._type_yscale[mtype] = (new_ymin, new_ymax, new_ytick)

        self._build_controls()
        self._activate_buttons(self._mode_buttons, self._mode_labels, self._display_mode)

        if self._available_types:
            self._select_type(self._available_types[0], redraw=False)
        if self._available_channels:
            self._select_channel(self._available_channels[0], redraw=False)
        else:
            self._sel_channel = None

        self._update_subcol_row()
        self._update_comp_row()
        self._redraw()

    def set_lr_diff(self, data: Optional[Tuple[np.ndarray, np.ndarray]]) -> None:
        """Set the L-R fixture compensation curve (called by MeasurementsViewerRoot)."""
        self._lr_diff_data = data

    def set_cat_refs(self, refs: Optional[CategoryRefs]) -> None:
        """Set category reference curves and limits (called by MeasurementsViewerRoot)."""
        self._cat_refs = refs

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
        self._comp_buttons.clear()
        self._type_labels.clear()
        self._ch_labels.clear()
        self._mode_labels.clear()
        self._subcol_names.clear()
        self._comp_row = None
        self._display_row = None
        self._input_row = None
        row_count = 0

        _mtype_tips = {
            "RMS_Level": "Frequency-response amplitude [dBSPL].",
            "Phase":     "Frequency-response phase [degrees].",
            "THD":       "Total Harmonic Distortion.",
            "RnB_CF":    "Rub-and-Buzz crest factor.",
            "RnB_PR":    "Rub-and-Buzz peak ratio [dB].",
            "LR_Diff":   "Left-Right difference curve (fixture compensation).",
        }
        _mode_tips = {
            "raw":        "Show all individual measurement curves.",
            "median":     "Show only the per-channel median curve.",
            "normalized": "Show each curve as deviation from its channel median.",
        }
        if self._available_types:
            row = self._make_label_row("Measurement:")
            for t in self._available_types:
                display = _TYPE_CONFIG[t][0] if t in _TYPE_CONFIG else t
                self._type_labels[t] = display
                btn = self._make_toggle(display, "mtype", lambda b, tp=t: self._select_type(tp))
                self._type_buttons[t] = btn
                self._tips.register(btn, _mtype_tips.get(t, f"Show {display} measurements."))
                row.add_widget(btn)
            self._controls.add_widget(row)
            row_count += 1

        # Display-mode row (Raw / Median)
        self._display_row = self._make_label_row("Display:")
        for mode in self._DISPLAY_MODES:
            label = self._DISPLAY_LABELS[mode]
            self._mode_labels[mode] = label
            btn = self._make_toggle(label, "display", lambda b, m=mode: self._select_mode(m))
            self._mode_buttons[mode] = btn
            self._tips.register(btn, _mode_tips.get(mode, mode))
            self._display_row.add_widget(btn)
        self._controls.add_widget(self._display_row)
        row_count += 1

        if self._available_channels:
            self._input_row = self._make_label_row("Input:")
            for ch in self._available_channels:
                self._ch_labels[ch] = ch
                btn = self._make_toggle(ch, "channel", lambda b, c=ch: self._select_channel(c))
                self._ch_buttons[ch] = btn
                self._tips.register(btn, f"Filter to input channel '{ch}'.")
                self._input_row.add_widget(btn)
            self._controls.add_widget(self._input_row)
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
            self._tips.register(btn, f"Toggle sub-channel '{sc}' on/off.")
            row.add_widget(btn)

        self._subcol_row = row
        self._controls.add_widget(row)
        self._controls.height += 44

    def _update_comp_row(self) -> None:
        """Show/hide L-R compensation toggle (only for RMS Level + stereo + diff curve loaded)."""
        # Remove existing comp row from widget tree
        if self._comp_row is not None and self._comp_row.parent is not None:
            self._controls.remove_widget(self._comp_row)
            self._controls.height = max(0, self._controls.height - 44)
        self._comp_row = None
        self._comp_buttons.clear()

        # Show only when: RMS Level is selected, diff curve is loaded,
        # and the runs have Left/Right sub-columns (regardless of input-channel split).
        filtered = self._filter_runs()
        has_lr_subcols = any(
            any(n.startswith(("Left", "Right")) for n in r.col_names)
            for r in filtered
        )
        if (
            self._sel_type != "RMS_Level"
            or self._lr_diff_data is None
            or not has_lr_subcols
        ):
            return

        row = self._make_label_row("Compensation:")
        comp_labels = {"off": "Off", "on": "On"}
        _comp_tips = {
            "off": "Show raw levels without L-R fixture compensation.",
            "on":  "Apply the L-R difference curve to equalise fixture offsets between channels.",
        }
        for mode in ("off", "on"):
            btn = self._make_toggle(
                comp_labels[mode], "compensation", lambda b, m=mode: self._select_comp(m)
            )
            self._comp_buttons[mode] = btn
            self._tips.register(btn, _comp_tips[mode])
            row.add_widget(btn)

        active_mode = "on" if self._compensate_rms else "off"
        self._activate_buttons(self._comp_buttons, comp_labels, active_mode)

        self._comp_row = row
        self._controls.add_widget(row)
        self._controls.height += 44

    def _set_mode_input_visible(self, visible: bool) -> None:
        """Show or hide Display/Input rows (not relevant for L-R Diff view)."""
        for row in (self._display_row, self._input_row):
            if row is None:
                continue
            currently_visible = row.height > 0
            if visible and not currently_visible:
                row.height = 44
                row.opacity = 1.0
                row.disabled = False
                self._controls.height += 44
            elif not visible and currently_visible:
                row.height = 0
                row.opacity = 0.0
                row.disabled = True
                self._controls.height = max(0, self._controls.height - 44)

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
            self._graph.ymin = ymin
            self._graph.ymax = ymax
            self._graph.y_ticks_major = ytick
        elif mtype in _TYPE_CONFIG:
            _, ymin, ymax, ytick, _ = _TYPE_CONFIG[mtype]
            self._graph.ymin = ymin
            self._graph.ymax = ymax
            self._graph.y_ticks_major = ytick
        self._update_subcol_row()
        self._update_comp_row()
        self._set_mode_input_visible(mtype != "LR_Diff")
        if redraw:
            self._redraw()

    def _select_channel(self, channel: str, redraw: bool = True) -> None:
        self._sel_channel = channel
        self._activate_buttons(self._ch_buttons, self._ch_labels, channel)
        self._update_subcol_row()
        self._update_comp_row()  # re-append comp row so it stays below subcol row
        if redraw:
            self._redraw()

    def _select_comp(self, mode: str) -> None:
        """Toggle L-R compensation on/off for the RMS Level plot."""
        self._compensate_rms = (mode == "on")
        self._activate_buttons(self._comp_buttons, {"off": "Off", "on": "On"}, mode)
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
        for p in self._lr_diff_plots:
            self._graph.remove_plot(p)
        self._lr_diff_plots.clear()
        for p in self._limit_plots + self._violation_plots:
            self._graph.remove_plot(p)
        self._limit_plots.clear()
        self._violation_plots.clear()
        self._computed_medians.clear()

        if self._sel_type == "LR_Diff":
            self._draw_lr_diff_view()
            return

        filtered = self._filter_runs()
        if not filtered:
            return

        # -- Pass 1: collect data --
        col_data: Dict[int, List[Tuple[np.ndarray, np.ndarray]]] = {}
        all_freqs_flat: List[np.ndarray] = []
        col_color: Dict[int, List[float]] = {}

        for run in filtered:
            col_indices = self._get_col_indices(run)
            for col_idx in col_indices:
                if col_idx >= len(run.frequencies):
                    continue
                freqs = run.frequencies[col_idx]
                lvls  = self._apply_compensation(run, col_idx, run.levels[col_idx], freqs)
                if len(freqs) == 0:
                    continue
                col_data.setdefault(col_idx, []).append((freqs, lvls))
                all_freqs_flat.append(freqs)
                if col_idx not in col_color:
                    col_color[col_idx] = self._lr_color(run, col_idx, self._MEDIAN_ALPHA)

        if not all_freqs_flat:
            return

        # Auto x-range
        min_f = float(min(f[0] for f in all_freqs_flat))
        max_f = float(max(f[-1] for f in all_freqs_flat))
        self._graph.xmin = max(10.0, min_f * 0.85)
        self._graph.xmax = max_f * 1.1

        # Compute medians for every col_idx (violation checking + median/normalized drawing)
        for col_idx, pairs in col_data.items():
            common = pairs[0][0]
            interp = [
                l if np.array_equal(f, common) else np.interp(common, f, l)
                for f, l in pairs
            ]
            self._computed_medians[col_idx] = (common, np.median(np.stack(interp), axis=0))

        # Restore absolute y-scale when not in normalized mode
        if self._display_mode != "normalized" and self._sel_type in self._type_yscale:
            ymin, ymax, ytick = self._type_yscale[self._sel_type]
            self._graph.ymin = ymin
            self._graph.ymax = ymax
            self._graph.y_ticks_major = ytick

        # -- Pass 2: draw curves by mode --
        if self._display_mode == "raw":
            for run in filtered:
                for col_idx in self._get_col_indices(run):
                    if col_idx >= len(run.frequencies):
                        continue
                    freqs = run.frequencies[col_idx]
                    lvls  = self._apply_compensation(run, col_idx, run.levels[col_idx], freqs)
                    if len(freqs) == 0:
                        continue
                    ind_color = self._lr_color(run, col_idx, self._INDIVIDUAL_ALPHA)
                    plot = LinePlot(color=ind_color, line_width=self._INDIVIDUAL_LINE_WIDTH)
                    plot.points = self._plot_pts(freqs, lvls)
                    self._graph.add_plot(plot)
                    self._individual_plots.append(plot)

        elif self._display_mode == "median":
            for col_idx, (med_f, med_l) in self._computed_medians.items():
                self._draw_median(
                    med_f, med_l,
                    col_color.get(col_idx, list(self._MONO_MEDIAN_COLOR)),
                )

        elif self._display_mode == "normalized":
            dev_vals: List[float] = []
            for run in filtered:
                for col_idx in self._get_col_indices(run):
                    if col_idx >= len(run.frequencies) or col_idx not in self._computed_medians:
                        continue
                    freqs = run.frequencies[col_idx]
                    lvls  = self._apply_compensation(run, col_idx, run.levels[col_idx], freqs)
                    if len(freqs) == 0:
                        continue
                    med_f, med_l = self._computed_medians[col_idx]
                    dev = lvls - np.interp(freqs, med_f, med_l)
                    dev_vals.extend(dev.tolist())
                    ind_color = self._lr_color(run, col_idx, self._INDIVIDUAL_ALPHA)
                    plot = LinePlot(color=ind_color, line_width=self._INDIVIDUAL_LINE_WIDTH)
                    plot.points = self._plot_pts(freqs, dev)
                    self._graph.add_plot(plot)
                    self._individual_plots.append(plot)
            if dev_vals:
                max_dev = max(abs(min(dev_vals)), abs(max(dev_vals)))
                # Also include relative limit values so limit lines are always visible
                max_dev = max(max_dev, self._normalized_limit_max())
                ymin, ymax, ytick = _nice_range(-max_dev * 1.05, max_dev * 1.05)
                self._graph.ymin = ymin
                self._graph.ymax = ymax
                self._graph.y_ticks_major = ytick

        # Limits: absolute in raw/median, relative in normalized
        if self._display_mode == "normalized":
            self._draw_normalized_limits()
        else:
            self._draw_limits()

    def _draw_median(
        self,
        freqs: np.ndarray,
        levels: np.ndarray,
        color: Optional[List[float]] = None,
    ) -> None:
        if color is None:
            color = list(self._MONO_MEDIAN_COLOR)
        median_plot = LinePlot(color=color, line_width=self._MEDIAN_LINE_WIDTH)
        median_plot.points = self._plot_pts(freqs, levels)
        self._graph.add_plot(median_plot)
        self._median_plots.append(median_plot)

    def _draw_lr_diff_view(self) -> None:
        """Draw the L-R fixture compensation curve on the graph."""
        if self._lr_diff_data is None:
            return
        freqs, levels = self._lr_diff_data
        if len(freqs) == 0:
            return
        self._graph.xmin = max(10.0, float(freqs[0]) * 0.85)
        self._graph.xmax = float(freqs[-1]) * 1.1
        plot = LinePlot(color=[0.95, 0.75, 0.25, 1.0], line_width=2.0)
        plot.points = self._plot_pts(freqs, levels)
        self._graph.add_plot(plot)
        self._lr_diff_plots.append(plot)

    def _apply_compensation(
        self,
        run: "MeasurementFile",
        col_idx: int,
        lvls: np.ndarray,
        freqs: np.ndarray,
    ) -> np.ndarray:
        """Return levels with L-R fixture compensation applied (half-diff per channel)."""
        if not self._compensate_rms or self._lr_diff_data is None:
            return lvls
        if self._sel_type != "RMS_Level":
            return lvls
        if col_idx >= len(run.col_names):
            return lvls
        diff_freqs, diff_levels = self._lr_diff_data
        half_diff = np.interp(freqs, diff_freqs, diff_levels) / 2.0
        name = run.col_names[col_idx]
        if name.startswith("Left"):
            return lvls + half_diff
        if name.startswith("Right"):
            return lvls - half_diff
        return lvls

    # ------------------------------------------------------------------
    # Limit lines and violation highlighting
    # ------------------------------------------------------------------

    _LIMIT_COLOR               = [1.0, 1.0, 1.0, 0.90]  # white
    _VIOLATION_COLOR           = [1.0, 0.18, 0.12, 1.0]  # red
    _LIMIT_LINE_WIDTH          = 1.0
    _VIOLATION_LINE_WIDTH      = 2.5

    def _draw_limits(self) -> None:
        """Draw absolute limit lines and violation highlights for the current type."""
        if self._cat_refs is None:
            return
        if self._sel_type not in ("RMS_Level", "Phase", "THD"):
            return
        ch_col = 1 if self._sel_channel == "Ch_2" else 0
        if self._sel_type == "RMS_Level":
            self._draw_rms_limits(ch_col)
        elif self._sel_type == "Phase":
            self._draw_phase_limits(ch_col)
        elif self._sel_type == "THD":
            self._draw_thd_limits(ch_col)

    def _normalized_limit_max(self) -> float:
        """Return the max absolute relative-limit value for the current type/channel."""
        refs = self._cat_refs
        if refs is None or self._sel_type not in ("RMS_Level", "Phase", "THD"):
            return 0.0
        ch_col = 1 if self._sel_channel == "Ch_2" else 0
        vals: List[float] = []
        if self._sel_type == "RMS_Level" and refs.rms_limit is not None:
            vals.extend(refs.rms_limit[1].tolist())
        elif self._sel_type == "Phase":
            if refs.phase_upper is not None:
                vals.extend(refs.phase_upper[1].tolist())
            if refs.phase_lower is not None:
                vals.extend(refs.phase_lower[1].tolist())
        elif self._sel_type == "THD" and refs.thd_limit is not None and ch_col < len(refs.thd_limit):
            lim_f, lim_v = refs.thd_limit[ch_col]
            if ch_col in self._computed_medians:
                med_f, med_l = self._computed_medians[ch_col]
                vals.extend((lim_v - np.interp(lim_f, med_f, med_l)).tolist())
            else:
                vals.extend(lim_v.tolist())
        if not vals:
            return 0.0
        return max(abs(min(vals)), abs(max(vals)))

    def _draw_normalized_limits(self) -> None:
        """Draw relative limit lines (offset from zero) in normalized display mode."""
        refs = self._cat_refs
        if refs is None:
            return
        if self._sel_type not in ("RMS_Level", "Phase", "THD"):
            return
        ch_col = 1 if self._sel_channel == "Ch_2" else 0

        if self._sel_type == "RMS_Level" and refs.rms_limit is not None:
            lim_f, lim_v = refs.rms_limit
            out_f, offset = self._rel_limit_on_ref(refs.rms_ref, ch_col, lim_f, lim_v)
            self._draw_dashed_limit(out_f,  offset)
            self._draw_dashed_limit(out_f, -offset)
            for freqs, dev in self._iter_check_curves():
                for sf, sl in self._find_violations(freqs, dev, out_f,  offset, upper=True):
                    self._draw_violation_segment(sf, sl, upper=True)
                for sf, sl in self._find_violations(freqs, dev, out_f, -offset, upper=False):
                    self._draw_violation_segment(sf, sl, upper=False)

        elif self._sel_type == "Phase":
            limit_lines: List[Tuple[np.ndarray, np.ndarray, bool]] = []
            for lim_raw, is_upper in ((refs.phase_upper, True), (refs.phase_lower, False)):
                if lim_raw is None:
                    continue
                out_f, offset = self._rel_limit_on_ref(refs.phase_ref, ch_col, *lim_raw)
                self._draw_dashed_limit(out_f, offset)
                limit_lines.append((out_f, offset, is_upper))
            for freqs, dev in self._iter_check_curves():
                for lf, ll, is_upper in limit_lines:
                    for sf, sl in self._find_violations(freqs, dev, lf, ll, upper=is_upper):
                        self._draw_violation_segment(sf, sl, upper=is_upper)

        elif self._sel_type == "THD" and refs.thd_limit is not None and ch_col < len(refs.thd_limit):
            lim_f, lim_v = refs.thd_limit[ch_col]  # absolute limit in %
            if ch_col in self._computed_medians:
                med_f, med_l = self._computed_medians[ch_col]
                rel_lim = lim_v - np.interp(lim_f, med_f, med_l)
            else:
                rel_lim = np.zeros_like(lim_v)
            self._draw_dashed_limit(lim_f, rel_lim)
            for freqs, dev in self._iter_check_curves():
                for sf, sl in self._find_violations(freqs, dev, lim_f, rel_lim, upper=True):
                    self._draw_violation_segment(sf, sl, upper=True)

    def _rel_limit_on_ref(
        self,
        ref_list: List[Tuple[np.ndarray, np.ndarray]],
        col: int,
        lim_f: np.ndarray,
        lim_v: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (freqs, offset) for a relative limit, on the reference's dense freq grid."""
        if ref_list and col < len(ref_list):
            ref_f, _ = ref_list[col]
            in_range = (ref_f >= lim_f[0]) & (ref_f <= lim_f[-1])
            if in_range.any():
                out_f = ref_f[in_range]
                return out_f, np.interp(out_f, lim_f, lim_v)
        return lim_f, lim_v

    def _abs_limit_curve(
        self,
        ref_list: List[Tuple[np.ndarray, np.ndarray]],
        col: int,
        lim_f: np.ndarray,
        lim_v: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Add limit offset to reference curve, using reference's dense frequency grid."""
        if ref_list and col < len(ref_list):
            ref_f, ref_v = ref_list[col]
            # Clip to the limit's frequency range, then interpolate offset at ref points
            in_range = (ref_f >= lim_f[0]) & (ref_f <= lim_f[-1])
            if not in_range.any():
                return lim_f, np.interp(lim_f, ref_f, ref_v) + lim_v
            out_f = ref_f[in_range]
            out_v = ref_v[in_range]
            offset_at_ref = np.interp(out_f, lim_f, lim_v)
            return out_f, out_v + offset_at_ref
        else:
            return lim_f, lim_v

    def _iter_check_curves(self) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Curves to check against limits: medians (median), deviations (normalized), raws."""
        if self._display_mode == "median":
            return list(self._computed_medians.values())
        result: List[Tuple[np.ndarray, np.ndarray]] = []
        for run in self._filter_runs():
            for col_idx in self._get_col_indices(run):
                if col_idx >= len(run.frequencies):
                    continue
                freqs = run.frequencies[col_idx]
                lvls  = self._apply_compensation(run, col_idx, run.levels[col_idx], freqs)
                if self._display_mode == "normalized" and col_idx in self._computed_medians:
                    med_f, med_l = self._computed_medians[col_idx]
                    lvls = lvls - np.interp(freqs, med_f, med_l)
                result.append((freqs, lvls))
        return result

    def _draw_rms_limits(self, ch_col: int) -> None:
        refs = self._cat_refs
        if refs.rms_limit is None:
            return
        lim_f, lim_v = refs.rms_limit
        upper_f, upper_l = self._abs_limit_curve(refs.rms_ref, ch_col, lim_f,  lim_v)
        lower_f, lower_l = self._abs_limit_curve(refs.rms_ref, ch_col, lim_f, -lim_v)
        self._draw_dashed_limit(upper_f, upper_l)
        self._draw_dashed_limit(lower_f, lower_l)
        for freqs, lvls in self._iter_check_curves():
            for sf, sl in self._find_violations(freqs, lvls, upper_f, upper_l, upper=True):
                self._draw_violation_segment(sf, sl, upper=True)
            for sf, sl in self._find_violations(freqs, lvls, lower_f, lower_l, upper=False):
                self._draw_violation_segment(sf, sl, upper=False)

    def _draw_phase_limits(self, ch_col: int) -> None:
        refs = self._cat_refs
        limit_lines: List[Tuple[np.ndarray, np.ndarray, bool]] = []
        if refs.phase_upper is not None:
            uf, ul = self._abs_limit_curve(refs.phase_ref, ch_col, *refs.phase_upper)
            self._draw_dashed_limit(uf, ul)
            limit_lines.append((uf, ul, True))
        if refs.phase_lower is not None:
            lf, ll = self._abs_limit_curve(refs.phase_ref, ch_col, *refs.phase_lower)
            self._draw_dashed_limit(lf, ll)
            limit_lines.append((lf, ll, False))
        for freqs, lvls in self._iter_check_curves():
            for lim_f, lim_l, is_upper in limit_lines:
                for sf, sl in self._find_violations(freqs, lvls, lim_f, lim_l, upper=is_upper):
                    self._draw_violation_segment(sf, sl, upper=is_upper)

    def _draw_thd_limits(self, ch_col: int) -> None:
        refs = self._cat_refs
        if refs.thd_limit is None or ch_col >= len(refs.thd_limit):
            return
        lim_f, lim_v = refs.thd_limit[ch_col]
        self._draw_dashed_limit(lim_f, lim_v)
        for freqs, lvls in self._iter_check_curves():
            for sf, sl in self._find_violations(freqs, lvls, lim_f, lim_v, upper=True):
                self._draw_violation_segment(sf, sl, upper=True)

    def _draw_dashed_limit(
        self,
        freqs: np.ndarray,
        levels: np.ndarray,
        color: Optional[List[float]] = None,
    ) -> None:
        """Draw a solid thin limit line."""
        if color is None:
            color = self._LIMIT_COLOR
        if len(freqs) < 2 or freqs[0] <= 0:
            return
        plot = LinePlot(color=color, line_width=self._LIMIT_LINE_WIDTH)
        plot.points = list(zip(freqs.tolist(), levels.tolist()))
        self._graph.add_plot(plot)
        self._limit_plots.append(plot)

    @staticmethod
    def _find_violations(
        freqs: np.ndarray,
        levels: np.ndarray,
        limit_f: np.ndarray,
        limit_l: np.ndarray,
        *,
        upper: bool,
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Return contiguous (freqs, levels) segments where measurement exceeds limit."""
        f_min, f_max = limit_f[0], limit_f[-1]
        in_range = (freqs >= f_min) & (freqs <= f_max)
        if not in_range.any():
            return []
        f_r  = freqs[in_range]
        l_r  = levels[in_range]
        lim_at_f = np.interp(f_r, limit_f, limit_l)
        violates = l_r > lim_at_f if upper else l_r < lim_at_f
        segments: List[Tuple[np.ndarray, np.ndarray]] = []
        in_seg = False
        start_i = 0
        for i, v in enumerate(violates):
            if v and not in_seg:
                start_i = i
                in_seg = True
            elif not v and in_seg:
                if i > start_i:
                    segments.append((f_r[start_i:i], l_r[start_i:i]))
                in_seg = False
        if in_seg and len(f_r) > start_i:
            segments.append((f_r[start_i:], l_r[start_i:]))
        return segments

    def _draw_violation_segment(
        self, freqs: np.ndarray, levels: np.ndarray, upper: bool = True
    ) -> None:
        """Draw the failing portion of a curve in red (upper) or blue (lower)."""
        if len(freqs) < 1:
            return
        color = self._VIOLATION_COLOR
        plot = LinePlot(color=color, line_width=self._VIOLATION_LINE_WIDTH)
        plot.points = self._plot_pts(freqs, levels)
        self._graph.add_plot(plot)
        self._violation_plots.append(plot)


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
        self._tips = _DelayedTooltipManager(delay=0.6)

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
        _cat_tips = {
            "EOL":          "End-of-line production measurements.",
            "GoldenSample": "Reference golden-sample measurements.",
            "Reference":    "Reference measurements for limit generation.",
        }
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
            self._tips.register(btn, _cat_tips.get(cat, f"Show {cat} measurements."))
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
        self._tips.register(confirm_btn, "Load the selected folders and open the chart.")
        self._tips.register(cancel_btn, "Dismiss without loading.")

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
            self._tips.register(btn, "Click to select/deselect this result folder.")
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
# Analysis — reference & limit generation
# ---------------------------------------------------------------------------

@dataclass
class AnalysisOptions:
    reference_type: str   # "stereo" | "mono"
    lr_diff_source: str   # "existing" | "new"
    use_comp:       bool
    smooth_n:       float  # 1/N octave, 0 = off
    # per type: mode "sigma" | "offset", value, freq range
    rms_mode:    str;    rms_value:   float;  rms_f_low:   float;  rms_f_high:   float
    phase_mode:  str;    phase_value: float;  phase_f_low: float;  phase_f_high: float
    thd_mode:    str;    thd_value:   float;  thd_f_low:   float;  thd_f_high:   float


def _smooth_octave(freqs: np.ndarray, values: np.ndarray, n: float) -> np.ndarray:
    """Apply 1/N octave smoothing on a log-frequency axis."""
    if n <= 0 or len(freqs) < 2:
        return values.copy()
    half_width = 2.0 ** (1.0 / (2.0 * n))
    result = np.empty_like(values, dtype=float)
    for i, f in enumerate(freqs):
        mask = (freqs >= f / half_width) & (freqs <= f * half_width)
        result[i] = float(np.mean(values[mask])) if mask.any() else float(values[i])
    return result


def _compute_col_stats(
    runs: List[MeasurementFile],
    mtype: str,
    lr_diff: Optional[Tuple[np.ndarray, np.ndarray]],
    use_comp: bool,
) -> Dict[Tuple[Optional[str], int], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Compute per-(channel, col_idx) median and std across all runs of *mtype*.
    Returns {(channel, col_idx): (freqs, median, std)}.
    """
    from collections import defaultdict
    buckets: Dict[Tuple[Optional[str], int], List[Tuple[np.ndarray, np.ndarray]]] = defaultdict(list)

    for run in runs:
        if run.meas_type != mtype:
            continue
        for col_idx, (freqs, levels) in enumerate(zip(run.frequencies, run.levels)):
            lvls = levels.copy()
            if use_comp and lr_diff is not None and mtype == "RMS_Level" and run.channel is not None:
                diff_f, diff_v = lr_diff
                half = np.interp(freqs, diff_f, diff_v) / 2.0
                col_name = run.col_names[col_idx] if col_idx < len(run.col_names) else ""
                if col_name.startswith("Left"):
                    lvls = lvls + half
                elif col_name.startswith("Right"):
                    lvls = lvls - half
            buckets[(run.channel, col_idx)].append((freqs, lvls))

    result: Dict[Tuple[Optional[str], int], Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for key, pairs in buckets.items():
        common = pairs[0][0]
        stacked = np.stack([
            lv if np.array_equal(f, common) else np.interp(common, f, lv)
            for f, lv in pairs
        ])
        ddof = 1 if len(pairs) > 1 else 0
        result[key] = (common, np.median(stacked, axis=0), np.std(stacked, axis=0, ddof=ddof))
    return result


def _write_ap_ref_csv(
    path: Path,
    meas_name: str,
    subcol_names: List[str],
    unit: str,
    freq_cols: List[np.ndarray],
    level_cols: List[np.ndarray],
) -> None:
    """Write AP 4-header reference CSV (one or more column pairs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(freq_cols)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(meas_name + "," * (n * 2 - 1) + "\n")
        subcol_row = ",".join(v for sn in subcol_names for v in (sn, ""))
        f.write(subcol_row + "\n")
        f.write(",".join(["X", "Y"] * n) + "\n")
        f.write(",".join(["Hz", unit] * n) + "\n")
        max_len = max(len(fv) for fv in freq_cols)
        for i in range(max_len):
            row = []
            for j in range(n):
                if i < len(freq_cols[j]):
                    row += [f"{freq_cols[j][i]:.6g}", f"{level_cols[j][i]:.6g}"]
                else:
                    row += ["", ""]
            f.write(",".join(row) + "\n")


def _write_ap_limit_csv(
    path: Path,
    name: str,
    unit: str,
    freqs: np.ndarray,
    values: np.ndarray,
) -> None:
    """Write AP 4-header single-column limit CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(f"{name},\n")
        f.write("Ch1,\n")
        f.write("X,Y\n")
        f.write(f"Hz,{unit}\n")
        for fv, lv in zip(freqs, values):
            f.write(f"{fv:.6g},{lv:.6g}\n")


def _plot_analysis_results(
    output_dir: Path,
    runs: List[MeasurementFile],
    plot_data: Dict[str, dict],
    lr_diff_out: Optional[Tuple[np.ndarray, np.ndarray]],
) -> List[str]:
    """
    Render PNG overview plots for all computed measurement types.
    Returns a list of created relative filenames (e.g. "Plots/RMS.png").
    Silently returns [] if matplotlib is not available.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        return []

    plot_dir = output_dir / "Plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    created: List[str] = []

    _COL_COLORS = ["#3a7dd4", "#e07020", "#35b050", "#c040a0"]

    for mtype, data in plot_data.items():
        freq_cols   = data["freq_cols"]
        median_cols = data["median_cols"]
        std_cols    = data["std_cols"]
        lim_f       = data["lim_f"]
        lim_val     = data["lim_val"]
        subcols     = data["subcols"]
        unit        = data["unit"]
        fname       = data["fname"]
        title       = data["title"]
        is_thd      = (mtype == "THD")

        fig, ax = plt.subplots(figsize=(11, 5))
        ax.set_xscale("log")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.grid(True, which="both", alpha=0.3, linewidth=0.5)
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(
            lambda v, _: (f"{int(v):,}" if v >= 1000 else f"{int(v)}")))

        # --- Individual run curves (light grey background) ---
        for run in runs:
            if run.meas_type != mtype:
                continue
            for ci in range(len(run.frequencies)):
                ax.plot(run.frequencies[ci], run.levels[ci],
                        color="#999999", alpha=0.20, linewidth=0.7, zorder=1)

        # --- Per sub-column: median + limit band ---
        lim_f_arr = np.asarray(lim_f) if lim_f is not None else None
        lim_v_arr = np.asarray(lim_val) if lim_val is not None else None

        for i, (fc, mc, sc_name) in enumerate(zip(freq_cols, median_cols, subcols)):
            color = _COL_COLORS[i % len(_COL_COLORS)]
            ax.plot(fc, mc, color=color, linewidth=2.0, zorder=3,
                    label=sc_name if len(subcols) > 1 else None)

            if lim_f_arr is not None and lim_v_arr is not None:
                lv = np.interp(fc, lim_f_arr, lim_v_arr)
                if is_thd:
                    # lv is the % factor; upper bound = median * (1 + lv/100)
                    safe_mc = np.where(np.abs(mc) > 1e-10, np.abs(mc), 1e-10)
                    abs_upper = safe_mc * (1.0 + lv / 100.0)
                    ax.fill_between(fc, mc, abs_upper,
                                    alpha=0.18, color=color, zorder=2)
                    ax.plot(fc, abs_upper, color=color, linewidth=1.0,
                            linestyle="--", alpha=0.75, zorder=2)
                else:
                    ax.fill_between(fc, mc - lv, mc + lv,
                                    alpha=0.18, color=color, zorder=2)
                    ax.plot(fc, mc + lv, color=color, linewidth=1.0,
                            linestyle="--", alpha=0.75, zorder=2)
                    ax.plot(fc, mc - lv, color=color, linewidth=1.0,
                            linestyle="--", alpha=0.75, zorder=2)

        if len(subcols) > 1:
            ax.legend(fontsize=9, loc="upper right")

        n_runs = sum(1 for r in runs if r.meas_type == mtype)
        ax.annotate(f"n = {n_runs} runs", xy=(0.98, 0.02),
                    xycoords="axes fraction", ha="right", va="bottom",
                    fontsize=9, color="#555555")

        fig.tight_layout()
        out_path = plot_dir / f"{fname}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        created.append(f"Plots/{fname}.png")

    # --- L-R-Diff plot ---
    if lr_diff_out is not None:
        f_diff, v_diff = lr_diff_out
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.set_xscale("log")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("dB")
        ax.set_title("L-R Difference")
        ax.grid(True, which="both", alpha=0.3, linewidth=0.5)
        ax.axhline(0.0, color="#555555", linewidth=0.8, linestyle="-")
        ax.plot(f_diff, v_diff, color="#3a7dd4", linewidth=2.0)
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(
            lambda v, _: (f"{int(v):,}" if v >= 1000 else f"{int(v)}")))
        ax.annotate(
            "Positive = Left louder than Right",
            xy=(0.02, 0.96), xycoords="axes fraction",
            ha="left", va="top", fontsize=8, color="#555555",
        )
        fig.tight_layout()
        fig.savefig(plot_dir / "L-R-Diff.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        created.append("Plots/L-R-Diff.png")

    return created


def _write_analysis_readme(
    output_dir: Path,
    category: str,
    opts: AnalysisOptions,
    is_stereo: bool,
    n_runs: int,
    files_written: List[str],
) -> None:
    """Write a README.md into output_dir explaining the exported files."""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    ref_type_note = (
        "Stereo — separate Left/Right reference columns"
        if is_stereo and opts.reference_type == "stereo"
        else "Mono — single averaged reference column"
    )
    smooth_label = (
        f"1/{int(opts.smooth_n)} octave" if opts.smooth_n > 0 else "none"
    )

    def _mode_desc(mode: str, val: float, unit: str) -> str:
        if mode == "sigma":
            return f"{val} × σ (standard deviation)"
        return f"fixed ±{val} {unit}"

    lines = [
        f"# Analysis Export — {category}",
        f"",
        f"Generated: {now}  ",
        f"Runs analysed: {n_runs}  ",
        f"Reference type: {ref_type_note}  ",
        f"Smoothing: {smooth_label}  ",
        f"",
        f"---",
        f"",
        f"## How to deploy these files",
        f"",
        f"The workstation reads references from a `References/` folder inside the",
        f"APx project data directory (configured in DataTools **Settings → Measurements root path**).",
        f"",
        f"Copy the files as follows:",
        f"",
        f"```",
        f"<Measurements root>/",
        f"├── References/",
        f"│   ├── {category}/          ← copy RMS.csv, Phase.csv, THD.csv here",
        f"│   │   ├── RMS.csv",
        f"│   │   ├── Phase.csv",
        f"│   │   ├── THD.csv",
        f"│   │   └── Limits/          ← copy the four limit files here",
        f"│   │       ├── RMS.csv",
        f"│   │       ├── PhaseUpper.csv",
        f"│   │       ├── PhaseLower.csv",
        f"│   │       └── THD.csv",
    ]
    if is_stereo:
        lines += [
            f"│   └── L-R-Diff.csv         ← copy here (used for L/R compensation)",
        ]
    lines += [
        f"└── ...",
        f"```",
        f"",
        f"> **Tip:** The `Plots/` subfolder contains PNG overview charts for visual",
        f"> inspection. These plots are **not** used by the workstation.",
        f"",
        f"---",
        f"",
        f"## Files in this folder",
        f"",
        f"| File | Description | Unit |",
        f"|------|-------------|------|",
        f"| `RMS.csv` | Median RMS level reference curve(s) | dBSPL |",
        f"| `Phase.csv` | Median phase reference curve(s) | deg |",
        f"| `THD.csv` | Median THD reference curve(s) | % |",
    ]
    if is_stereo:
        lines += [
            f"| `L-R-Diff.csv` | Median Left-minus-Right difference curve | dB |",
        ]
    lines += [
        f"| `Limits/RMS.csv` | RMS tolerance (half-width of the pass band) | dB |",
        f"| `Limits/PhaseUpper.csv` | Phase upper tolerance | deg |",
        f"| `Limits/PhaseLower.csv` | Phase lower tolerance (negated) | deg |",
        f"| `Limits/THD.csv` | THD tolerance as a relative % factor | % |",
        f"",
        f"All CSV files use the **AP 4-header format** (4 rows of header, then X/Y data pairs).",
        f"",
        f"---",
        f"",
        f"## Limit settings used",
        f"",
        f"| Type | Mode | Value | Freq range |",
        f"|------|------|-------|------------|",
        f"| RMS Level | {_mode_desc(opts.rms_mode, opts.rms_value, 'dB')} "
        f"| {opts.rms_value} | {opts.rms_f_low} – {opts.rms_f_high} Hz |",
        f"| Phase | {_mode_desc(opts.phase_mode, opts.phase_value, 'deg')} "
        f"| {opts.phase_value} | {opts.phase_f_low} – {opts.phase_f_high} Hz |",
        f"| THD | {_mode_desc(opts.thd_mode, opts.thd_value, '%')} "
        f"| {opts.thd_value} | {opts.thd_f_low} – {opts.thd_f_high} Hz |",
        f"",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def run_analysis(
    opts: AnalysisOptions,
    runs: List[MeasurementFile],
    lr_diff_existing: Optional[Tuple[np.ndarray, np.ndarray]],
    output_dir: Path,
    category: str = "",
) -> str:
    """Generate reference curves and statistical limits. Returns a status message."""
    ref_dir = output_dir
    lim_dir = ref_dir / "Limits"
    ref_dir.mkdir(parents=True, exist_ok=True)
    lim_dir.mkdir(parents=True, exist_ok=True)

    is_stereo = any(r.channel is not None for r in runs)
    lr_diff = lr_diff_existing
    lr_diff_for_plot: Optional[Tuple[np.ndarray, np.ndarray]] = None
    files_written: List[str] = []
    plot_data: Dict[str, dict] = {}

    # --- Compute/save L-R-Diff ---
    if is_stereo:
        rms_stats_raw = _compute_col_stats(runs, "RMS_Level", None, False)
        left_key  = next(((ch, ci) for (ch, ci), _ in rms_stats_raw.items()
                          if ci < len(next((r for r in runs if r.meas_type == "RMS_Level"), runs[0]).col_names)
                          and next((r for r in runs if r.meas_type == "RMS_Level"), runs[0]).col_names[ci].startswith("Left")), None)
        right_key = next(((ch, ci) for (ch, ci), _ in rms_stats_raw.items()
                          if ci < len(next((r for r in runs if r.meas_type == "RMS_Level"), runs[0]).col_names)
                          and next((r for r in runs if r.meas_type == "RMS_Level"), runs[0]).col_names[ci].startswith("Right")), None)

        # Simpler: look for Left/Right by col_names of any RMS run
        rep_rms = next((r for r in runs if r.meas_type == "RMS_Level"), None)
        if rep_rms:
            left_key_  = next(((ch, ci) for (ch, ci) in rms_stats_raw
                               if ci < len(rep_rms.col_names) and rep_rms.col_names[ci].startswith("Left")), None)
            right_key_ = next(((ch, ci) for (ch, ci) in rms_stats_raw
                               if ci < len(rep_rms.col_names) and rep_rms.col_names[ci].startswith("Right")), None)
            if left_key_ and right_key_:
                lf, lm, _ = rms_stats_raw[left_key_]
                rf, rm, _ = rms_stats_raw[right_key_]
                new_diff_f = lf
                new_diff_v = np.interp(lf, rf, rm) - lm
                _write_ap_limit_csv(ref_dir / "L-R-Diff.csv", "L-R Difference", "dBSPL",
                                    new_diff_f, new_diff_v)
                files_written.append("L-R-Diff.csv")
                lr_diff_for_plot = (new_diff_f, new_diff_v)
                if opts.lr_diff_source == "new":
                    lr_diff = (new_diff_f, new_diff_v)

    # --- Per measurement type ---
    _MTYPE_META = {
        "RMS_Level": ("RMS Level",   "RMS",   "dBSPL"),
        "Phase":     ("Phase",       "Phase", "deg"),
        "THD":       ("THD Ratio",   "THD",   "%"),
    }
    _type_sigma = {
        "RMS_Level": opts.rms_value,   "Phase": opts.phase_value,   "THD": opts.thd_value,
    }
    _type_mode = {
        "RMS_Level": opts.rms_mode,    "Phase": opts.phase_mode,    "THD": opts.thd_mode,
    }
    _type_f_low  = {
        "RMS_Level": opts.rms_f_low,   "Phase": opts.phase_f_low,   "THD": opts.thd_f_low,
    }
    _type_f_high = {
        "RMS_Level": opts.rms_f_high,  "Phase": opts.phase_f_high,  "THD": opts.thd_f_high,
    }

    for mtype, (meas_name, fname, unit) in _MTYPE_META.items():
        type_runs = [r for r in runs if r.meas_type == mtype]
        if not type_runs:
            continue
        rep = type_runs[0]

        use_comp = opts.use_comp and mtype == "RMS_Level" and is_stereo
        stats = _compute_col_stats(runs, mtype, lr_diff if use_comp else None, use_comp)
        if not stats:
            continue

        # Collect per col_idx (merge across channels for stereo)
        col_indices = sorted({ci for (_, ci) in stats})
        freq_cols:   List[np.ndarray] = []
        median_cols: List[np.ndarray] = []
        std_cols:    List[np.ndarray] = []
        final_subcols: List[str] = []

        for ci in col_indices:
            # Prefer Ch_1; fallback to any
            key = next(((ch, ci) for (ch, c) in stats if c == ci and ch == rep.channel), None)
            if key is None:
                key = next(((ch, c) for (ch, c) in stats if c == ci), None)
            if key is None:
                continue
            freqs, median, std = stats[key]
            mask = (freqs >= _type_f_low[mtype]) & (freqs <= _type_f_high[mtype])
            if not mask.any():
                continue
            fc = freqs[mask]
            mc = _smooth_octave(fc, median[mask], opts.smooth_n)
            sc = _smooth_octave(fc, std[mask],    opts.smooth_n)
            freq_cols.append(fc)
            median_cols.append(mc)
            std_cols.append(sc)
            sn = rep.col_names[ci] if ci < len(rep.col_names) else f"Col{ci+1}"
            final_subcols.append(sn)

        if not freq_cols:
            continue

        # Mono reference: average across all sub-columns
        if is_stereo and opts.reference_type == "mono" and len(median_cols) >= 2:
            cf = freq_cols[0]
            avg_med = np.mean([np.interp(cf, freq_cols[i], median_cols[i])
                               for i in range(len(median_cols))], axis=0)
            avg_std = np.mean([np.interp(cf, freq_cols[i], std_cols[i])
                               for i in range(len(std_cols))], axis=0)
            freq_cols   = [cf] * len(final_subcols)
            median_cols = [avg_med] * len(final_subcols)
            std_cols    = [avg_std] * len(final_subcols)

        # Write reference
        _write_ap_ref_csv(ref_dir / f"{fname}.csv", meas_name, final_subcols,
                          unit, freq_cols, median_cols)
        files_written.append(f"{fname}.csv")

        # Limit computation
        # sigma mode: full frequency-dependent std vector
        # offset mode: constant → only two boundary points needed
        mode  = _type_mode[mtype]
        val   = _type_sigma[mtype]
        f_lo  = _type_f_low[mtype]
        f_hi  = _type_f_high[mtype]
        lim_f_full = freq_cols[0]

        if mode == "sigma":
            lim_f_out = lim_f_full
            lim_s = np.mean([np.interp(lim_f_out, freq_cols[i], std_cols[i])
                             for i in range(len(std_cols))], axis=0)
        else:
            lim_f_out = np.array([f_lo, f_hi], dtype=float)
            lim_s = None  # not needed in offset mode

        if mtype == "RMS_Level":
            lim_val = val * lim_s if mode == "sigma" else np.array([val, val], dtype=float)
            _write_ap_limit_csv(lim_dir / "RMS.csv", "RMS Limit", "dB",
                                 lim_f_out, lim_val)
            files_written.append("Limits/RMS.csv")
            plot_data[mtype] = dict(
                freq_cols=freq_cols, median_cols=median_cols, std_cols=std_cols,
                lim_f=lim_f_out, lim_val=lim_val, subcols=final_subcols,
                unit="dBSPL", fname="RMS", title="RMS Level",
            )

        elif mtype == "Phase":
            lim_val = val * lim_s if mode == "sigma" else np.array([val, val], dtype=float)
            _write_ap_limit_csv(lim_dir / "PhaseUpper.csv", "Phase Upper Limit", "deg",
                                 lim_f_out,  lim_val)
            _write_ap_limit_csv(lim_dir / "PhaseLower.csv", "Phase Lower Limit", "deg",
                                 lim_f_out, -lim_val)
            files_written += ["Limits/PhaseUpper.csv", "Limits/PhaseLower.csv"]
            plot_data[mtype] = dict(
                freq_cols=freq_cols, median_cols=median_cols, std_cols=std_cols,
                lim_f=lim_f_out, lim_val=lim_val, subcols=final_subcols,
                unit="deg", fname="Phase", title="Phase",
            )

        elif mtype == "THD":
            if mode == "sigma":
                ref_med   = median_cols[0]
                safe_ref  = np.where(np.abs(ref_med) > 1e-10, np.abs(ref_med), 1e-10)
                pct_factor = (val * lim_s / safe_ref) * 100.0
            else:
                # Parallel shift over the full reference frequency vector so the
                # limit mirrors the shape of the reference curve.
                lim_f_out = lim_f_full
                ref_med = np.mean(
                    [np.interp(lim_f_full, freq_cols[i], median_cols[i])
                     for i in range(len(median_cols))], axis=0,
                )
                safe_ref = np.where(np.abs(ref_med) > 1e-10, np.abs(ref_med), 1e-10)
                pct_factor = (val / safe_ref) * 100.0
            _write_ap_limit_csv(lim_dir / "THD.csv", "THD Limit", "%",
                                 lim_f_out, pct_factor)
            files_written.append("Limits/THD.csv")
            plot_data[mtype] = dict(
                freq_cols=freq_cols, median_cols=median_cols, std_cols=std_cols,
                lim_f=lim_f_out, lim_val=pct_factor, subcols=final_subcols,
                unit="%", fname="THD", title="THD",
            )

    if not files_written:
        return "No measurement data found."

    # --- Plots and README ---
    plot_files = _plot_analysis_results(output_dir, runs, plot_data, lr_diff_for_plot)
    files_written += plot_files
    _write_analysis_readme(
        output_dir, category or "Unknown", opts, is_stereo,
        n_runs=len(runs), files_written=files_written,
    )
    files_written.append("README.md")

    refs  = [f for f in files_written if "/" not in f]
    lims  = [f for f in files_written if f.startswith("Limits/")]
    plots = [f for f in files_written if f.startswith("Plots/")]
    parts = (
        [f for f in refs if f != "README.md"]
        + ([f"Limits/ ({len(lims)}×)"] if lims else [])
        + ([f"Plots/ ({len(plots)}×)"] if plots else [])
        + (["README.md"] if "README.md" in files_written else [])
    )
    return "Saved: " + ", ".join(parts)


class _TooltipWidget(BoxLayout):
    """Lightweight tooltip bubble attached directly to the Window."""

    def __init__(self, text: str, pos, **kwargs):
        super().__init__(padding=(10, 5, 10, 5), **kwargs)
        self.size_hint = (None, None)
        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.13, 0.13, 0.15, 0.94)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))
        lab = Label(text=text, font_size="12sp", halign="left", valign="middle",
                    color=(0.95, 0.95, 0.95, 1), size_hint=(1, 1))
        lab.bind(size=lambda i, _v: setattr(i, "text_size", (i.width, None)))
        self.add_widget(lab)
        width = max(180, min(560, int(len(text) * 7.2) + 24))
        self.size = (width, 32)
        self.pos = pos


class _DelayedTooltipManager:
    """Show a tooltip bubble after the mouse lingers on a registered widget."""

    def __init__(self, delay: float = 0.6):
        self._delay   = delay
        self._entries: List[Tuple[Widget, str]] = []
        self._hovered: Optional[Widget] = None
        self._event   = None
        self._tip: Optional[_TooltipWidget] = None
        self._mouse   = (0, 0)
        Window.bind(mouse_pos=self._on_mouse)

    def register(self, widget: Widget, text: str) -> None:
        if widget and text:
            self._entries.append((widget, text))

    def _find(self, x: float, y: float):
        for w, t in reversed(self._entries):
            if w.get_root_window() is None:
                continue
            lx, ly = w.to_widget(x, y, relative=False)
            if w.collide_point(lx, ly):
                return w, t
        return None

    def _on_mouse(self, _win, pos) -> None:
        x, y = pos
        self._mouse = pos
        hit = self._find(x, y)
        if not hit:
            self._cancel(); self._hovered = None; self._hide(); return
        w, t = hit
        if w is self._hovered:
            return
        self._cancel(); self._hide()
        self._hovered = w
        self._event = Clock.schedule_once(lambda _dt: self._show(t), self._delay)

    def _show(self, text: str) -> None:
        self._event = None
        if not self._hovered:
            return
        mx, my = self._mouse
        tip = _TooltipWidget(text=text, pos=(0, 0))
        tx = min(mx + 12, Window.width  - tip.width  - 8)
        ty = min(my + 16, Window.height - tip.height - 8)
        tip.pos = (max(8, tx), max(8, ty))
        Window.add_widget(tip)
        self._tip = tip

    def _cancel(self) -> None:
        if self._event is not None:
            self._event.cancel(); self._event = None

    def _hide(self) -> None:
        if self._tip is not None:
            Window.remove_widget(self._tip); self._tip = None


class AnalysisDialog(Popup):
    """Dialog to configure and run reference/limit generation."""

    _ACTIVE_BG   = (0.2, 0.55, 0.85, 1)
    _INACTIVE_BG = (0.22, 0.22, 0.25, 1)

    def __init__(
        self,
        runs: List[MeasurementFile],
        lr_diff_existing: Optional[Tuple[np.ndarray, np.ndarray]],
        root_path: Path,
        category: str,
        settings_store: Optional["DataToolsSettingsStore"] = None,
        on_done: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._runs          = runs
        self._lr_diff       = lr_diff_existing
        self._root_path     = root_path
        self._category      = category
        self._on_done       = on_done
        self._store         = settings_store
        self._is_stereo     = any(r.channel is not None for r in runs)

        self.title      = "Generate References & Limits"
        self.size_hint  = (0.60, 0.80)
        self.auto_dismiss = True

        def _s(key, default):  # load from store or fall back to default
            return self._store.get(key, str(default)) if self._store else str(default)

        # Option state — restored from settings
        self._ref_type  = _s("analysis_ref_type",  "stereo" if self._is_stereo else "mono")
        self._lr_source = _s("analysis_lr_source",  "existing")
        self._use_comp  = _s("analysis_use_comp",   "true") == "true"

        outer = BoxLayout(orientation="vertical", spacing=10, padding=14)
        self.content = outer
        self._tips = _DelayedTooltipManager(delay=0.6)

        from kivy.uix.textinput import TextInput

        def lbl(text, align="right", size_hint_x=1, font_size="13sp", color=(0.85, 0.85, 0.85, 1)):
            l = Label(text=text, halign=align, valign="middle",
                      color=color, font_size=font_size, size_hint_x=size_hint_x)
            l.bind(size=lambda i, v: setattr(i, "text_size", v))
            return l

        def toggle_row(options, getter, setter, tips: Dict[str, str] = None):
            row = BoxLayout(spacing=4)
            btns: Dict[str, ToggleButton] = {}
            for key, label in options.items():
                btn = ToggleButton(text=label, group=id(options),
                                   background_normal="", background_down="",
                                   background_color=self._ACTIVE_BG if getter() == key else self._INACTIVE_BG,
                                   color=(1, 1, 1, 1), bold=getter() == key,
                                   state="down" if getter() == key else "normal",
                                   font_size="13sp")
                def _cb(b, k=key, s=setter, bs=btns, opts=options):
                    s(k)
                    for kk, bb in bs.items():
                        active = kk == k
                        bb.background_color = self._ACTIVE_BG if active else self._INACTIVE_BG
                        bb.bold = active
                btn.bind(on_release=_cb)
                btns[key] = btn
                row.add_widget(btn)
                if tips and key in tips:
                    self._tips.register(btn, tips[key])
            return row

        def ti(default, hint=""):
            return TextInput(text=str(default), hint_text=hint,
                             multiline=False, font_size="13sp",
                             background_color=(0.15, 0.15, 0.17, 1),
                             foreground_color=(1, 1, 1, 1))

        # --- Stereo options (2-col grid) ---
        top_grid = GridLayout(cols=2, spacing=8, size_hint_y=None,
                              row_default_height=40, row_force_default=True)
        top_grid.bind(minimum_height=top_grid.setter("height"))

        if self._is_stereo:
            top_grid.add_widget(lbl("Reference type:"))
            self._ref_row = toggle_row(
                {"stereo": "Stereo", "mono": "Mono"},
                lambda: self._ref_type,
                lambda v: setattr(self, "_ref_type", v),
                tips={
                    "stereo": "Separate Left and Right reference curves.",
                    "mono":   "Average Left and Right into a single reference curve.",
                },
            )
            top_grid.add_widget(self._ref_row)

            top_grid.add_widget(lbl("Compensation:"))
            self._comp_row_w = toggle_row(
                {"on": "On", "off": "Off"},
                lambda: "on" if self._use_comp else "off",
                lambda v: setattr(self, "_use_comp", v == "on"),
                tips={
                    "on":  "Apply L-R fixture compensation (shifts each channel by ½ diff) before computing the reference.",
                    "off": "Compute reference without L-R compensation.",
                },
            )
            top_grid.add_widget(self._comp_row_w)

            top_grid.add_widget(lbl("L-R Diff:"))
            self._lr_row = toggle_row(
                {"existing": "Use existing", "new": "Compute new"},
                lambda: self._lr_source,
                lambda v: setattr(self, "_lr_source", v),
                tips={
                    "existing": "Load L-R-Diff.csv from the References folder.",
                    "new":      "Recompute L-R difference from the current measurements and export it.",
                },
            )
            top_grid.add_widget(self._lr_row)

        top_grid.add_widget(lbl("Smoothing:"))
        from kivy.uix.spinner import Spinner
        _SMOOTH_OPTS = ["None", "1/24", "1/12", "1/9", "1/6", "1/3", "1"]
        _SMOOTH_N    = {"None": 0.0, "1/24": 24.0, "1/12": 12.0, "1/9": 9.0,
                        "1/6": 6.0,  "1/3":  3.0,  "1":    1.0}
        _saved_smooth = _s("analysis_smooth_n", "1/3")
        _smooth_default = _saved_smooth if _saved_smooth in _SMOOTH_OPTS else "1/3"
        self._smooth_spinner = Spinner(
            text=_smooth_default,
            values=_SMOOTH_OPTS,
            background_normal="", background_color=(0.15, 0.15, 0.17, 1),
            color=(1, 1, 1, 1), font_size="13sp",
        )
        self._smooth_n_map = _SMOOTH_N
        top_grid.add_widget(self._smooth_spinner)
        self._tips.register(
            self._smooth_spinner,
            "1/N octave log-scale smoothing applied to reference and limit curves before export. 'None' = no smoothing.",
        )

        if top_grid.children:  # only add if there's something in it
            outer.add_widget(top_grid)

        # --- Per-type settings table ---
        _DIM_COLOR = (0.50, 0.50, 0.55, 1)
        _ROW_H  = 36
        _LABEL_X = 0.24
        _MODE_X  = 0.15
        _VAL_X   = 0.13
        _FLOW_X  = 0.19
        _SEP_X   = 0.05
        _FHIGH_X = 0.19
        _PAD_X   = 0.05

        # Header
        hdr = BoxLayout(size_hint_y=None, height=26, spacing=4)
        hdr.add_widget(Widget(size_hint_x=_LABEL_X))
        hdr.add_widget(Widget(size_hint_x=_MODE_X))
        hdr.add_widget(lbl("value",  "center", _VAL_X,   "14sp", _DIM_COLOR))
        hdr.add_widget(lbl("f low",  "center", _FLOW_X,  "14sp", _DIM_COLOR))
        hdr.add_widget(Widget(size_hint_x=_SEP_X))
        hdr.add_widget(lbl("f high", "center", _FHIGH_X, "14sp", _DIM_COLOR))
        hdr.add_widget(lbl("(Hz)",   "left",   _PAD_X,   "13sp", _DIM_COLOR))
        outer.add_widget(hdr)

        _MODE_ACTIVE_BG   = (0.25, 0.48, 0.75, 1)
        _MODE_INACTIVE_BG = (0.18, 0.18, 0.21, 1)

        def mode_toggle(mode_state, tip_sigma: str = "", tip_offset: str = "", offset_label: str = "+/−"):
            """Return a BoxLayout with σ× / offset toggle buttons that update mode_state."""
            box  = BoxLayout(spacing=2, size_hint_x=_MODE_X)
            btns: Dict[str, ToggleButton] = {}
            for mk, txt in [("sigma", "σ×"), ("offset", offset_label)]:
                active = mode_state["val"] == mk
                btn = ToggleButton(
                    text=txt, state="down" if active else "normal",
                    background_normal="", background_down="",
                    background_color=_MODE_ACTIVE_BG if active else _MODE_INACTIVE_BG,
                    color=(1, 1, 1, 1), font_size="11sp",
                )
                def _cb(b, ms=mode_state, mk_=mk, bs=btns):
                    ms["val"] = mk_
                    for k_, bb in bs.items():
                        a = k_ == mk_
                        bb.background_color = _MODE_ACTIVE_BG if a else _MODE_INACTIVE_BG
                        bb.state = "down" if a else "normal"
                btn.bind(on_release=_cb)
                btns[mk] = btn
                box.add_widget(btn)
            if tip_sigma:
                self._tips.register(btns["sigma"],  tip_sigma)
            if tip_offset:
                self._tips.register(btns["offset"], tip_offset)
            return box

        _TIP_SIGMA  = "Limit width = value × std deviation (frequency-dependent)."
        _TIP_OFFSET = "Fixed absolute offset — stored as a constant 2-point boundary line."
        _TIP_FLO    = "Lower frequency bound for limit computation [Hz]."
        _TIP_FHI    = "Upper frequency bound for limit computation [Hz]."

        def type_row(display_name, mode_default, val_default, fl_default, fh_default, tip_val: str = "", offset_label: str = "+/−"):
            ms = {"val": mode_default}
            row = BoxLayout(size_hint_y=None, height=_ROW_H, spacing=4)
            row.add_widget(lbl(display_name + ":", "right", _LABEL_X))
            row.add_widget(mode_toggle(ms, tip_sigma=_TIP_SIGMA, tip_offset=_TIP_OFFSET, offset_label=offset_label))
            val_in   = ti(val_default)
            flow_in  = ti(fl_default)
            fhigh_in = ti(fh_default)
            val_in.size_hint_x   = _VAL_X
            flow_in.size_hint_x  = _FLOW_X
            fhigh_in.size_hint_x = _FHIGH_X
            row.add_widget(val_in)
            row.add_widget(flow_in)
            row.add_widget(lbl("–", "center", _SEP_X))
            row.add_widget(fhigh_in)
            row.add_widget(Widget(size_hint_x=_PAD_X))
            if tip_val:
                self._tips.register(val_in,   tip_val)
            self._tips.register(flow_in,  _TIP_FLO)
            self._tips.register(fhigh_in, _TIP_FHI)
            return row, ms, val_in, flow_in, fhigh_in

        rms_row, self._rms_mode, self._rms_val, self._rms_fl, self._rms_fh  = type_row(
            "RMS Level", _s("analysis_rms_mode","sigma"), _s("analysis_rms_val",3),
            _s("analysis_rms_fl",20), _s("analysis_rms_fh",20000),
            tip_val="σ× mode: multiplier × std deviation.  +/− mode: fixed half-width [dBSPL].",
        )
        ph_row,  self._ph_mode,  self._ph_val,  self._ph_fl,  self._ph_fh   = type_row(
            "Phase",     _s("analysis_ph_mode", "sigma"), _s("analysis_ph_val",3),
            _s("analysis_ph_fl",20),  _s("analysis_ph_fh",20000),
            tip_val="σ× mode: multiplier × std deviation.  +/− mode: fixed half-width [deg].",
        )
        thd_row, self._thd_mode, self._thd_val, self._thd_fl, self._thd_fh  = type_row(
            "THD",       _s("analysis_thd_mode","sigma"), _s("analysis_thd_val",3),
            _s("analysis_thd_fl",20),  _s("analysis_thd_fh",20000),
            tip_val="σ× mode: multiplier × std deviation.  + mode: absolute offset [% THD], converted to a frequency-dependent relative factor.",
            offset_label="+",
        )
        outer.add_widget(rms_row)
        outer.add_widget(ph_row)
        outer.add_widget(thd_row)

        # Compute default output path: prefer explicit root_path, fallback to settings_store
        _root = root_path
        if _root is None and settings_store:
            _p = settings_store.get("measurements_root_path", "")
            _root = Path(_p) if _p else None
        _default_out = str((_root / "Analysis_Export") if _root else Path("."))
        self._output_path = Path(_default_out)
        path_row = BoxLayout(size_hint_y=None, height=32, spacing=6)
        path_row.add_widget(lbl("Output path:", "right", 0.22, "12sp"))
        self._path_label = Label(
            text=self._trunc_path(self._output_path),
            halign="left", valign="middle",
            font_size="11sp", color=(0.55, 0.55, 0.60, 1),
        )
        self._path_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        path_row.add_widget(self._path_label)
        browse_btn = Button(
            text="…", size_hint_x=None, width=dp(36),
            background_normal="", background_color=(0.35, 0.35, 0.38, 1),
        )
        browse_btn.bind(on_release=self._browse_output_dir)
        path_row.add_widget(browse_btn)
        outer.add_widget(path_row)
        self._tips.register(
            self._path_label,
            "Folder where reference CSVs, limit CSVs, PNG plots and README.md will be saved.",
        )
        self._tips.register(browse_btn, "Open folder picker to choose the output directory.")

        self._status = Label(text="", size_hint_y=None, height=28,
                             font_size="12sp", color=(0.7, 0.7, 0.7, 1))
        outer.add_widget(self._status)

        outer.add_widget(Widget())  # spacer

        btn_row = BoxLayout(size_hint_y=None, height=42, spacing=8)
        self._cancel_btn = Button(text="Cancel", background_normal="",
                             background_color=(0.35, 0.35, 0.38, 1))
        self._cancel_btn.bind(on_release=lambda *_: self.dismiss())
        self._done_btn = Button(text="Done", background_normal="",
                               background_color=(0.18, 0.55, 0.30, 1),
                               disabled=True, opacity=0.0)
        self._done_btn.bind(on_release=lambda *_: self.dismiss())
        self._gen_btn = Button(text="Generate", background_normal="",
                               background_color=(0.2, 0.55, 0.85, 1))
        self._gen_btn.bind(on_release=self._on_generate)
        btn_row.add_widget(self._cancel_btn)
        btn_row.add_widget(self._done_btn)
        btn_row.add_widget(self._gen_btn)
        outer.add_widget(btn_row)
        self._tips.register(self._gen_btn,
            "Compute median reference curves and statistical limits, then save CSV files, PNG plots and README.")
        self._tips.register(self._done_btn, "Close this dialog.")

    @staticmethod
    def _trunc_path(path: Path, max_chars: int = 52) -> str:
        s = str(path)
        return s if len(s) <= max_chars else "…" + s[-(max_chars - 1):]

    def _on_generate(self, *_) -> None:
        try:
            rms_val  = float(self._rms_val.text.strip())
            rms_fl   = float(self._rms_fl.text.strip())
            rms_fh   = float(self._rms_fh.text.strip())
            ph_val   = float(self._ph_val.text.strip())
            ph_fl    = float(self._ph_fl.text.strip())
            ph_fh    = float(self._ph_fh.text.strip())
            thd_val  = float(self._thd_val.text.strip())
            thd_fl   = float(self._thd_fl.text.strip())
            thd_fh   = float(self._thd_fh.text.strip())
        except ValueError:
            self._status.text  = "Invalid input — please use numbers."
            self._status.color = (1, 0.45, 0.45, 1)
            return
        n_smo    = self._smooth_n_map[self._smooth_spinner.text]
        rms_mode  = self._rms_mode["val"]
        ph_mode   = self._ph_mode["val"]
        thd_mode  = self._thd_mode["val"]

        opts = AnalysisOptions(
            reference_type = self._ref_type,
            lr_diff_source = self._lr_source,
            use_comp       = self._use_comp,
            smooth_n       = n_smo,
            rms_mode=rms_mode,   rms_value=rms_val,   rms_f_low=rms_fl,   rms_f_high=rms_fh,
            phase_mode=ph_mode,  phase_value=ph_val,  phase_f_low=ph_fl,  phase_f_high=ph_fh,
            thd_mode=thd_mode,   thd_value=thd_val,   thd_f_low=thd_fl,   thd_f_high=thd_fh,
        )
        if self._store:
            self._store.set("analysis_ref_type",   self._ref_type)
            self._store.set("analysis_lr_source",  self._lr_source)
            self._store.set("analysis_use_comp",   "true" if self._use_comp else "false")
            self._store.set("analysis_smooth_n",   self._smooth_spinner.text)
            self._store.set("analysis_rms_mode",   rms_mode)
            self._store.set("analysis_rms_val",    str(rms_val))
            self._store.set("analysis_rms_fl",     str(rms_fl))
            self._store.set("analysis_rms_fh",     str(rms_fh))
            self._store.set("analysis_ph_mode",    ph_mode)
            self._store.set("analysis_ph_val",     str(ph_val))
            self._store.set("analysis_ph_fl",      str(ph_fl))
            self._store.set("analysis_ph_fh",      str(ph_fh))
            self._store.set("analysis_thd_mode",   thd_mode)
            self._store.set("analysis_thd_val",    str(thd_val))
            self._store.set("analysis_thd_fl",     str(thd_fl))
            self._store.set("analysis_thd_fh",     str(thd_fh))
        self._gen_btn.disabled = True
        self._status.text  = "Computing…"
        self._status.color = (0.8, 0.8, 0.5, 1)
        Clock.schedule_once(lambda _dt: self._run(opts), 0.05)

    def _browse_output_dir(self, *_) -> None:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(
            initialdir=str(self._output_path),
            title="Speicherordner wählen",
        )
        root.destroy()
        if folder:
            self._output_path = Path(folder)
            self._path_label.text = self._trunc_path(self._output_path)

    def _run(self, opts: AnalysisOptions) -> None:
        success = False
        try:
            msg = run_analysis(opts, self._runs, self._lr_diff,
                               self._output_path, category=self._category)
            self._status.text  = msg
            self._status.color = (0.5, 0.9, 0.5, 1)
            success = True
        except Exception as exc:
            self._status.text  = f"Error: {exc}"
            self._status.color = (1, 0.45, 0.45, 1)
        finally:
            self._gen_btn.disabled = False
        if success:
            self._done_btn.disabled = False
            self._done_btn.opacity  = 1.0
            self._cancel_btn.opacity = 0.0
            self._cancel_btn.disabled = True
        if self._on_done:
            self._on_done(self._status.text)


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
        self._current_category: Optional[str] = None
        self._current_runs: List[MeasurementFile] = []

        root_path_str = settings_store.get("measurements_root_path", "")
        self.root_path = Path(root_path_str) if root_path_str else None
        self._lr_diff_data = (
            _load_lr_diff(self.root_path / "References" / "L-R-Diff.csv")
            if self.root_path else None
        )

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
        self._analyze_btn = Button(
            text="Create Refs...",
            background_normal="",
            background_color=(0.28, 0.45, 0.25, 1),
            size_hint_x=None,
            width=dp(100),
            disabled=True,
            opacity=0.4,
        )
        self._analyze_btn.bind(on_release=lambda *_: self._open_analysis_dialog())
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
        toolbar.add_widget(self._analyze_btn)
        toolbar.add_widget(self._info_label)
        self.add_widget(toolbar)

        self._tips = _DelayedTooltipManager(delay=0.6)
        self._tips.register(select_btn, "Choose a product category and result folders to load.")
        self._tips.register(self._analyze_btn, "Open the dialog to generate reference curves and limit files.")
        if on_back is not None:
            self._tips.register(back_btn, "Return to the home screen.")

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
            self._lr_diff_data = (
                _load_lr_diff(self.root_path / "References" / "L-R-Diff.csv")
                if self.root_path else None
            )
            if self._chart:
                self._chart.set_lr_diff(self._lr_diff_data)
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
        self._chart.set_lr_diff(self._lr_diff_data)
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

        self._current_category = category
        self._current_runs = runs
        self._analyze_btn.disabled = False
        self._analyze_btn.opacity = 1.0

        self._show_chart()
        self._chart.set_cat_refs(
            _load_category_refs(self.root_path, category) if self.root_path else None
        )
        self._chart.load_data(runs)

        serials = len({r.serial for r in runs})
        timestamps = len({(r.serial, r.timestamp) for r in runs})
        folder_names = ", ".join(p.name for p in folder_paths)
        self._info_label.text = (
            f"{category}  ·  {folder_names}  ·  {serials} serial{'s' if serials != 1 else ''}  ·  {timestamps} run{'s' if timestamps != 1 else ''}"
        )

    def _open_analysis_dialog(self) -> None:
        if not self._current_runs:
            return
        AnalysisDialog(
            runs=self._current_runs,
            lr_diff_existing=self._lr_diff_data,
            root_path=self.root_path,
            category=self._current_category or "",
            settings_store=self.settings_store,
            on_done=self._on_analysis_done,
        ).open()

    def _on_analysis_done(self, msg: str) -> None:
        # Reload cat_refs so freshly written files are picked up immediately
        if self.root_path and self._current_category:
            self._chart.set_cat_refs(
                _load_category_refs(self.root_path, self._current_category)
            )
            self._lr_diff_data = _load_lr_diff(
                self.root_path / "References" / self._current_category / "L-R-Diff.csv"
            ) or _load_lr_diff(
                self.root_path / "References" / "L-R-Diff.csv"
            )
            self._chart.set_lr_diff(self._lr_diff_data)
            self._chart.load_data(self._current_runs)
