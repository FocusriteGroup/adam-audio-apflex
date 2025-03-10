import datetime
import argparse
import os
import pandas as pd

class CommandProcessor:

    def __init__(self):
        self.command_map = {
            "get_timestamp_subpath": self.generate_timestamp_subpath,
            "get_timestamp_extension": self.convert_timestamp_path_to_extension,
            "separate_level_and_distortion": self.separate_level_and_distortion,
            "construct_path": self.construct_path
        }
        self.parser = argparse.ArgumentParser(description="Utility functions.")
        subparsers = self.parser.add_subparsers(dest="command", required=True)

        # Generate a timestamp subpath
        parser_generate_subpath = subparsers.add_parser("get_timestamp_subpath", help="Generate a timestamp subpath.")

        # Convert a timestamp path to an extension format
        parser_convert_extension = subparsers.add_parser("get_timestamp_extension", help="Convert a timestamp path to an underscore-separated extension.")
        parser_convert_extension.add_argument("timestamp_path", type=str, help="Timestamp path to convert.")

        # Separate level and distortion
        parser_separate_level_distortion = subparsers.add_parser("separate_level_and_distortion", help="Separate level and distortion.")
        parser_separate_level_distortion.add_argument("results_path", type=str, help="Results path.")
        parser_separate_level_distortion.add_argument("timestamp_path", type=str, help="Timestamp path to process.")
        parser_separate_level_distortion.add_argument("lnd_filename", type=str, help="LND filename.")
        parser_separate_level_distortion.add_argument("fundamental_filename", type=str, help="Fundamental filename.")
        parser_separate_level_distortion.add_argument("h2_filename", type=str, help="H2 filename.")
        parser_separate_level_distortion.add_argument("h3_filename", type=str, help="H3 filename.")

        # Construct path
        parser_construct_path = subparsers.add_parser("construct_path", help="Construct path.")
        parser_construct_path.add_argument("paths", type=str, nargs='+', help="List of paths to join.")

    def generate_timestamp_subpath(self):
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m/%d/%H_%M_%S")
        return os.path.normpath(subpath)

    def convert_timestamp_path_to_extension(self, timestamp_path):
        """Convert a timestamp path to an underscore-separated extension format."""
        parts = timestamp_path.split(os.path.sep)
        date_part = parts[:3]
        time_part = parts[3].split('_')
        extension = f"_{date_part[0]}_{date_part[1]}_{date_part[2]}_{time_part[0]}_{time_part[1]}_{time_part[2]}"
        return os.path.normpath(extension)

    def separate_level_and_distortion(self, results_path, timestamp_extension, lnd_filename, fundamental_filename, h2_filename, h3_filename):
        """Separate level and distortion."""
        # Construct the full filename
        csv_filename = f"{lnd_filename}{timestamp_extension}.csv"
        csv_path = os.path.join(results_path, csv_filename)

        # Load the LevelAndDistortion CSV file
        try:
            df = pd.read_csv(csv_path, skiprows=2)
        except FileNotFoundError:
            return

        # Ensure the results directory exists
        os.makedirs(results_path, exist_ok=True)

        # Extract data for each channel
        channels = ["Fundamental", "H2", "H3"]
        filenames = [fundamental_filename, h2_filename, h3_filename]
        for i, (channel, filename) in enumerate(zip(channels, filenames)):
            channel_df = df.iloc[:, [2 * i, 2 * i + 1]].copy()
            channel_df.columns = ["Hz", "dBSPL1"]
            channel_df.dropna(how='all', inplace=True)  # Remove rows with all NaN values
            channel_filename = f"{filename}{timestamp_extension}.csv"
            channel_path = os.path.join(results_path, channel_filename)
            
            # Write the DataFrame to a CSV file with the correct headers
            with open(channel_path, 'w', newline='') as f:
                f.write(f'"{channel}",\n')
                f.write('Ch1,\n')
                f.write('X,Y\n')
                channel_df.to_csv(f, index=False, header=False)

    def construct_path(self, paths):
        """Construct path by joining the list of paths."""
        joined_path = os.path.normpath(os.path.join(*paths))
        return joined_path

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
