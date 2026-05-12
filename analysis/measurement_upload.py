import json
import logging
import sqlite3
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

    @staticmethod
    def write_measurement_local_db(upload_data: dict, serial_number: str, db_path: str) -> dict:
        """
        Writes a prepared measurement directly into the local matcher SQLite database.

        Existing rows are updated when status is 'unmatched' or 'matched'.
        Paired rows are rejected and must be unpaired first.
        """
        try:
            db_file = Path(db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

            measurement_data = upload_data.get("measurement_data", {})
            channels = measurement_data.get("channels", {}) if isinstance(measurement_data, dict) else {}
            ch1 = channels.get("Ch1", {})
            levels = ch1.get("levels")

            if not isinstance(levels, list) or not levels:
                return {"error": "No Ch1 levels found in measurement data"}

            if serial_number.startswith("IA"):
                side = "left"
            elif serial_number.startswith("IB"):
                side = "right"
            else:
                return {"error": f"Unsupported serial prefix for matching pool: {serial_number}"}

            con = sqlite3.connect(str(db_file))
            cur = con.cursor()
            cur.execute("PRAGMA journal_mode=DELETE")
            cur.execute("PRAGMA busy_timeout=5000")

            # Ensure matcher schema exists for standalone local usage.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS frequency_vector (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    frequencies TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS drivers (
                    serial      TEXT PRIMARY KEY,
                    side        TEXT NOT NULL,
                    levels      TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'unmatched',
                    partner     TEXT,
                    loaded_at   TEXT NOT NULL,
                    matched_at  TEXT
                )
            """)

            freqs = ch1.get("frequencies")
            if isinstance(freqs, list) and freqs:
                cur.execute("SELECT id FROM frequency_vector WHERE id = 1")
                if cur.fetchone() is None:
                    cur.execute(
                        "INSERT INTO frequency_vector (id, frequencies) VALUES (1, ?)",
                        (json.dumps(freqs),),
                    )

            now = datetime.now().isoformat()
            cur.execute("SELECT status, partner FROM drivers WHERE serial = ?", (serial_number,))
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    "INSERT INTO drivers (serial, side, levels, status, loaded_at) VALUES (?, ?, ?, 'unmatched', ?)",
                    (serial_number, side, json.dumps(levels), now),
                )
                operation = "inserted"
            else:
                status, partner = row
                if status == "paired":
                    con.close()
                    return {
                        "error": "status_blocked",
                        "serial_number": serial_number,
                        "current_status": status,
                    }

                if status == "matched":
                    # Matched is transient in this workflow: reset the affected pair back to unmatched.
                    if partner:
                        cur.execute(
                            "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
                            "WHERE serial IN (?, ?)",
                            (serial_number, partner),
                        )
                    else:
                        cur.execute(
                            "UPDATE drivers SET status='unmatched', partner=NULL, matched_at=NULL "
                            "WHERE serial = ?",
                            (serial_number,),
                        )
                elif status != "unmatched":
                    con.close()
                    return {
                        "error": "status_blocked",
                        "serial_number": serial_number,
                        "current_status": status,
                    }

                cur.execute(
                    "UPDATE drivers SET side = ?, levels = ?, loaded_at = ? WHERE serial = ?",
                    (side, json.dumps(levels), now, serial_number),
                )
                operation = "updated"

            con.commit()
            con.close()

            UPLOAD_LOGGER.info(
                "Measurement written to local DB (%s): serial=%s, db=%s",
                operation,
                serial_number,
                db_file,
            )

            return {
                "status": "success",
                "operation": operation,
                "serial_number": serial_number,
                "db_file": str(db_file.resolve()),
            }

        except (sqlite3.Error, OSError, KeyError, ValueError, TypeError) as e:
            UPLOAD_LOGGER.error("Failed to write measurement to local DB: %s", str(e))
            return {"error": str(e)}