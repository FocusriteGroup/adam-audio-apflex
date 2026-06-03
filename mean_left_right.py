"""Compute the mean of the Left and Right channel Y values from an AP CSV export.

The CSV layout produced by Audio Precision contains four header rows followed by
data rows with four columns: X_left, Y_left, X_right, Y_right.

Usage:
    python mean_left_right.py <input.csv> [output.csv]

If no output path is given, the result is written next to the input as
``<stem>_Mean.csv``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def compute_mean(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = rows[:4]
    data = rows[4:]

    measurement = header[0][0] if header and header[0] else "Measurement"
    x_unit = header[3][0] if len(header) > 3 and len(header[3]) > 0 else "X"
    y_unit = header[3][1] if len(header) > 3 and len(header[3]) > 1 else "Y"

    out_header = [
        [measurement, ""],
        ["Mean(Left,Right)", ""],
        ["X", "Y"],
        [x_unit, y_unit],
    ]

    out_rows: list[list[str]] = []
    for row in data:
        if len(row) < 4:
            continue
        try:
            x_l = float(row[0])
            y_l = float(row[1])
            y_r = float(row[3])
        except ValueError:
            continue
        out_rows.append([f"{x_l:.10g}", f"{(y_l + y_r) / 2:.10g}"])

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(out_header)
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {output_path}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    input_path = Path(argv[1])
    if not input_path.is_file():
        print(f"Input file not found: {input_path}")
        return 1
    if len(argv) > 2:
        output_path = Path(argv[2])
    else:
        default_dir = Path(__file__).resolve().parent / "DefaultReferences"
        default_dir.mkdir(parents=True, exist_ok=True)
        output_path = default_dir / f"{input_path.stem}_Mean.csv"
    compute_mean(input_path, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
