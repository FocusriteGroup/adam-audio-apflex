import socket
import json
import sys
import logging
import argparse

# Configure logging for the client
logging.basicConfig(
    filename="ap_client.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

class APClient:
    def __init__(self, host="127.0.0.1", port=65432):
        self.host = host
        self.port = port
        self.command_map = {
            "wake_up": self.wake_up,
            "generate_timestamp_extension": self.generate_timestamp_extension,
            "construct_path": self.construct_path,
            "get_timestamp_subpath": self.get_timestamp_subpath,
            "generate_file_prefix": self.generate_file_prefix,
            "activate_measurement": self.activate_measurement,
            "set_average": self.set_average,
        }
        self.parser = argparse.ArgumentParser(description="AP Client Command Processor")
        subparsers = self.parser.add_subparsers(dest="command", required=True)

        # Define subparsers for each command
        subparsers.add_parser("wake_up", help="Wake up the server.")

        subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")

        parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
        parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")

        subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")

        parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
        parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")

        parser_activate_measurement = subparsers.add_parser("activate_measurement", help="Activate a measurement.")
        parser_activate_measurement.add_argument("measurement_name", type=str, help="Name of the measurement to activate.")

        parser_set_average = subparsers.add_parser("set_average", help="Set the number of averages.")
        parser_set_average.add_argument("averages", type=int, help="Number of averages to set.")

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
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.host, self.port))
                client_socket.send(json.dumps(command).encode("utf-8"))
                logging.info(f"Sent command: {command}")

                if wait_for_response:
                    response = client_socket.recv(1024).decode("utf-8")
                    logging.info(f"Received response: {response}")
                    return response
                else:
                    logging.info("No response expected for this command.")
                    return None
        except (socket.error, json.JSONDecodeError) as e:
            logging.error(f"Error: {e}")
            return f"Error: {e}"

    def wake_up(self, args):
        command = {"action": "wake_up", "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def generate_timestamp_extension(self, args):
        command = {"action": "generate_timestamp_extension"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def construct_path(self, args):
        command = {"action": "construct_path", "paths": args.paths}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def get_timestamp_subpath(self, args):
        command = {"action": "get_timestamp_subpath"}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def generate_file_prefix(self, args):
        command = {"action": "generate_file_prefix", "strings": args.strings}
        response = self.send_command(command, wait_for_response=True)
        print(response)

    def activate_measurement(self, args):
        command = {"action": "activate_measurement", "measurement_name": args.measurement_name, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def set_average(self, args):
        if args.averages <= 0:
            logging.error("'averages' must be a positive integer.")
            sys.exit(1)
        command = {"action": "set_average", "averages": args.averages, "wait_for_response": False}
        self.send_command(command, wait_for_response=False)

    def parse_and_execute(self):
        """
        Parse command-line arguments and execute the appropriate function.
        """
        args = self.parser.parse_args()
        command = args.command
        if command in self.command_map:
            self.command_map[command](args)
        else:
            logging.error(f"Unknown command: {command}")
            sys.exit(1)


if __name__ == "__main__":
    client = APClient()
    client.parse_and_execute()