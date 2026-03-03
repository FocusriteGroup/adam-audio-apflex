"""
csv_processing.py

CSV processing utilities for ADAM Audio analysis workflows.
"""

import csv
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


if __name__ == "__main__":
    demo_input_path = (
        r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente\H200Data12"
        r"\Measurements\EOL\2026\02_25\dsfsdc_2026_02_25_13_19_07_Lvl_Dist_Ch_1.csv"
    )
    demo_output_filename = "output.csv"

    if not os.path.isfile(demo_input_path):
        raise FileNotFoundError(f"Demo input CSV not found: {demo_input_path}")

    demo_columns = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    demo_result = extract_csv_columns(
        demo_input_path,
        demo_columns,
        demo_output_filename,
    )
    print(demo_result)
