"""
csv_processing.py

CSV processing utilities for ADAM Audio analysis workflows.
"""

import csv
import math
import os
from itertools import chain
from typing import Iterable, Optional


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


if __name__ == "__main__":
    demo_input_path = (
        r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente\H200Data12"
        r"\Measurements\EOL\2026\03_03\dsfsdc_2026_03_03_11_24_08_Lvl_Dist_Ch_1.csv"
    )

    if not os.path.isfile(demo_input_path):
        raise FileNotFoundError(f"Demo input CSV not found: {demo_input_path}")

    demo_results = split_ap_distortion_csv(demo_input_path)
    for metric, path in demo_results.items():
        print(f"{metric}: {path}")
