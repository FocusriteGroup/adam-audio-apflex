import json
import logging
import time
from datetime import datetime
from pathlib import Path
from .measurement_parser import MeasurementParser

# Configure local logger
UPLOAD_LOGGER = logging.getLogger("MeasurementUpload")
UPLOAD_LOGGER.setLevel(logging.INFO)

class MeasurementUpload:
    """Handles measurement data upload preparation."""

    @staticmethod
    def prepare_upload(measurement_path: str, serial_number: str, workstation_id: str):
        """
        Prepares measurement data for upload to service.

        Args:
            measurement_path (str): Path to measurement CSV file
            serial_number (str): Device serial number
            workstation_id (str): Workstation identifier

        Returns:
            dict: Formatted data ready for service upload
        """
        UPLOAD_LOGGER.info("Preparing measurement file for upload: %s", measurement_path)
        
        try:
            # Parse measurement data
            measurement_data = MeasurementParser.parse_measurement_csv(measurement_path)
            
            # Format for upload
            upload_data = {
                "workstation_id": workstation_id,
                "serial_number": serial_number,
                "timestamp": datetime.now().isoformat(),
                "measurement_data": measurement_data
            }
            
            UPLOAD_LOGGER.info("Measurement data prepared successfully")
            return upload_data
            
        except Exception as e:
            UPLOAD_LOGGER.error("Failed to prepare measurement data: %s", str(e))
            raise

    @staticmethod
    def write_measurement_local(upload_data: dict, serial_number: str, json_directory: str = "measurements") -> dict:
        """
        Writes a prepared measurement to a local JSON file without requiring the ADAM service.

        Args:
            upload_data (dict): Output of prepare_upload().
            serial_number (str): Device serial number used as measurement key.
            json_directory (str): Directory path for the JSON file (absolute or relative to cwd).

        Returns:
            dict: Result with keys 'status', 'measurement_id', 'measurement_count',
                  'frequency_points', 'json_file' on success, or 'error' on failure.
        """
        try:
            target_dir = Path(json_directory)
            target_dir.mkdir(parents=True, exist_ok=True)
            json_file = target_dir / "all_measurements.json"

            # Inner parsed data has the channels
            measurement_data = upload_data.get("measurement_data", {})

            # Load existing JSON or create base structure
            if json_file.exists():
                with json_file.open("r", encoding="utf-8") as f:
                    json_data = json.load(f)
            else:
                json_data = {
                    "metadata": {
                        "created": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_measurements": 0,
                    },
                    "measurements": {},
                }

            # Reject if this serial number was already measured
            existing_serials = {
                v.get("serial_number") for v in json_data.get("measurements", {}).values()
            }
            if serial_number in existing_serials:
                UPLOAD_LOGGER.warning("Duplicate measurement rejected: serial=%s", serial_number)
                return {"error": "duplicate", "serial_number": serial_number}

            global_freq = json_data.get("frequency_vector", None)

            # Adopt frequency vector from first measurement if not yet present
            if global_freq is None:
                adopted = False
                for ch_name, ch_data in measurement_data.get("channels", {}).items():
                    freqs = ch_data.get("frequencies")
                    if freqs and isinstance(freqs, list) and len(freqs) > 0:
                        json_data["frequency_vector"] = freqs
                        json_data["metadata"]["frequency_points"] = len(freqs)
                        global_freq = freqs
                        UPLOAD_LOGGER.info("Global frequency vector adopted from channel %s (%d points)", ch_name, len(freqs))
                        adopted = True
                        break
                if not adopted:
                    return {"error": "No frequency vector found in first measurement"}
            else:
                # Validate incoming frequency vectors
                for ch_name, ch_data in measurement_data.get("channels", {}).items():
                    incoming = ch_data.get("frequencies")
                    if incoming:
                        if len(incoming) != len(global_freq):
                            UPLOAD_LOGGER.warning(
                                "Frequency length mismatch (ch=%s expected=%d got=%d) -> ignoring",
                                ch_name, len(global_freq), len(incoming)
                            )
                        else:
                            if not (incoming[0] == global_freq[0] and
                                    incoming[len(incoming) // 2] == global_freq[len(global_freq) // 2] and
                                    incoming[-1] == global_freq[-1]):
                                UPLOAD_LOGGER.warning(
                                    "Frequency values differ (ch=%s) -> ignoring", ch_name
                                )

            # Strip frequencies from channel data, keep only levels
            for ch_name, ch_data in measurement_data.get("channels", {}).items():
                if "frequencies" in ch_data:
                    del ch_data["frequencies"]
                if "levels" in ch_data and isinstance(ch_data["levels"], list):
                    ch_data["data_points"] = len(ch_data["levels"])

            measurement_id = f"{serial_number}_{int(time.time())}"
            json_data["measurements"][measurement_id] = {
                "workstation_id": upload_data.get("workstation_id"),
                "serial_number": serial_number,
                "timestamp": upload_data.get("timestamp"),
                **measurement_data,
            }
            json_data["metadata"]["last_updated"] = datetime.now().isoformat()
            json_data["metadata"]["total_measurements"] = len(json_data["measurements"])

            with json_file.open("w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            UPLOAD_LOGGER.info("Measurement written locally: id=%s, file=%s", measurement_id, json_file)
            return {
                "status": "success",
                "measurement_id": measurement_id,
                "measurement_count": len(json_data["measurements"]),
                "frequency_points": len(json_data.get("frequency_vector", [])),
                "json_file": str(json_file.resolve()),
            }

        except (FileNotFoundError, PermissionError, json.JSONDecodeError, KeyError, ValueError) as e:
            UPLOAD_LOGGER.error("Failed to write measurement locally: %s", str(e))
            return {"error": str(e)}