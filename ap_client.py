import socket
import json
import sys
import logging
import argparse
import os
from datetime import datetime

# Unterverzeichnis "logs" erstellen, falls es noch nicht existiert
log_dir = "logs/client"
os.makedirs(log_dir, exist_ok=True)

# Heutiges Datum im Format JJJJ-MM-TT
today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"{log_dir}/ap_client_log_{today}.log"


# Configure logging for the client
logging.basicConfig(
    filename=log_filename,  # Log file to store client logs
    level=logging.INFO,  # Log level set to INFO
    format="%(asctime)s - %(levelname)s - %(message)s"  # Log format with timestamp
)

logging.info("----------------------------------- APClient started")

class APClient:
    """
    A client class to communicate with the APServer.

    This class provides methods to send commands to the server and process responses.
    It uses command-line arguments to determine which command to execute.
    """

    def __init__(self, host="127.0.0.1", port=65432):
        """
        Initialize the APClient.

        Args:
            host (str): The server's hostname or IP address. Default is "127.0.0.1".
            port (int): The server's port number. Default is 65432.
        """
        self.host = host
        self.port = port

        # Map of commands to their corresponding methods
        self.command_map = {
            "wake_up": self.wake_up,
            "generate_timestamp_extension": self.generate_timestamp_extension,
            "construct_path": self.construct_path,
            "get_timestamp_subpath": self.get_timestamp_subpath,
            "generate_file_prefix": self.generate_file_prefix,
            "activate_measurement": self.activate_measurement,
            "set_average": self.set_average,
            "set_channel": self.set_channel,
            "open_box": self.open_box,
            "scan_serial": self.scan_serial,
            "get_biquad_coefficients": self.get_biquad_coefficients,
            "set_device_biquad": self.set_device_biquad,
        }

        # Argument parser for command-line arguments
        self.parser = argparse.ArgumentParser(description="AP Client Command Processor")
        subparsers = self.parser.add_subparsers(dest="command", required=True)

        # Define subparsers for each command
        subparsers.add_parser("wake_up", help="Wake up the server.")

        subparsers.add_parser("generate_timestamp_extension",
                              help="Generate a timestamp extension.")

        parser_construct_path = subparsers.add_parser("construct_path",
                                                      help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+",
                                           help="List of paths to join.")

        subparsers.add_parser("get_timestamp_subpath",
                              help="Get a timestamp subpath.")

        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix",
                                                            help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+",
                                                 help="List of strings to combine.")

        parser_activate_measurement = subparsers.add_parser("activate_measurement",
                                                            help="Activate a measurement.")
        parser_activate_measurement.add_argument("measurement_name", type=str,
                                                 help="Name of the measurement to activate.")

        parser_set_average = subparsers.add_parser("set_average",
                                                   help="Set the number of averages.")
        parser_set_average.add_argument("averages", type=int, 
                                        help="Number of averages to set.")

        parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
        parser_set_channel.add_argument("channel", type=int, choices=[1, 2],
                                        help="Channel to set (1 or 2).")

        subparsers.add_parser("open_box",
                              help="Open the box.")

        subparsers.add_parser("scan_serial",
                              help="Scan the serial number.")

        # Add biquad coefficients command
        biquad_parser = subparsers.add_parser("get_biquad_coefficients",
                                              help="Get biquad filter coefficients")
        biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"],
                                   help="Type of biquad filter")
        biquad_parser.add_argument("gain", type=float,
                                   help="Gain in dB")
        biquad_parser.add_argument("peak_freq", type=float,
                                   help="Peak frequency in Hz")
        biquad_parser.add_argument("Q", type=float,
                                   help="Quality factor")
        biquad_parser.add_argument("sample_rate", type=int,
                                   help="Sample rate in Hz")

        # Subparser for "set_device_biquad" command
        set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
        set_biquad_parser.add_argument("index", type=int, help="Biquad index")
        set_biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        set_biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        set_biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        set_biquad_parser.add_argument("Q", type=float, help="Quality factor")
        set_biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")
        set_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_biquad_parser.add_argument("port", type=int, help="OCA device port")

    def send_command(self, command, wait_for_response=True):
        """
        Send a command to the server and optionally wait for a response.

        Args:
            command (dict): The command to send to the server.
            wait_for_response (bool): Whether to wait for a response from the server.

        Returns:
            str: The server's response if wait_for_response is True, otherwise None.
        """
        try:
            logging.info("Connecting to server at %s:%s...", self.host, self.port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.host, self.port))  # Connect to the server
                logging.info("Connected to server. Sending command: %s", command)
                client_socket.send(json.dumps(command).encode("utf-8"))  # Send the command as JSON

                if wait_for_response:
                    response = client_socket.recv(1024).decode("utf-8")  # Receive and decode the server's response
                    logging.info("Received response from server: %s", response)
                    return response
                else:
                    logging.info("No response expected for this command.")
                    return None
        except socket.error as e:
            logging.error(f"Socket error: {e}")
            return f"Error: {e}"
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return f"Error: {e}"

    # Command methods
    def wake_up(self, args): # deprecated
        """Send a command to wake up the server."""
        logging.info("Executing 'wake_up' command.")
        command = {"action": "wake_up", "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def generate_timestamp_extension(self, args):
        """Request the server to generate a timestamp extension."""
        logging.info("Executing 'generate_timestamp_extension' command.")
        command = {"action": "generate_timestamp_extension"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def construct_path(self, args):
        """Request the server to construct a path from the provided components."""
        logging.info(f"Executing 'construct_path' command with paths: {args.paths}")
        command = {"action": "construct_path", "paths": args.paths}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_timestamp_subpath(self, args):
        """Request the server to generate a timestamp subpath."""
        logging.info("Executing 'get_timestamp_subpath' command.")
        command = {"action": "get_timestamp_subpath"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def generate_file_prefix(self, args):
        """Request the server to generate a file prefix from the provided strings."""
        logging.info(f"Executing 'generate_file_prefix' command with strings: {args.strings}")
        command = {"action": "generate_file_prefix", "strings": args.strings}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def activate_measurement(self, args):
        """Request the server to activate a specific measurement."""
        logging.info(f"Executing 'activate_measurement' command for measurement: {args.measurement_name}")
        command = {"action": "activate_measurement", "measurement_name": args.measurement_name, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def set_average(self, args):
        """Request the server to set the number of averages."""
        if args.averages <= 0:
            logging.error("'averages' must be a positive integer.")
            sys.exit(1)
        logging.info(f"Executing 'set_average' command with averages: {args.averages}")
        command = {"action": "set_average", "averages": args.averages, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def set_channel(self, args):
        """Request the server to set the channel on the SwitchBox."""
        logging.info(f"Executing 'set_channel' command with channel: {args.channel}")
        command = {"action": "set_channel", "channel": args.channel, "wait_for_response": True}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def open_box(self, args):
        """Request the server to open the box."""
        logging.info("Executing 'open_box' command.")
        command = {"action": "open_box", "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def scan_serial(self, args):
        """Request the server to scan a serial number."""
        logging.info("Executing 'scan_serial' command.")
        command = {"action": "scan_serial", "wait_for_response": True}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_biquad_coefficients(self, args):
        """
        Request the server to calculate biquad filter coefficients.
        """
        logging.info(f"Executing 'get_biquad_coefficients' with: "
                     f"type={args.filter_type}, gain={args.gain}, peak_freq={args.peak_freq}, Q={args.Q}, sample_rate={args.sample_rate}")
        command = {
            "action": "get_biquad_coefficients",
            "filter_type": args.filter_type,
            "gain": args.gain,
            "peak_freq": args.peak_freq,
            "Q": args.Q,
            "sample_rate": args.sample_rate,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def set_device_biquad(self, args):
        """
        Request the server to calculate biquad coefficients and set them on the OCA device.
        """
        logging.info(f"Executing 'set_device_biquad' with: "
                     f"index={args.index}, type={args.filter_type}, gain={args.gain}, "
                     f"peak_freq={args.peak_freq}, Q={args.Q}, sample_rate={args.sample_rate}, "
                     f"target_ip={args.target_ip}, port={args.port}")
        command = {
            "action": "set_device_biquad",
            "index": args.index,
            "filter_type": args.filter_type,
            "gain": args.gain,
            "peak_freq": args.peak_freq,
            "Q": args.Q,
            "sample_rate": args.sample_rate,
            "target_ip": args.target_ip,
            "port": args.port,
            "wait_for_response": True
        }
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def setup_arg_parser(self):
        """
        Set up the argument parser for command-line arguments.
        """
        parser = argparse.ArgumentParser(description="AP Client")
        subparsers = parser.add_subparsers(dest="command", required=True)

        # Subparser for "wake_up" command
        subparsers.add_parser("wake_up", help="Wake up the server.")

        # Subparser for "generate_timestamp_extension" command
        subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")

        # Subparser for "construct_path" command
        parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")

        # Subparser for "get_timestamp_subpath" command
        subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")

        # Subparser for "generate_file_prefix" command
        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")

        # Subparser for "activate_measurement" command
        parser_activate_measurement = subparsers.add_parser("activate_measurement", help="Activate a measurement.")
        parser_activate_measurement.add_argument("measurement_name", type=str, help="Name of the measurement to activate.")

        # Subparser for "set_average" command
        parser_set_average = subparsers.add_parser("set_average", help="Set the number of averages.")
        parser_set_average.add_argument("averages", type=int, help="Number of averages to set.")

        # Subparser for "set_channel" command
        parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
        parser_set_channel.add_argument("channel", type=int, choices=[1, 2], help="Channel to set (1 or 2).")

        # Subparser for "open_box" command
        subparsers.add_parser("open_box", help="Open the box.")

        # Subparser for "scan_serial" command
        subparsers.add_parser("scan_serial", help="Scan the serial number.")

        # Add biquad coefficients command
        biquad_parser = subparsers.add_parser("get_biquad_coefficients", help="Get biquad filter coefficients")
        biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        biquad_parser.add_argument("Q", type=float, help="Quality factor")
        biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")

        # Subparser for "set_device_biquad" command
        set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
        set_biquad_parser.add_argument("index", type=int, help="Biquad index")
        set_biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
        set_biquad_parser.add_argument("gain", type=float, help="Gain in dB")
        set_biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
        set_biquad_parser.add_argument("Q", type=float, help="Quality factor")
        set_biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")
        set_biquad_parser.add_argument("target_ip", type=str, help="OCA device IP address")
        set_biquad_parser.add_argument("port", type=int, help="OCA device port")

        self.parser = parser

    def parse_and_execute(self):
        """
        Parse command-line arguments and execute the appropriate function.
        """
        args = self.parser.parse_args()  # Parse the arguments
        command = args.command  # Get the command name
        logging.info(f"Parsing and executing command: {command}")
        if command in self.command_map:
            self.command_map[command](args)  # Execute the corresponding method
        else:
            logging.error(f"Unknown command: {command}")
            sys.exit(1)


if __name__ == "__main__":
    # Create an instance of APClient and execute the parsed command
    client = APClient()
    client.parse_and_execute()
