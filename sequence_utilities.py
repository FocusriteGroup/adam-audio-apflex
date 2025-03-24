import datetime
import argparse
import os
import pandas as pd
import clr

# Load APx500 API DLLs
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API2.dll")
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API.dll")

from AudioPrecision.API import *

class Utilities:
    """Handles various utility functions."""

    def generate_timestamp_subpath(self):
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m/%d/%H_%M_%S")
        return os.path.normpath(subpath)

    def convert_timestamp_path_to_extension(self, timestamp_path):
        """Convert a timestamp path to an underscore-separated extension format."""
        # Normalize the path to handle both forward and backward slashes
        normalized_path = os.path.normpath(timestamp_path)
        parts = normalized_path.split(os.path.sep)
        
        # Ensure the path has at least four parts
        if len(parts) < 4:
            raise ValueError("Invalid timestamp path format. Expected at least four parts (e.g., 'YYYY/MM/DD/HH_MM_SS').")
        
        date_part = parts[:3]
        time_part = parts[3].split('_')
        extension = f"_{date_part[0]}_{date_part[1]}_{date_part[2]}_{time_part[0]}_{time_part[1]}_{time_part[2]}"
        return os.path.normpath(extension)

    def construct_path(self, paths):
        """Construct path by joining the list of paths."""
        joined_path = os.path.normpath(os.path.join(*paths))
        return joined_path

class AudioPrecisionAPI:
    """Handles commands related to the Audio Precision API."""

    def __init__(self):
        # Initialize the Audio Precision API
        self.apx = APx500_Application()
        self.apx.Visible = True  # Make sure APx500 is visible

    def set_averages(self, measurement_name, averages):
        """Set the number of averages for a specific measurement."""
        # Ensure a valid project is loaded
        if self.apx.ProjectFileName == "":
            self.apx.CreateNewProject()

        # Get the specified measurement
        measurement = getattr(self.apx, measurement_name, None)
        if measurement is None:
            raise ValueError(f"Measurement '{measurement_name}' not found.")

        # Set the number of averages
        measurement.Averages = averages
        return f"Number of averages for '{measurement_name}' set to {measurement.Averages}."

class CommandProcessor:
    """Handles command processing and delegates tasks to appropriate classes."""

    def __init__(self):
        self.utilities = Utilities()
        self.audio_precision_api = AudioPrecisionAPI()
        self.command_map = {
            "get_timestamp_subpath": self.utilities.generate_timestamp_subpath,
            "get_timestamp_extension": self.utilities.convert_timestamp_path_to_extension,
            "construct_path": self.utilities.construct_path,
            "set_averages": self.audio_precision_api.set_averages
        }
        self.parser = argparse.ArgumentParser(description="Utility functions.")
        subparsers = self.parser.add_subparsers(dest="command", required=True)

        # Generate a timestamp subpath
        parser_generate_subpath = subparsers.add_parser("get_timestamp_subpath", help="Generate a timestamp subpath.")

        # Convert a timestamp path to an extension format
        parser_convert_extension = subparsers.add_parser("get_timestamp_extension", help="Convert a timestamp path to an underscore-separated extension.")
        parser_convert_extension.add_argument("timestamp_path", type=str, help="Timestamp path to convert.")

        # Construct path
        parser_construct_path = subparsers.add_parser("construct_path", help="Construct path.")
        parser_construct_path.add_argument("paths", type=str, nargs='+', help="List of paths to join.")

        # Set averages
        parser_set_averages = subparsers.add_parser("set_averages", help="Set the number of averages for a measurement.")
        parser_set_averages.add_argument("measurement_name", type=str, help="Name of the measurement.")
        parser_set_averages.add_argument("averages", type=int, help="Number of averages to set.")

    def execute(self, command, args):
        """Execute a function dynamically based on the command."""
        if command in self.command_map:
            method = self.command_map[command]
            return method(*args)
        else:
            raise ValueError(f"Unknown command: {command}")

    def parse_and_execute(self):
        """Parse command-line arguments and execute the appropriate function."""
        args = self.parser.parse_args()
        result = self.execute(args.command, [getattr(args, arg) for arg in vars(args) if arg != "command"])
        print(result)

def main():
    processor = CommandProcessor()
    try:
        processor.parse_and_execute()
    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()
