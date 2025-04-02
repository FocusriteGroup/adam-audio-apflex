import socket
import json
import sys
import logging
import time

class CommandClient:

    def __init__(self, host="127.0.0.1", port=65432, log_file="client.log"):
        self.host = host
        self.port = port

        # Set up logging
        self.logger = logging.getLogger("CommandClient")
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def send_command(self, cmd, wait_for_response=True):
        """Send a command to the server and optionally wait for a response."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                self.logger.info("Connecting to server at %s:%s", self.host, self.port)
                client.connect((self.host, self.port))
                self.logger.info("Connected to server. Sending command: %s", cmd)

                client.send(json.dumps(cmd).encode("utf-8"))
                

                if wait_for_response:
                    server_response = client.recv(1024).decode("utf-8")
                    self.logger.info("Received response: %s", server_response)
                    return server_response
                else:
                    self.logger.info("Command sent. Not waiting for a response.")
                    return None
        except (socket.error, json.JSONDecodeError) as e:
            self.logger.error("Error sending command: %s", e)
            sys.exit(1)

    def parse_arguments(self, args):
        """Parse command-line arguments into a command dictionary."""
        if len(args) < 1:
            self.logger.error("No command provided.")
            sys.exit(1)

        command_name = args[0]
        if command_name == "get_timestamp_subpath":
            command = {"action": "get_timestamp_subpath"}
        elif command_name == "generate_timestamp_extension":
            command = {"action": "generate_timestamp_extension"}
        elif command_name == "construct_path":
            if len(args) < 2:
                self.logger.error("Missing parameters for 'construct_path'.")
                sys.exit(1)
            paths = args[1:]
            if not all(isinstance(p, str) for p in paths):
                self.logger.error("All elements in 'paths' must be strings.")
                sys.exit(1)
            command = {"action": "construct_path", "paths": paths}
        elif command_name == "generate_file_prefix":
            if len(args) < 2:
                self.logger.error("Missing strings for 'generate_file_prefix'.")
                sys.exit(1)
            strings = args[1:]
            if not all(isinstance(s, str) for s in strings):
                self.logger.error("All elements in 'strings' must be strings.")
                sys.exit(1)
            command = {"action": "generate_file_prefix", "strings": strings}
        elif command_name == "set_averages":
            if len(args) < 2:
                self.logger.error("Missing parameter for 'set_averages'.")
                sys.exit(1)
            try:
                averages = int(args[1])
            except ValueError:
                self.logger.error("Invalid parameter for 'set_averages'. Must be an integer.")
                sys.exit(1)
            command = {"action": "set_averages", "averages": averages}
        
        else:
            self.logger.error("Unknown command: %s", command_name)
            sys.exit(1)

        self.logger.info("Parsed command: %s", command)
        return command

if __name__ == "__main__":
    client = CommandClient()

    # Parse the command-line arguments into a command dictionary
    parsed_command = client.parse_arguments(sys.argv[1:])

    # Determine if the command requires a response
    wait_for_response = parsed_command["action"] not in ["set_averages"]

    # Send the command to the server
    response = client.send_command(parsed_command, wait_for_response=wait_for_response)

    time.sleep(1)  # Optional delay to ensure the server has time to process the command

    # Print the response if one is expected
    if response is not None:
        print(response)