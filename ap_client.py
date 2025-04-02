import socket
import json
import sys
import logging

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

    def handle_action(self, action, args):
        """
        Parse and handle the action with its arguments.

        Args:
            action (str): The action to perform.
            args (list): Additional arguments for the action.

        Returns:
            None
        """
        if action == "wake_up":
            command = {"action": "wake_up", "wait_for_response": False}
            wait_for_response = False
        elif action == "generate_timestamp_extension":
            command = {"action": "generate_timestamp_extension"}
            wait_for_response = True
        elif action == "construct_path":
            if len(args) < 1:
                logging.error("Usage: python ap_client.py construct_path <string1> <string2> ...")
                sys.exit(1)
            paths = args
            command = {"action": "construct_path", "paths": paths}
            wait_for_response = True
        elif action == "get_timestamp_subpath":
            command = {"action": "get_timestamp_subpath"}
            wait_for_response = True
        elif action == "generate_file_prefix":
            if len(args) < 1:
                logging.error("Usage: python ap_client.py generate_file_prefix <string1> <string2> ...")
                sys.exit(1)
            strings = args
            command = {"action": "generate_file_prefix", "strings": strings}
            wait_for_response = True
        elif action == "activate_measurement":
            if len(args) < 1:
                logging.error("Usage: python ap_client.py activate_measurement <measurement_name>")
                sys.exit(1)
            measurement_name = args[0]
            command = {"action": "activate_measurement", "measurement_name": measurement_name, "wait_for_response": False}
            wait_for_response = False
        elif action == "set_average":
            if len(args) < 1:
                logging.error("Usage: python ap_client.py set_average <averages>")
                sys.exit(1)
            try:
                averages = int(args[0])
            except ValueError:
                logging.error("'averages' must be a positive integer.")
                sys.exit(1)
            command = {"action": "set_average", "averages": averages, "wait_for_response": False}
            wait_for_response = False
        else:
            logging.error(f"Error: Unknown action '{action}'")
            sys.exit(1)

        # Send the command to the server
        logging.info(f"Connecting to server.")
        response = self.send_command(command, wait_for_response)

        # Print the response if one is expected
        if wait_for_response and response is not None:
            print(response)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error("Usage: python ap_client.py <action> [parameters...]")
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]  # Additional arguments for the action

    client = APClient()
    client.handle_action(action, args)