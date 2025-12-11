import logging
import numpy as np
from .measurement_parser import MeasurementParser

# Configure local logger
CALIBRATION_LOGGER = logging.getLogger("GainCalibration")
CALIBRATION_LOGGER.setLevel(logging.INFO)

class GainCalibration:
    """Handles gain calibration calculations between input and target measurements."""

    @staticmethod
    def calculate_gain_difference(input_file: str, target_file: str, frequencies: list) -> dict:
        """
        Calculates gain differences between input and target measurements at specified frequencies.

        Args:
            input_file (str): Path to input measurement CSV
            target_file (str): Path to target/reference measurement CSV
            frequencies (list): List of frequencies to analyze

        Returns:
            dict: Results containing per-frequency and average gain differences
        """
        CALIBRATION_LOGGER.info("Starting gain calibration calculation")
        
        try:
            # Parse both measurement files
            input_data = MeasurementParser.parse_measurement_csv(input_file)
            target_data = MeasurementParser.parse_measurement_csv(target_file)
            
            # Warn if multiple channels found
            if len(input_data["channels"]) > 1:
                CALIBRATION_LOGGER.warning("Input file contains %d channels. Using Channel 1 only.", 
                                         len(input_data["channels"]))
            if len(target_data["channels"]) > 1:
                CALIBRATION_LOGGER.warning("Target file contains %d channels. Using Channel 1 only.", 
                                         len(target_data["channels"]))
            
            # Extract Channel 1 data
            input_ch = input_data["channels"]["Ch1"]
            target_ch = target_data["channels"]["Ch1"]
            
            input_freqs = np.array(input_ch["frequencies"])
            input_levels = np.array(input_ch["levels"])
            target_freqs = np.array(target_ch["frequencies"])
            target_levels = np.array(target_ch["levels"])
            
            calibration_results = {}
            gain_differences = []
            
            # Calculate gain difference for each requested frequency
            for freq in frequencies:
                # Find closest frequency bins
                input_idx = np.abs(input_freqs - freq).argmin()
                target_idx = np.abs(target_freqs - freq).argmin()
                
                # Get actual frequencies and levels
                actual_input_freq = input_freqs[input_idx]
                actual_target_freq = target_freqs[target_idx]
                gain_diff = target_levels[target_idx] - input_levels[input_idx]
                gain_differences.append(gain_diff)
                
                calibration_results[freq] = {
                    "gain_difference_db": float(gain_diff),
                    "actual_input_freq": float(actual_input_freq),
                    "actual_target_freq": float(actual_target_freq)
                }
            
            # Calculate average gain difference, limit to +/- 2.0 and round to one decimal
            average_gain = float(np.clip(np.round(np.mean(gain_differences), 1), -2.0, 2.0))
            
            CALIBRATION_LOGGER.info("Gain calibration completed successfully")
            return {
                "frequency_results": calibration_results,
                "average_gain_db": average_gain
            }
            
        except Exception as e:
            CALIBRATION_LOGGER.error("Gain calibration failed: %s", str(e))
            raise