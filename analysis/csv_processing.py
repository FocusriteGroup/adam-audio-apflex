"""
csv_processing.py

CSV processing utilities for ADAM Audio analysis workflows.
"""

import csv
import logging
import math
import os
from itertools import chain
from typing import Iterable, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)


def _write_rows_with_fallback(output_path: str, rows: Iterable[list[str]]) -> str:
    """Write CSV rows and gracefully handle locked target files by using a fallback name."""
    if os.path.isdir(output_path):
        raise IsADirectoryError(f"Output path points to a directory, not a file: {output_path}")

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            for row in rows:
                writer.writerow(row)
        return output_path
    except PermissionError as exc:
        base, ext = os.path.splitext(output_path)
        for index in range(1, 100):
            fallback_path = f"{base}_{index}{ext}"
            if os.path.exists(fallback_path):
                continue

            try:
                with open(fallback_path, "x", newline="", encoding="utf-8") as output_file:
                    writer = csv.writer(output_file)
                    for row in rows:
                        writer.writerow(row)
                return fallback_path
            except PermissionError:
                continue

        raise PermissionError(
            f"Unable to write output CSV. Target may be locked or not writable: {output_path}"
        ) from exc


def extract_csv_columns(
    input_path: str,
    columns: Iterable[int],
    output_filename: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Extract columns from a CSV and write a new CSV file.

    Skips the first row and copies only the requested column indices from row 2 onward.

    Args:
        input_path: Path to the source CSV file.
        columns: Iterable of zero-based column indices to extract.
        output_filename: Filename for the output CSV file.
        output_dir: Output directory. Defaults to the input file's directory.

    Returns:
        Path to the written CSV file.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    if not output_filename:
        raise ValueError("output_filename must be provided")

    output_base = output_dir if output_dir else os.path.dirname(os.path.abspath(input_path))
    os.makedirs(output_base, exist_ok=True)
    output_path = os.path.join(output_base, output_filename)

    selected = list(columns)
    if not selected:
        raise ValueError("columns must contain at least one column index")
    if any(not isinstance(index, int) or index < 0 for index in selected):
        raise ValueError("columns must contain only non-negative integer indices")

    with open(input_path, "r", newline="", encoding="utf-8") as source_file:
        reader = csv.reader(source_file)
        skipped_row = next(reader, None)
        if skipped_row is None:
            raise ValueError("Input CSV is empty")

        first_element = skipped_row[0] if skipped_row else ""
        prepended_row = [first_element] + ["" for _ in selected[1:]]
        extracted_rows = ([row[idx] if idx < len(row) else "" for idx in selected] for row in reader)
        rows = chain([prepended_row], extracted_rows)
        written_path = _write_rows_with_fallback(output_path, rows)

    return written_path


def octave_smooth(
    frequencies: list[float],
    values_db: list[float],
    fraction: int = 3,
) -> list[float]:
    """
    Apply 1/n-octave smoothing to frequency-domain data.

    Smoothing is performed in the linear amplitude domain (Pa) to be
    physically correct, then converted back to dB.

    For each output point at frequency f the window covers:
        [f / 2^(1 / (2*fraction)),  f * 2^(1 / (2*fraction))]

    Args:
        frequencies: Frequency values in Hz (must be positive and sorted ascending).
        values_db:   Corresponding amplitude values in dBSPL.
        fraction:    Octave fraction denominator — e.g. 3 for 1/3 octave,
                     6 for 1/6 octave, 12 for 1/12 octave.

    Returns:
        Smoothed dBSPL values (same length as input).

    Raises:
        ValueError: If inputs have different lengths, are empty, or fraction < 1.
    """
    if len(frequencies) != len(values_db):
        raise ValueError("frequencies and values_db must have the same length.")
    if not frequencies:
        raise ValueError("Input arrays must not be empty.")
    if fraction < 1:
        raise ValueError("fraction must be >= 1.")

    # dBSPL → linear pressure (Pa): p = 10^(dBSPL / 20)
    linear = [10.0 ** (db / 20.0) for db in values_db]

    half_width = 2.0 ** (1.0 / (2.0 * fraction))
    smoothed_db: list[float] = []

    for freq in frequencies:
        f_low = freq / half_width
        f_high = freq * half_width
        window = [
            lin
            for f, lin in zip(frequencies, linear)
            if f_low <= f <= f_high
        ]
        mean_linear = sum(window) / len(window)
        smoothed_db.append(20.0 * math.log10(mean_linear))

    return smoothed_db


_AP_NUM_HEADER_ROWS = 4


def octave_smooth_ap_csv(
    input_path: str,
    fraction: int = 3,
    output_filename: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """
    Apply 1/n-octave smoothing to all Y columns in an AP measurement CSV.

    Reads a file in the standard AP format (4 header rows, then X/Y pairs),
    smooths every Y (dBSPL) column independently, and writes a new CSV.

    Args:
        input_path:      Path to the source AP CSV file.
        fraction:        Octave fraction denominator (default: 3 → 1/3 octave).
        output_filename: Output filename. Defaults to
                         ``<stem>_smooth<fraction>.csv``.
        output_dir:      Output directory. Defaults to the input file's directory.

    Returns:
        Path to the written CSV file.

    Raises:
        FileNotFoundError: If input_path does not exist.
        ValueError:        If fraction < 1 or the file has no data rows.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    if fraction < 1:
        raise ValueError("fraction must be >= 1.")

    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    if len(all_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError("Input CSV has no data rows after the header.")

    header_rows = all_rows[:_AP_NUM_HEADER_ROWS]
    data_rows = all_rows[_AP_NUM_HEADER_ROWS:]

    num_cols = max(len(row) for row in data_rows)

    # Parse all columns; X cols = even indices (0, 2, …), Y cols = odd (1, 3, …)
    columns: list[list[float]] = []
    for col_idx in range(num_cols):
        col_values: list[float] = []
        for row in data_rows:
            raw = row[col_idx].strip() if col_idx < len(row) else ""
            try:
                col_values.append(float(raw))
            except ValueError:
                col_values.append(float("nan"))
        columns.append(col_values)

    # Extract X columns (frequencies) to find the right X for each Y
    # Y columns are at odd indices; the corresponding X is at index - 1
    smoothed_columns = list(columns)  # shallow copy, we'll replace Y cols
    for col_idx in range(1, num_cols, 2):  # odd = Y
        x_idx = col_idx - 1
        frequencies = columns[x_idx]
        values_db = columns[col_idx]

        # Filter out NaN pairs before smoothing
        valid_pairs = [
            (f, v)
            for f, v in zip(frequencies, values_db)
            if not (math.isnan(f) or math.isnan(v))
        ]
        if not valid_pairs:
            continue
        valid_freqs, valid_vals = zip(*valid_pairs)
        smoothed = octave_smooth(list(valid_freqs), list(valid_vals), fraction)

        # Put smoothed values back (NaN positions remain NaN)
        smoothed_iter = iter(smoothed)
        new_col: list[float] = []
        for v in values_db:
            if math.isnan(v):
                new_col.append(float("nan"))
            else:
                new_col.append(next(smoothed_iter))
        smoothed_columns[col_idx] = new_col

    # Rebuild rows
    def _fmt(v: float) -> str:
        return "" if math.isnan(v) else repr(v)

    smoothed_data_rows = [
        [_fmt(smoothed_columns[col_idx][row_idx]) for col_idx in range(num_cols)]
        for row_idx in range(len(data_rows))
    ]

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    if output_filename is None:
        output_filename = f"{base_name}_smooth{fraction}.csv"

    output_base = output_dir if output_dir else os.path.dirname(os.path.abspath(input_path))
    os.makedirs(output_base, exist_ok=True)
    output_path = os.path.join(output_base, output_filename)

    all_output_rows = header_rows + smoothed_data_rows
    return _write_rows_with_fallback(output_path, all_output_rows)


_AP_DISTORTION_METRICS = ["F", "H2", "H3", "Total"]
_AP_COLS_PER_CURVE = 2
_AP_CURVES_PER_CHANNEL = 4
_AP_COLS_PER_CHANNEL = _AP_COLS_PER_CURVE * _AP_CURVES_PER_CHANNEL  # 8


def split_ap_distortion_csv(
    input_path: str,
    output_dir: Optional[str] = None,
    fraction: Optional[int] = None,
    output_prefix: Optional[str] = None,
) -> dict[str, str]:
    """
    Split an Audio Precision Level & Distortion CSV into per-metric files.

    The AP format has 4 header rows:
      Row 1: Measurement name
      Row 2: Curve descriptions, e.g. Left-Left(F),, Left-Left(H2),, ...
      Row 3: X/Y roles
      Row 4: Units (Hz, dBSPL, ...)
      Row 5+: Numeric data

    Within each channel block of 8 columns the order is always:
      F (cols 0-1), H2 (cols 2-3), H3 (cols 4-5), Total (cols 6-7)

    Detects the number of channels automatically from the non-empty entries
    in Row 2 (must be a multiple of 4).

    Args:
        input_path:    Path to the source AP measurement CSV file.
        output_dir:    Output directory. Defaults to the input file's directory.
        fraction:      If provided, applies 1/n-octave smoothing to every output
                       file after extraction (e.g. 3 for 1/3 octave).
                       If None (default), no smoothing is applied.
        output_prefix: Base name for output files. Defaults to the input file stem.

    Returns:
        Dict mapping metric name to written output file path,
        e.g. {"F": "/path/name_F.csv", "H2": ..., "H3": ..., "Total": ...}

    Raises:
        FileNotFoundError: If input_path does not exist.
        ValueError: If the curve count in Row 2 is not a multiple of 4,
                    or fraction < 1 when provided.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    if fraction is not None and fraction < 1:
        raise ValueError("fraction must be >= 1.")

    # Detect channel count from Row 2
    with open(input_path, "r", newline="", encoding="utf-8") as source_file:
        reader = csv.reader(source_file)
        next(reader, None)  # skip Row 1 (measurement name)
        header_row = next(reader, [])

    curve_names = [cell.strip() for cell in header_row if cell.strip()]
    num_curves = len(curve_names)
    if num_curves == 0 or num_curves % _AP_CURVES_PER_CHANNEL != 0:
        raise ValueError(
            f"Expected a multiple of {_AP_CURVES_PER_CHANNEL} curves in Row 2, "
            f"got {num_curves}: {curve_names}"
        )
    num_channels = num_curves // _AP_CURVES_PER_CHANNEL

    base_name = output_prefix if output_prefix else os.path.splitext(os.path.basename(input_path))[0]

    results: dict[str, str] = {}
    for metric_index, metric in enumerate(_AP_DISTORTION_METRICS):
        # Collect X/Y column pairs for this metric across all channels
        columns: list[int] = []
        for ch in range(num_channels):
            base_col = ch * _AP_COLS_PER_CHANNEL + metric_index * _AP_COLS_PER_CURVE
            columns.extend([base_col, base_col + 1])

        output_filename = f"{base_name}_{metric}.csv"
        written_path = extract_csv_columns(input_path, columns, output_filename, output_dir)
        if fraction is not None:
            written_path = octave_smooth_ap_csv(
                input_path=written_path,
                fraction=fraction,
                output_filename=output_filename,  # overwrite same file
                output_dir=output_dir,
            )
        results[metric] = written_path

    return results


def merge_ap_distortion_csvs(
    input_paths: list[str],
    output_dir: Optional[str] = None,
    fraction: Optional[int] = None,
    output_prefix: Optional[str] = None,
) -> dict[str, str]:
    """
    Merge multiple AP Level & Distortion CSV files into per-metric combined files.

    For each metric (F, H2, H3, Total) the corresponding columns from all input
    files are placed side-by-side in a single output file.  Each input file may
    contain one or more channels; all channels of all files are collected into
    the respective metric output.

    Args:
        input_paths:   List of at least 2 source AP CSV file paths.
        output_dir:    Output directory.  Defaults to the directory of the first
                       input file.
        fraction:      If provided, apply 1/n-octave smoothing to every output
                       file after merging (e.g. 3 = 1/3 octave).
        output_prefix: Base name for output files.  Defaults to the longest
                       common prefix of all input file stems (trimmed of
                       trailing ``_`` / ``-`` / space).

    Returns:
        Dict mapping metric name to output file path,
        e.g. ``{"F": "/path/prefix_F.csv", "H2": ..., "H3": ..., "Total": ...}``

    Raises:
        FileNotFoundError: If any input path does not exist.
        ValueError:        If fewer than 2 paths are given, any file has an
                           invalid curve count in Row 2, or fraction < 1.
    """
    if len(input_paths) < 2:
        raise ValueError("At least 2 input paths are required.")
    if fraction is not None and fraction < 1:
        raise ValueError("fraction must be >= 1.")

    # Read all files into memory
    all_rows: list[list[list[str]]] = []
    for path in input_paths:
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"Input CSV not found: {path}")
        with open(path, "r", newline="", encoding="utf-8") as f:
            all_rows.append(list(csv.reader(f)))

    def _metric_cols(rows: list[list[str]], metric_idx: int) -> list[int]:
        """Return the column indices for *metric_idx* across all channels of *rows*."""
        header_row = rows[1]  # Row 2 (0-indexed)
        num_curves = sum(1 for v in header_row if v.strip())
        if num_curves == 0 or num_curves % _AP_CURVES_PER_CHANNEL != 0:
            raise ValueError(
                f"Expected a multiple of {_AP_CURVES_PER_CHANNEL} curves in Row 2, "
                f"got {num_curves}."
            )
        num_channels = num_curves // _AP_CURVES_PER_CHANNEL
        cols: list[int] = []
        for ch in range(num_channels):
            base = ch * _AP_COLS_PER_CHANNEL + metric_idx * _AP_COLS_PER_CURVE
            cols.extend([base, base + 1])
        return cols

    # Derive output prefix from common stem if not supplied
    if output_prefix is None:
        stems = [os.path.splitext(os.path.basename(p))[0] for p in input_paths]
        common = stems[0]
        for stem in stems[1:]:
            # Shorten common until stem starts with it
            while common and not stem.startswith(common):
                common = common[:-1]
        stripped = common.rstrip("_- ")
        if stripped.lower().endswith("_ch"):
            stripped = stripped[:-3].rstrip("_- ")
        output_prefix = stripped or "merged"

    output_base = output_dir if output_dir else os.path.dirname(os.path.abspath(input_paths[0]))
    os.makedirs(output_base, exist_ok=True)

    results: dict[str, str] = {}
    for metric_idx, metric in enumerate(_AP_DISTORTION_METRICS):
        file_cols = [_metric_cols(rows, metric_idx) for rows in all_rows]
        num_rows = max(len(rows) for rows in all_rows)

        merged: list[list[str]] = []
        for row_i in range(num_rows):
            merged_row: list[str] = []
            for file_idx, rows in enumerate(all_rows):
                cols = file_cols[file_idx]
                if row_i < len(rows):
                    row = rows[row_i]
                    merged_row.extend(row[c] if c < len(row) else "" for c in cols)
                else:
                    merged_row.extend("" for _ in cols)
            merged.append(merged_row)

        output_filename = f"{output_prefix}_{metric}.csv"
        output_path = os.path.join(output_base, output_filename)
        written_path = _write_rows_with_fallback(output_path, merged)

        if fraction is not None:
            written_path = octave_smooth_ap_csv(
                input_path=written_path,
                fraction=fraction,
                output_filename=output_filename,  # overwrite same file
                output_dir=output_base,
            )

        results[metric] = written_path

    return results


def _apply_limits_offset(
    ref_value: float,
    limit_value: float,
    ref_unit: str,
    limit_unit: str,
) -> float:
    """
    Apply limits offset to reference value with unit conversion.
    
    Args:
        ref_value: Reference value (in ref_unit).
        limit_value: Limits offset value (in limit_unit).
        ref_unit: Unit of reference value ("dB", "dBSPL", or "%").
        limit_unit: Unit of limits value ("dB" or "%").
    
    Returns:
        New value with offset applied (in ref_unit).
    
    Notes:
        - dB + dB → addition: ref_value + limit_value
        - dB + % → convert % to dB, then add: ref_value + 20*log10(1 + limit%/100)
        - % + % → multiply factors: ref_value * (1 + limit%/100)
        - % + dB → convert dB to factor: ref_value * 10^(limit_dB/20)
    """
    import math
    
    # Normalize units (dBSPL is treated as dB)
    ref_is_db = ref_unit.upper() in ("DB", "DBSPL")
    ref_is_percent = ref_unit == "%"
    
    limit_is_db = limit_unit.upper() in ("DB", "DBSPL")
    limit_is_percent = limit_unit == "%"
    
    if ref_is_db and limit_is_db:
        # dB + dB → simple addition
        return ref_value + limit_value
    
    elif ref_is_db and limit_is_percent:
        # dB + % → convert % to dB, then add
        factor = 1 + limit_value / 100
        if factor <= 0:
            return float('-inf')  # Avoid log of non-positive
        dB_change = 20 * math.log10(factor)
        return ref_value + dB_change
    
    elif ref_is_percent and limit_is_percent:
        # % + % → multiply factors
        return ref_value * (1 + limit_value / 100)
    
    elif ref_is_percent and limit_is_db:
        # % + dB → convert dB to factor, then multiply
        factor = 10 ** (limit_value / 20)
        return ref_value * factor
    
    else:
        raise ValueError(f"Unsupported unit combination: ref={ref_unit}, limit={limit_unit}")


def _interpolate_reference_frequencies(
    ref_frequencies: list[float],
    ref_values: list[list[float]],
    target_frequencies: list[float],
    num_channels: int,
) -> list[list[str]]:
    """
    Interpolate reference values at target frequencies using logarithmic-linear interpolation.
    
    Args:
        ref_frequencies: Original reference frequencies (Hz).
        ref_values: List of value arrays, one per column (X,Y for each channel).
        target_frequencies: Target frequencies to interpolate at (from limits CSV).
        num_channels: Number of channels (1 for mono, 2 for stereo).
    
    Returns:
        List of rows with interpolated values as strings.
    """
    import numpy as np
    
    # Convert to numpy arrays
    ref_freq_array = np.array(ref_frequencies)
    log_ref_freq = np.log10(ref_freq_array)
    log_target_freq = np.log10(target_frequencies)
    
    interpolated_rows: list[list[str]] = []
    
    for target_freq, log_target in zip(target_frequencies, log_target_freq):
        row_data: list[str] = []
        
        # Process each column (X,Y for each channel)
        for col_idx in range(num_channels * 2):
            if col_idx % 2 == 0:
                # X column (frequency) - use target frequency
                row_data.append(str(target_freq))
            else:
                # Y column (dB value) - interpolate
                ref_col_values = np.array(ref_values[col_idx])
                
                # Filter out NaN values for interpolation
                valid_mask = ~np.isnan(ref_col_values)
                if not valid_mask.any():
                    row_data.append("")
                    continue
                
                valid_log_freq = log_ref_freq[valid_mask]
                valid_values = ref_col_values[valid_mask]
                
                # Perform logarithmic-linear interpolation
                # extrapolate with edge values if outside range
                interpolated = np.interp(log_target, valid_log_freq, valid_values)
                row_data.append(str(interpolated))
        
        interpolated_rows.append(row_data)
    
    return interpolated_rows


def _interpolate_limits_values(
    limits_frequencies: list[float],
    limits_values: list[float],
    target_frequencies: list[float],
) -> list[float]:
    """
    Interpolate limits values at target frequencies using logarithmic-linear interpolation.
    
    Args:
        limits_frequencies: Original limits frequencies (Hz).
        limits_values: Limits Y-values (dB or %).
        target_frequencies: Target frequencies to interpolate at.
    
    Returns:
        Interpolated limits values at target frequencies.
    """
    import numpy as np
    
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy is required for limits interpolation")
    
    # Convert to numpy arrays
    limits_freq_array = np.array(limits_frequencies)
    log_limits_freq = np.log10(limits_freq_array)
    log_target_freq = np.log10(target_frequencies)
    
    # Filter out NaN values
    valid_mask = ~np.isnan(limits_values)
    if not valid_mask.any():
        return [float('nan')] * len(target_frequencies)
    
    valid_log_freq = log_limits_freq[valid_mask]
    valid_values = np.array(limits_values)[valid_mask]
    
    # Perform logarithmic-linear interpolation
    interpolated = np.interp(log_target_freq, valid_log_freq, valid_values)
    
    return interpolated.tolist()


def filter_reference_by_limits(
    reference_path: str,
    limits_path: str,
    output_filename: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """
    Filter a reference measurement CSV and apply limits as offset to create absolute limits.

    Takes a reference measurement (e.g., 100 dBSPL) and applies limits offsets (e.g., +3 dB)
    to create absolute limit values (e.g., 103 dBSPL). Handles unit conversion between
    dB/dBSPL and % according to Audio Precision conventions.

    Process:
    1. Extract frequency range from limits CSV (min to max frequency)
    2. Filter reference to only include frequencies within that range
    3. Interpolate missing limits frequencies into reference (if needed)
    4. Apply limits offsets to reference Y-values with unit conversion
    5. Output contains reference values + limits offsets in reference units

    Unit Conversion Logic:
    - dB + dB → addition: new_value = ref + limit
    - dB + % → convert % to dB: new_value = ref + 20*log10(1 + limit%/100)
    - % + % → multiply factors: new_value = ref * (1 + limit%/100)
    - % + dB → convert dB to factor: new_value = ref * 10^(limit_dB/20)

    Args:
        reference_path: Path to the reference measurement CSV (can be stereo or mono).
        limits_path:    Path to the limits CSV (mono, defines frequency ranges and offsets).
        output_filename: Output filename. Defaults to ``<ref_stem>_filtered.csv``.
        output_dir:      Output directory. Defaults to the reference file's directory.

    Returns:
        Path to the written output CSV file.

    Raises:
        FileNotFoundError: If reference_path or limits_path does not exist.
        ValueError:        If CSV format is invalid or no data rows remain after filtering.

    Notes:
        - Both CSVs must have 4 header rows (Audio Precision format).
        - Reference can be stereo (X,Y,X,Y) or mono (X,Y) format.
        - Limits CSV is always mono (X,Y) with relative offset values.
        - Frequency ranges are determined by min/max limits frequency.
        - Requires numpy for interpolation and offset calculations.
    """
    if not reference_path or not os.path.isfile(reference_path):
        raise FileNotFoundError(f"Reference CSV not found: {reference_path}")
    if not limits_path or not os.path.isfile(limits_path):
        raise FileNotFoundError(f"Limits CSV not found: {limits_path}")

    # Read limits CSV and extract frequency ranges and Y-values
    with open(limits_path, "r", newline="", encoding="utf-8") as f:
        limits_reader = csv.reader(f)
        limits_rows = list(limits_reader)

    if len(limits_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError("Limits CSV has no data rows after the header.")

    limits_header_rows = limits_rows[:_AP_NUM_HEADER_ROWS]
    limits_data_rows = limits_rows[_AP_NUM_HEADER_ROWS:]
    
    # Extract units from limits header (row 4, index 3)
    limits_units_row = limits_header_rows[3] if len(limits_header_rows) > 3 else []
    limits_y_unit = limits_units_row[1].strip() if len(limits_units_row) > 1 else "dB"
    
    # Extract frequency and Y values from limits (column 0 = X = Hz, column 1 = Y)
    limit_frequencies: list[float] = []
    limit_y_values: list[float] = []
    for row in limits_data_rows:
        if row and row[0].strip():
            try:
                freq = float(row[0])
                y_val = float(row[1]) if len(row) > 1 and row[1].strip() else float('nan')
                limit_frequencies.append(freq)
                limit_y_values.append(y_val)
            except ValueError:
                continue

    if not limit_frequencies:
        raise ValueError("No valid frequency values found in limits CSV.")

    # Sort frequencies and corresponding Y-values
    freq_y_pairs = list(zip(limit_frequencies, limit_y_values))
    freq_y_pairs.sort(key=lambda x: x[0])
    limit_frequencies = [f for f, _ in freq_y_pairs]
    limit_y_values = [y for _, y in freq_y_pairs]
    
    logger.info(f"Loaded {len(limit_frequencies)} frequency points from limits CSV")

    # Define frequency range from min to max limits frequency (no gaps)
    freq_min = min(limit_frequencies)
    freq_max = max(limit_frequencies)
    
    logger.info(f"Limits frequency range: [{freq_min:.1f}-{freq_max:.1f}] Hz")

    # Read reference CSV
    with open(reference_path, "r", newline="", encoding="utf-8") as f:
        ref_reader = csv.reader(f)
        ref_rows = list(ref_reader)

    if len(ref_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError("Reference CSV has no data rows after the header.")

    ref_header_rows = ref_rows[:_AP_NUM_HEADER_ROWS]
    ref_data_rows = ref_rows[_AP_NUM_HEADER_ROWS:]

    # Extract units from reference header (row 4, index 3)
    ref_units_row = ref_header_rows[3] if len(ref_header_rows) > 3 else []
    ref_y_unit = ref_units_row[1].strip() if len(ref_units_row) > 1 else "dBSPL"
    
    logger.info(f"Reference Y-unit: {ref_y_unit}, Limits Y-unit: {limits_y_unit}")

    # Detect if reference is stereo or mono by checking number of non-empty columns in header row 3
    # Header row 3 (index 2) contains X,Y or X,Y,X,Y
    header_row_3 = ref_header_rows[2] if len(ref_header_rows) > 2 else []
    num_channels = sum(1 for i, val in enumerate(header_row_3) if i % 2 == 0 and val.strip())
    
    ref_type = "Stereo" if num_channels > 1 else "Mono"
    logger.info(f"Reference type: {ref_type} ({num_channels} channel(s))")

    # Parse reference data into structured format
    ref_frequencies: list[float] = []
    ref_values: list[list[float]] = [[] for _ in range(num_channels * 2)]  # X,Y for each channel
    
    for row in ref_data_rows:
        if not row or not row[0].strip():
            continue
        
        try:
            freq = float(row[0])
            ref_frequencies.append(freq)
            
            # Parse all column values
            for col_idx in range(min(len(row), num_channels * 2)):
                try:
                    val = float(row[col_idx]) if row[col_idx].strip() else float('nan')
                    ref_values[col_idx].append(val)
                except (ValueError, IndexError):
                    ref_values[col_idx].append(float('nan'))
        except ValueError:
            continue

    if not ref_frequencies:
        raise ValueError("No valid frequency data found in reference CSV.")
    
    logger.info(f"Loaded {len(ref_frequencies)} frequency points from reference CSV")

    # Step 1: Filter reference data rows to include only frequencies within limits range
    filtered_frequencies: list[float] = []
    filtered_data_rows: list[list[str]] = []
    
    for i, freq in enumerate(ref_frequencies):
        # Check if frequency falls within the limits range
        if freq_min <= freq <= freq_max:
            filtered_frequencies.append(freq)
            row_data = []
            for col_idx in range(num_channels * 2):
                val = ref_values[col_idx][i]
                row_data.append("" if math.isnan(val) else str(val))
            filtered_data_rows.append(row_data)
    
    logger.info(f"Filtered to {len(filtered_data_rows)} frequency points from reference")

    # Step 2: Check if limits frequencies need to be added via interpolation
    # Find limits frequencies that are NOT already in the filtered reference
    missing_limit_freqs = [freq for freq in limit_frequencies if freq not in filtered_frequencies]
    
    if missing_limit_freqs:
        if not NUMPY_AVAILABLE:
            logger.warning(
                f"{len(missing_limit_freqs)} limits frequencies are missing from reference but cannot be interpolated "
                f"(numpy not available). Continuing with existing frequencies only."
            )
        else:
            logger.info(
                f"Interpolating {len(missing_limit_freqs)} missing limits frequencies: "
                f"{[f'{f:.1f}' for f in missing_limit_freqs[:5]]}{'...' if len(missing_limit_freqs) > 5 else ''}"
            )
            
            # Interpolate missing limits frequencies
            interpolated_rows = _interpolate_reference_frequencies(
                ref_frequencies,
                ref_values,
                missing_limit_freqs,
                num_channels
            )
            
            # Add interpolated rows to filtered data
            for i, interp_row in enumerate(interpolated_rows):
                filtered_frequencies.append(missing_limit_freqs[i])
                filtered_data_rows.append(interp_row)
            
            logger.info(f"Added {len(interpolated_rows)} interpolated frequency points")
    
    # Step 3: Sort all rows by frequency
    if filtered_data_rows:
        # Create list of (frequency, row) tuples, sort by frequency, then extract rows
        freq_row_pairs = list(zip(filtered_frequencies, filtered_data_rows))
        freq_row_pairs.sort(key=lambda x: x[0])
        filtered_frequencies = [freq for freq, _ in freq_row_pairs]
        filtered_data_rows = [row for _, row in freq_row_pairs]
        
        logger.info(f"Total output frequencies: {len(filtered_data_rows)} (sorted by frequency)")
    else:
        raise ValueError(
            f"No frequencies in reference CSV fall within limits range: [{freq_min:.1f}-{freq_max:.1f}] Hz."
        )

    # Step 4: Apply limits as offset to reference Y-values
    # Interpolate limits Y-values for all output frequencies
    if not NUMPY_AVAILABLE:
        logger.warning("numpy not available - cannot apply limits offset. Output will contain reference values only.")
        limits_at_output_freq = [float('nan')] * len(filtered_frequencies)
    else:
        limits_at_output_freq = _interpolate_limits_values(
            limit_frequencies,
            limit_y_values,
            filtered_frequencies
        )
        logger.info(f"Interpolated limits values for {len(filtered_frequencies)} output frequencies")
    
    # Apply offset to each Y-value in filtered_data_rows
    for row_idx, row in enumerate(filtered_data_rows):
        limit_offset = limits_at_output_freq[row_idx]
        
        # Skip if limits value is NaN
        if math.isnan(limit_offset):
            continue
        
        # Apply offset to each Y column (every odd column index)
        for col_idx in range(len(row)):
            if col_idx % 2 == 1:  # Y columns only
                if row[col_idx].strip():
                    try:
                        ref_y_value = float(row[col_idx])
                        new_y_value = _apply_limits_offset(
                            ref_y_value,
                            limit_offset,
                            ref_y_unit,
                            limits_y_unit
                        )
                        row[col_idx] = str(new_y_value)
                    except (ValueError, ArithmeticError) as e:
                        logger.warning(f"Could not apply offset at row {row_idx}, col {col_idx}: {e}")
                        continue
    
    logger.info(f"Applied limits offset to all Y-values (ref unit: {ref_y_unit}, limit unit: {limits_y_unit})")

    # Prepare output
    base_name = os.path.splitext(os.path.basename(reference_path))[0]
    if output_filename is None:
        output_filename = f"{base_name}_filtered.csv"

    output_base = output_dir if output_dir else os.path.dirname(os.path.abspath(reference_path))
    os.makedirs(output_base, exist_ok=True)
    output_path = os.path.join(output_base, output_filename)

    # Write filtered CSV
    all_output_rows = ref_header_rows + filtered_data_rows
    written_path = _write_rows_with_fallback(output_path, all_output_rows)
    
    logger.info(f"Output written to: {written_path}")
    
    return written_path


def compensate_lr_diff(
    input_path: str,
    diff_path: str,
    output_path: str,
    freq_tolerance: float = 1e-3,
) -> str:
    """
    Compensate left/right channel imbalance in a stereo AP RMS measurement CSV.

    For each frequency point::

        L_new = L + 0.5 * diff
        R_new = R - 0.5 * diff

    where ``diff`` comes from a mono AP CSV (e.g. an L-R difference reference
    captured with a known good driver pair).

    Args:
        input_path:     Stereo AP measurement CSV (4 header rows, then ``X,Y,X,Y``).
        diff_path:      Mono AP CSV with the L-R difference (4 header rows, then ``X,Y``).
        output_path:    Destination CSV path. Parent directories are created if needed.
        freq_tolerance: Allowed absolute mismatch (Hz) between input and diff frequency grids.

    Returns:
        The actual written path (may differ from ``output_path`` if the target is locked).

    Raises:
        FileNotFoundError: If either input file is missing.
        ValueError:        If the input is not stereo, the diff is not mono, the row counts
                           differ, or any frequency pair exceeds ``freq_tolerance``.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    if not diff_path or not os.path.isfile(diff_path):
        raise FileNotFoundError(f"Diff CSV not found: {diff_path}")
    if not output_path:
        raise ValueError("output_path must be provided")

    with open(input_path, "r", newline="", encoding="utf-8-sig") as f:
        in_rows = list(csv.reader(f))
    with open(diff_path, "r", newline="", encoding="utf-8-sig") as f:
        diff_rows = list(csv.reader(f))

    if len(in_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError("Input CSV has no data rows after the header.")
    if len(diff_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError("Diff CSV has no data rows after the header.")

    in_header = in_rows[:_AP_NUM_HEADER_ROWS]
    in_data = in_rows[_AP_NUM_HEADER_ROWS:]
    diff_data = diff_rows[_AP_NUM_HEADER_ROWS:]

    # Sanity-check stereo layout on the input (X,Y,X,Y).
    if not in_data or len(in_data[0]) < 4:
        raise ValueError("Input CSV is not stereo (expected at least 4 columns: X,Y,X,Y).")

    # Build a lookup of diff values keyed by frequency rounded to mHz to tolerate
    # the formatting precision difference between AP exports (e.g. 17.36111111
    # vs 17.3611111111111).
    diff_lookup: dict[float, float] = {}
    for row in diff_data:
        if not row or not row[0].strip():
            continue
        try:
            f = float(row[0])
            y = float(row[1]) if len(row) > 1 and row[1].strip() else float("nan")
        except ValueError:
            continue
        diff_lookup[round(f, 3)] = y

    out_data: list[list[str]] = []
    missing = 0
    for row in in_data:
        if not row or not row[0].strip():
            continue
        try:
            x_l = float(row[0])
            y_l = float(row[1])
            x_r = float(row[2])
            y_r = float(row[3])
        except (ValueError, IndexError):
            continue

        if abs(x_l - x_r) > freq_tolerance:
            raise ValueError(
                f"Left/right frequency mismatch in input at {x_l} Hz vs {x_r} Hz."
            )

        diff_val = diff_lookup.get(round(x_l, 3))
        if diff_val is None or math.isnan(diff_val):
            missing += 1
            new_row = [f"{x_l:.10g}", f"{y_l:.10g}", f"{x_r:.10g}", f"{y_r:.10g}"]
        else:
            new_row = [
                f"{x_l:.10g}",
                f"{y_l + 0.5 * diff_val:.10g}",
                f"{x_r:.10g}",
                f"{y_r - 0.5 * diff_val:.10g}",
            ]
        out_data.append(new_row)

    if missing:
        logger.warning(
            "compensate_lr_diff: %d/%d frequency points had no diff entry and were left unchanged.",
            missing,
            len(out_data),
        )

    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    written_path = _write_rows_with_fallback(output_path, in_header + out_data)
    logger.info(
        "compensate_lr_diff: wrote %d compensated rows to %s", len(out_data), written_path
    )
    return written_path


def _load_diff_lookup(diff_path: str) -> dict[float, float]:
    """Load a mono AP diff CSV into a {round(freq, 3) -> y} lookup."""
    with open(diff_path, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if len(rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError(f"Diff CSV has no data rows after the header: {diff_path}")

    lookup: dict[float, float] = {}
    for row in rows[_AP_NUM_HEADER_ROWS:]:
        if not row or not row[0].strip():
            continue
        try:
            f_hz = float(row[0])
            y = float(row[1]) if len(row) > 1 and row[1].strip() else float("nan")
        except ValueError:
            continue
        lookup[round(f_hz, 3)] = y
    return lookup


def extract_compensated_lr_diff(
    input_path: str,
    diff_path: str,
    output_path: str,
    freq_tolerance: float = 1e-3,
    diff_lookup: Optional[dict[float, float]] = None,
) -> str:
    """
    Compute the L-R difference of a stereo RMS measurement after compensating the
    mic L/R imbalance described by ``diff_path``.

    For each frequency::

        L_comp = L + 0.5 * mic_diff
        R_comp = R - 0.5 * mic_diff
        out    = L_comp - R_comp = (L - R) + mic_diff

    The result is written as a mono AP-style CSV (4 header rows, then ``X,Y`` in dB).

    Args:
        input_path:     Stereo AP measurement CSV (``X,Y,X,Y``).
        diff_path:      Mono AP CSV with the mic L-R difference (dB).
        output_path:    Destination CSV path.
        freq_tolerance: Allowed Hz mismatch between the input L and R frequency columns.
        diff_lookup:    Optional pre-loaded diff lookup (use to avoid re-reading the
                        diff CSV when processing multiple inputs).

    Returns:
        The actual written path.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    if not output_path:
        raise ValueError("output_path must be provided")

    if diff_lookup is None:
        if not diff_path or not os.path.isfile(diff_path):
            raise FileNotFoundError(f"Diff CSV not found: {diff_path}")
        diff_lookup = _load_diff_lookup(diff_path)

    with open(input_path, "r", newline="", encoding="utf-8-sig") as f:
        in_rows = list(csv.reader(f))
    if len(in_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError(f"Input CSV has no data rows after the header: {input_path}")

    in_data = in_rows[_AP_NUM_HEADER_ROWS:]
    if not in_data or len(in_data[0]) < 4:
        raise ValueError(
            f"Input CSV is not stereo (expected at least 4 columns: X,Y,X,Y): {input_path}"
        )

    # Derive the measurement name and X-unit from the source header where possible.
    src_header = in_rows[:_AP_NUM_HEADER_ROWS]
    measurement = src_header[0][0] if src_header and src_header[0] else "Measurement"
    x_unit = "Hz"
    if len(src_header) > 3 and len(src_header[3]) > 0 and src_header[3][0].strip():
        x_unit = src_header[3][0].strip()

    out_header = [
        [measurement, ""],
        ["L-R Compensated", ""],
        ["X", "Y"],
        [x_unit, "dB"],
    ]

    out_data: list[list[str]] = []
    missing = 0
    for row in in_data:
        if not row or not row[0].strip():
            continue
        try:
            x_l = float(row[0])
            y_l = float(row[1])
            x_r = float(row[2])
            y_r = float(row[3])
        except (ValueError, IndexError):
            continue
        if abs(x_l - x_r) > freq_tolerance:
            raise ValueError(
                f"Left/right frequency mismatch in input at {x_l} Hz vs {x_r} Hz."
            )
        mic_diff = diff_lookup.get(round(x_l, 3))
        if mic_diff is None or math.isnan(mic_diff):
            missing += 1
            comp_diff = y_l - y_r
        else:
            comp_diff = (y_l - y_r) + mic_diff
        out_data.append([f"{x_l:.10g}", f"{comp_diff:.10g}"])

    if missing:
        logger.warning(
            "extract_compensated_lr_diff: %d/%d frequency points had no diff entry "
            "and were treated as raw L-R.",
            missing,
            len(out_data),
        )

    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    written_path = _write_rows_with_fallback(output_path, out_header + out_data)
    logger.info(
        "extract_compensated_lr_diff: wrote %d rows from %s to %s",
        len(out_data), input_path, written_path,
    )
    return written_path


def _compute_compensated_lr_diff_rows(
    input_path: str,
    diff_lookup: dict[float, float],
    freq_tolerance: float = 1e-3,
) -> tuple[list[list[str]], list[str], int]:
    """Return ``(rows, src_header, missing)`` where ``rows`` is a list of ``[X, Y]``
    strings holding the compensated L-R difference for one stereo input CSV.
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with open(input_path, "r", newline="", encoding="utf-8-sig") as f:
        in_rows = list(csv.reader(f))
    if len(in_rows) <= _AP_NUM_HEADER_ROWS:
        raise ValueError(f"Input CSV has no data rows after the header: {input_path}")

    src_header = in_rows[:_AP_NUM_HEADER_ROWS]
    in_data = in_rows[_AP_NUM_HEADER_ROWS:]
    if not in_data or len(in_data[0]) < 4:
        raise ValueError(
            f"Input CSV is not stereo (expected at least 4 columns: X,Y,X,Y): {input_path}"
        )

    out_rows: list[list[str]] = []
    missing = 0
    for row in in_data:
        if not row or not row[0].strip():
            continue
        try:
            x_l = float(row[0])
            y_l = float(row[1])
            x_r = float(row[2])
            y_r = float(row[3])
        except (ValueError, IndexError):
            continue
        if abs(x_l - x_r) > freq_tolerance:
            raise ValueError(
                f"Left/right frequency mismatch in {input_path} at {x_l} Hz vs {x_r} Hz."
            )
        mic_diff = diff_lookup.get(round(x_l, 3))
        if mic_diff is None or math.isnan(mic_diff):
            missing += 1
            comp_diff = y_l - y_r
        else:
            comp_diff = (y_l - y_r) + mic_diff
        out_rows.append([f"{x_l:.10g}", f"{comp_diff:.10g}"])

    return out_rows, src_header, missing


def extract_compensated_lr_diff_combined(
    diff_path: str,
    input1_path: str,
    input2_path: str,
    output_path: str,
    freq_tolerance: float = 1e-3,
) -> str:
    """
    Like :func:`extract_compensated_lr_diff_pair` but writes the compensated L-R
    diff of both inputs into a single stereo AP-style CSV (``X,Y,X,Y`` in dB).

    The two inputs must share the same frequency grid (within ``freq_tolerance``).
    """
    if not diff_path or not os.path.isfile(diff_path):
        raise FileNotFoundError(f"Diff CSV not found: {diff_path}")
    if not output_path:
        raise ValueError("output_path must be provided")

    lookup = _load_diff_lookup(diff_path)
    rows1, src_header, missing1 = _compute_compensated_lr_diff_rows(
        input1_path, lookup, freq_tolerance
    )
    rows2, _, missing2 = _compute_compensated_lr_diff_rows(
        input2_path, lookup, freq_tolerance
    )

    if len(rows1) != len(rows2):
        raise ValueError(
            f"Input row counts differ ({len(rows1)} vs {len(rows2)}); cannot combine."
        )
    for i, (r1, r2) in enumerate(zip(rows1, rows2)):
        if abs(float(r1[0]) - float(r2[0])) > freq_tolerance:
            raise ValueError(
                f"Frequency mismatch between inputs at row {i}: {r1[0]} vs {r2[0]}."
            )

    x_unit = "Hz"
    if len(src_header) > 3 and len(src_header[3]) > 0 and src_header[3][0].strip():
        x_unit = src_header[3][0].strip()

    out_header = [
        ["L-R-Diff", "", "", ""],
        ["L-R-Diff-Left", "", "L-R-Diff-Right", ""],
        ["X", "Y", "X", "Y"],
        [x_unit, "dB", x_unit, "dB"],
    ]

    combined: list[list[str]] = [r1 + r2 for r1, r2 in zip(rows1, rows2)]

    if missing1 or missing2:
        logger.warning(
            "extract_compensated_lr_diff_combined: missing diff entries -> %d (input1), %d (input2).",
            missing1, missing2,
        )

    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    written_path = _write_rows_with_fallback(output_path, out_header + combined)
    logger.info(
        "extract_compensated_lr_diff_combined: wrote %d rows to %s",
        len(combined), written_path,
    )
    return written_path


def _resolve_lr_diff_output(output_path: str, input_path: str) -> str:
    """If ``output_path`` is a directory (existing or trailing-slash) or has no
    file extension, append a default filename derived from ``input_path``.
    """
    default_name = f"{os.path.splitext(os.path.basename(input_path))[0]}_LRdiff_comp.csv"
    if not output_path:
        return default_name
    normalized = output_path.rstrip("/\\")
    is_dir = (
        os.path.isdir(output_path)
        or output_path.endswith(("/", "\\"))
        or (not os.path.splitext(normalized)[1])
    )
    if is_dir:
        return os.path.join(normalized, default_name)
    return output_path


def extract_compensated_lr_diff_pair(
    diff_path: str,
    input1_path: str,
    output1_path: str,
    input2_path: str,
    output2_path: str,
    freq_tolerance: float = 1e-3,
) -> tuple[str, str]:
    """
    Convenience wrapper: load the mic diff CSV once and produce a compensated L-R
    difference CSV for each of two stereo RMS measurements.

    ``output1_path`` / ``output2_path`` may be a directory; in that case the
    filename is auto-generated as ``<input_stem>_LRdiff_comp.csv``.
    """
    if not diff_path or not os.path.isfile(diff_path):
        raise FileNotFoundError(f"Diff CSV not found: {diff_path}")
    lookup = _load_diff_lookup(diff_path)
    out1 = extract_compensated_lr_diff(
        input_path=input1_path, diff_path=diff_path,
        output_path=_resolve_lr_diff_output(output1_path, input1_path),
        freq_tolerance=freq_tolerance, diff_lookup=lookup,
    )
    out2 = extract_compensated_lr_diff(
        input_path=input2_path, diff_path=diff_path,
        output_path=_resolve_lr_diff_output(output2_path, input2_path),
        freq_tolerance=freq_tolerance, diff_lookup=lookup,
    )
    return out1, out2


if __name__ == "__main__":
    # Demo 1: Split distortion CSV
    demo_input_path = (
        r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente\H200Data12"
        r"\Measurements\EOL\2026\03_03\dsfsdc_2026_03_03_11_24_08_Lvl_Dist_Ch_1.csv"
    )

    if os.path.isfile(demo_input_path):
        demo_results = split_ap_distortion_csv(demo_input_path)
        for metric, path in demo_results.items():
            print(f"{metric}: {path}")

    # Demo 2: Filter reference by limits
    print("\n--- Filter Reference by Limits Demo ---")
    
    # Example: Filter stereo reference by limits
    demo_reference = r"c:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente\Repos\Audio-Precision\DefaultReferences\GoldenSample\RMS.csv"
    demo_limits = r"c:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente\Repos\Audio-Precision\DefaultReferences\GoldenSample\Limits\RMS.csv"
    
    if os.path.isfile(demo_reference) and os.path.isfile(demo_limits):
        try:
            filtered_path = filter_reference_by_limits(
                reference_path=demo_reference,
                limits_path=demo_limits,
                output_filename="RMS_filtered_demo.csv"
            )
            print(f"Filtered reference saved to: {filtered_path}")
        except Exception as e:
            print(f"Error filtering reference: {e}")
    else:
        print("Demo files not found. Skipping filter demo.")

