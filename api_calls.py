import clr
import threading

# Add references to the Audio Precision API DLLs
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API2.dll")
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API.dll")

from AudioPrecision.API import APx500_Application

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
            project_file = self.APx.ProjectFileName  # Access a property
            self.APx.Visible = True  # Ensure the application remains visible
            print(f"[INFO] Wake-up check: Current project file is '{project_file}'.")
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
        """Activate a specific measurement in the APx500 sequence."""
        try:
            sequence = self.APx.Sequence[0]  # Access the first sequence
            measurement = sequence[measurement_name]  # Get the measurement by name
            measurement.Show()  # Show the measurement
            measurement.Checked = True  # Check the measurement to activate it
            print(f"[INFO] Activated measurement: {measurement_name}")
        except KeyError:
            print(f"[ERROR] Measurement '{measurement_name}' not found in the sequence.")
        except Exception as e:
            print(f"[ERROR] Failed to activate measurement '{measurement_name}': {e}")

    def set_average(self, averages):
        """Set the number of averages for the current measurement."""
        with self.lock:  # Ensure thread-safe access
            try:
                self.APx.AcousticResponse.Averages = averages
                print(f"[INFO] Averages set to {averages}.")
                return f"Successfully set averages to {averages}."
            except Exception as e:
                print(f"[ERROR] Failed to set averages: {e}")
                return f"Error: Failed to set averages. {e}"