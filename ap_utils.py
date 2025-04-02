import os
import datetime
import clr
import threading


clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API2.dll")
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API.dll")

from AudioPrecision.API import *

class Utilities:
    """Utility class for various helper functions."""

    @staticmethod
    def generate_timestamp_extension():
        """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
        now = datetime.datetime.now()
        extension = now.strftime("%Y_%m_%d_%H_%M_%S")
        return extension

    @staticmethod
    def construct_path(paths):
        """
        Construct a path by joining the list of paths.

        Args:
            paths (list): A list of strings representing path components.

        Returns:
            str: A normalized path string.
        """
        if not paths or not isinstance(paths, list):
            raise ValueError("'paths' must be a non-empty list of strings.")
        if not all(isinstance(p, str) for p in paths):
            raise ValueError("All elements in 'paths' must be strings.")
        return os.path.normpath(os.path.join(*paths))

    @staticmethod
    def generate_timestamp_subpath():
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m_%d")
        return os.path.normpath(subpath)

    @staticmethod
    def generate_file_prefix(strings):
        """
        Generate a file prefix by concatenating a list of strings with an underscore.

        Args:
            strings (list): A list of strings to concatenate.

        Returns:
            str: A single string with the substrings joined by an underscore.
        """
        if not strings or not isinstance(strings, list):
            raise ValueError("'strings' must be a non-empty list of strings.")
        if not all(isinstance(s, str) for s in strings):
            raise ValueError("All elements in 'strings' must be strings.")
        return "_".join(strings)
    

class AudioPrecisionAPI:
    """Class to interact with Audio Precision devices or APIs."""

    def __init__(self):
        """
        Initialize the Audio Precision API interface.
        """
        if not hasattr(AudioPrecisionAPI, "_apx_instance"):
            AudioPrecisionAPI._apx_instance = APx500_Application()
            AudioPrecisionAPI._apx_instance.Visible = True
        self.APx = AudioPrecisionAPI._apx_instance

        # Lock for thread safety
        self.lock = threading.Lock()

    def wake_up(self):
        """Wake up the APx500_Application to ensure it remains active."""
        try:
            # Perform a lightweight operation to keep the connection alive
            project_file = self.APx.ProjectFileName  # Access a property
            self.APx.Visible = True  # Ensure the application remains visible
            print(f"[INFO] Wake-up check: Current project file is '{project_file}'.")

            # Optionally, check if there is an active measurement
            if self.APx.ActiveMeasurement is None:
                print("[WARNING] No active measurement found.")
        except Exception as e:
            print(f"[ERROR] Wake-up error: {e}")
            self._reinitialize_apx()


    def _reinitialize_apx(self):
        """Reinitialize the APx500_Application if the connection is lost."""
        try:
            print("[DEBUG] Reinitializing APx500_Application...")
            AudioPrecisionAPI._apx_instance = APx500_Application()
            AudioPrecisionAPI._apx_instance.Visible = True
            self.APx = AudioPrecisionAPI._apx_instance
            print("[DEBUG] Reinitialization complete.")
        except Exception as reinit_error:
            print(f"[ERROR] Failed to reinitialize APx500_Application: {reinit_error}")

    def activate_measurement(self, measurement_name):
        """
        Activate a specific measurement in the APx500 sequence.

        Args:
            measurement_name (str): The name of the measurement to activate.
        """
        try:
            # Select and activate the measurement from the sequence
            sequence = self.APx.Sequence[0]  # Access the first sequence
            measurement = sequence[measurement_name]  # Get the measurement by name
            measurement.Show()  # show the measurement
            measurement.Checked = True # Check the measurement to activate it
            print(f"[INFO] Activated measurement: {measurement_name}")
        except KeyError:
            print(f"[ERROR] Measurement '{measurement_name}' not found in the sequence.")
        except Exception as e:
            print(f"[ERROR] Failed to activate measurement '{measurement_name}': {e}")

    def set_average(self, averages):
        """
        Set the number of averages for the current measurement.

        Args:
            averages (int): The number of averages to set.

        Returns:
            str: A message indicating the result of the operation.
        """
        with self.lock:  # Ensure thread-safe access
            try:
                self.APx.AcousticResponse.Averages = averages
                print(f"[INFO] Averages set to {averages}.")
                return f"Successfully set averages to {averages}."
            except Exception as e:
                print(f"[ERROR] Failed to set averages: {e}")
                return f"Error: Failed to set averages. {e}"

