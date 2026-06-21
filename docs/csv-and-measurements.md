# CSV And Measurement Processing

CSV and measurement utilities live in [../analysis](../analysis) and are exposed mainly through [../adam_workstation.py](../adam_workstation.py). They are used by APx500 projects to prepare reference curves, process AP output files, calculate calibration offsets, and write matching measurements.

## AP CSV Assumptions

Most AP measurement processors expect the standard AP CSV shape:

- four header rows;
- data rows after the header;
- X/Y column pairs, where X is frequency and Y is a measured value;
- stereo files commonly use `X,Y,X,Y`;
- Y values for smoothing are treated as dB SPL.

Some simple helper functions, such as `extract_csv_columns`, operate on generic CSV files and have their own rules.

## Workstation Commands

| Command | Purpose | Stdout |
|---|---|---|
| `extract_csv_columns` | Copy selected zero-based columns from row 2 onward to a new file. | Output path. |
| `octave_smooth_ap_csv` | Apply 1/n-octave smoothing to every AP Y column. | Output path. |
| `split_ap_distortion_csv` | Split AP Level & Distortion CSV into per-metric files such as F, H2, H3, Total. | Local: `metric: path` lines. Service: JSON mapping. |
| `merge_ap_distortion_csvs` | Merge multiple Level & Distortion CSV files into combined per-metric files. | Local: `metric: path` lines. Service: JSON mapping. |
| `filter_reference_by_limits` | Keep reference frequencies that fall inside mono limits ranges. | `successful` on success. |
| `compensate_lr_diff` | Apply L/R microphone compensation to stereo RMS data. | Output path. |
| `extract_compensated_lr_diff_pair` | Produce compensated L/R diff files for two measurements. | Two output paths, one per line. |
| `extract_compensated_lr_diff_combined` | Produce one stereo compensated L/R diff CSV from two measurements. | Output path. |
| `calibrate_gain` | Compare an input measurement with a target reference at selected frequencies. | Numeric average gain offset with two decimals. |
| `upload_measurement` | Parse measurement CSV and write the matching data into SQLite. | `True` or `False`. |

## Octave Smoothing

`octave_smooth_ap_csv` reads AP data rows, finds Y columns at odd indices, and smooths each Y column independently. Smoothing is performed in linear pressure and converted back to dB:

$$
p = 10^{dB / 20}
$$

For each frequency $f$, the smoothing window is:

$$
\left[\frac{f}{2^{1/(2n)}}, f \cdot 2^{1/(2n)}\right]
$$

where $n$ is the octave fraction denominator, for example `3` for 1/3 octave.

## Reference Filtering

`filter_reference_by_limits` is APx-gated by the literal stdout string `successful`. It writes a filtered reference CSV using a reference measurement and a mono limits CSV. See [filter_reference_by_limits.md](filter_reference_by_limits.md) for algorithm details.

## L/R Compensation

The L/R compensation tools use a mono diff CSV and stereo RMS measurements. The compensation rule is:

$$
L' = L + 0.5 \cdot diff
$$

$$
R' = R - 0.5 \cdot diff
$$

This keeps the correction symmetric around the measured stereo response.

## Measurement Upload

[../analysis/measurement_parser.py](../analysis/measurement_parser.py) parses AP measurement CSV files into a structured object with channels, frequency vectors, and level arrays. [../analysis/measurement_upload.py](../analysis/measurement_upload.py) wraps the parsed data with:

| Field | Meaning |
|---|---|
| `workstation_id` | Hostname of the workstation. |
| `serial_number` | Device or module serial number from APx. |
| `timestamp` | Upload time. |
| `measurement_data` | Parsed channel data. |

`upload_measurement` writes directly to `Matching_App/Data/db/matcher.db` by default. It accepts only serial numbers starting with `IA` for left drivers or `IB` for right drivers. Existing rows can be updated when their status is `unmatched` or `matched`; `paired` rows are rejected and must be unpaired first.

The JSON upload path is deprecated for the APx command, and `--server` is disabled for `upload_measurement`.

## Locked Output Files

CSV writers use a fallback naming strategy when the target output file is locked. If `output.csv` cannot be opened due to `PermissionError`, the writer attempts `output_1.csv`, `output_2.csv`, and so on.

## Practical APx Guidance

- Use quoted paths for APx variables that may contain spaces.
- Use `WaitForExitValidateResponse` only for commands with stable literal stdout such as `successful`, `True`, or `Channel set to 1`.
- Use `WaitForExitStoreOutputInVariable` for paths, timestamps, serial numbers, and numeric calibration offsets.
- Treat `ERROR: ...`, `Error: ...`, or unexpected paths as production failures.