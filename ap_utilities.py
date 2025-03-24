import datetime
import os
import sys
import clr
import threading
import socket
import json

clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API2.dll")
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API.dll")

from AudioPrecision.API import *

class Utilities:
    """Utility class for various helper functions."""

    def generate_timestamp_subpath(self):
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m_%d")
        return os.path.normpath(subpath)
    
    def generate_timestamp_extension(self):
        """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
        now = datetime.datetime.now()
        extension = now.strftime("%Y_%m_%d_%H_%M_%S")
        return extension

    def construct_path(self, paths):
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

    def generate_file_prefix(self, strings):
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

    def __init__(self, server_host="127.0.0.1", server_port=65432):
        """
        Initialize the Audio Precision API interface.

        Args:
            server_host (str): The IP address of the server to notify.
            server_port (int): The port of the server to notify.
        """
        if not hasattr(AudioPrecisionAPI, "_apx_instance"):
            AudioPrecisionAPI._apx_instance = APx500_Application()
            AudioPrecisionAPI._apx_instance.Visible = True
        self.APx = AudioPrecisionAPI._apx_instance
        self.measurement = self.APx.AcousticResponse

        self.server_host = server_host
        self.server_port = server_port

        # Lock for thread safety
        self.lock = threading.Lock()

        # Start a keep-alive thread
        self.keep_alive_thread = threading.Thread(target=self._keep_alive, daemon=True)
        self.keep_alive_thread.start()

    def _keep_alive(self):
        """Periodically interact with the APx500_Application object to keep it alive."""
        while True:
            with self.lock:  # Ensure thread-safe access
                try:
                    # Perform a lightweight operation to keep the connection alive
                    project_file = self.APx.ProjectFileName  # Access a property
                    self.APx.Visible = True  # Ensure the application remains visible
                    print(f"[INFO] Keep-alive check: Current project file is '{project_file}'.")

                    # Check if there is an active measurement
                    if self.APx.ActiveMeasurement is None:
                        print("[ERROR] No active measurement found.")
                        return

                    # Optionally, activate the active measurement
                    print(f"[DEBUG] Active measurement: {self.APx.ActiveMeasurementName}")
                except Exception as e:
                    print(f"[ERROR] Keep-alive error: {e}")
                    # Attempt to reinitialize the APx500_Application if the connection is lost
                    try:
                        print("[DEBUG] Reinitializing APx500_Application...")
                        AudioPrecisionAPI._apx_instance = APx500_Application()
                        AudioPrecisionAPI._apx_instance.Visible = True
                        self.APx = AudioPrecisionAPI._apx_instance
                        self.measurement = self.APx.AcousticResponse
                        print("[DEBUG] Reinitialization complete.")
                    except Exception as reinit_error:
                        print(f"[ERROR] Failed to reinitialize APx500_Application: {reinit_error}")
            threading.Event().wait(10)  # Wait for 10 seconds before the next interaction

    def set_averages(self, averages):
        """Set the number of averages for the hardcoded measurement."""
        with self.lock:  # Ensure thread-safe access
            try:
                # Check if the AcousticResponse measurement is valid
                if self.measurement is None:
                    print("[ERROR] AcousticResponse measurement is not initialized.")
                    return

                # Check if there is an active measurement
                if self.APx.ActiveMeasurement is None:
                    print("[ERROR] No active measurement found. The application might not be ready.")
                    return

                # Attempt to set the averages
                self.measurement.Averages = averages
                print("info", f"Number of averages for AcousticResponse set to {self.measurement.Averages}.")
            except Exception as e:
                print("error", f"Error setting averages: {e}")
                # Reinitialize APx500_Application if needed
                try:
                    print("[DEBUG] Reinitializing APx500_Application...")
                    AudioPrecisionAPI._apx_instance = APx500_Application()
                    AudioPrecisionAPI._apx_instance.Visible = True
                    self.APx = AudioPrecisionAPI._apx_instance
                    self.measurement = self.APx.AcousticResponse
                    print("[DEBUG] Reinitialization complete.")
                except Exception as reinit_error:
                    print(f"[ERROR] Failed to reinitialize APx500_Application: {reinit_error}")
