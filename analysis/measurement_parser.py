import logging
import csv
import numpy as np
import math

# Configure local logger
PARSER_LOGGER = logging.getLogger("MeasurementParser")
PARSER_LOGGER.setLevel(logging.INFO)

class MeasurementParser:
    """Handles CSV measurement file parsing."""
    
    @staticmethod
    def parse_measurement_csv(file_path: str):
        """
        Parses a measurement CSV file with dynamic channel count.

        Args:
            file_path (str): Path to the measurement CSV file.

        Returns:
            dict: {
                'channels': {
                    'Ch1': {'frequencies': [...], 'levels': [...], 'unit': 'dBSPL'},
                    'Ch2': {...}, ...
                },
                'data_points': int
            }
        """
        PARSER_LOGGER.info("Starting to parse measurement file: %s", file_path)
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip()]

            # Find units row (containing 'Hz' and 'dB')
            units_idx = None
            for i, line in enumerate(lines):
                if "Hz" in line and "dB" in line:
                    units_idx = i
                    break
            if units_idx is None:
                PARSER_LOGGER.error("No units header (Hz,dB...) found")
                raise ValueError("No units header (Hz,dB...) found")

            # Extract units columns
            units_tokens = [t for t in lines[units_idx].split(",") if t]
            data_lines = lines[units_idx + 1:]

            def _unit_for_pair(pair_index):
                try:
                    return units_tokens[pair_index * 2 + 1]
                except IndexError:
                    return "dB"

            # Parse data rows
            rows = []
            reader = csv.reader(data_lines)
            for row in reader:
                row = [c.strip() for c in row if c.strip() != ""]
                if not row:
                    continue
                rows.append(row)

            if not rows:
                PARSER_LOGGER.error("No data lines found")
                raise ValueError("No data lines found")

            # Validate column count
            col_count = len(rows[0])
            if any(len(r) != col_count for r in rows):
                rows = [r for r in rows if len(r) == col_count]

            if col_count % 2 != 0:
                PARSER_LOGGER.error("Expected even column count, found: %d", col_count)
                raise ValueError(f"Expected even column count (frequency+level per channel). Found: {col_count}")

            channel_count = col_count // 2
            PARSER_LOGGER.info("Found %d channels in measurement file", channel_count)

            channels = {}
            
            # Convert to numeric arrays
            cols_numeric = []
            for r in rows:
                numeric = []
                for c in r:
                    try:
                        numeric.append(float(c))
                    except ValueError:
                        numeric.append(math.nan)
                cols_numeric.append(numeric)

            arr = np.array(cols_numeric, dtype=float)
            mask_valid = ~np.isnan(arr).any(axis=1)
            arr = arr[mask_valid]

            for ch_index in range(channel_count):
                freq_col = arr[:, 2 * ch_index]
                level_col = arr[:, 2 * ch_index + 1]
                ch_name = f"Ch{ch_index + 1}"
                channels[ch_name] = {
                    "frequencies": freq_col.tolist(),
                    "levels": level_col.tolist(),
                    "unit": _unit_for_pair(ch_index),
                    "data_points": int(len(freq_col))
                }

            PARSER_LOGGER.info("Successfully parsed measurement file with %d data points", len(rows))
            return {
                "channels": channels,
                "data_points": int(arr.shape[0])
            }
            
        except Exception as e:
            PARSER_LOGGER.error("Failed to parse measurement file: %s", str(e))
            raise