import logging
from datetime import datetime
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