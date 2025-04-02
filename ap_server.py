import socket
import threading
import json
import logging
from ap_utils import Utilities
from api_calls import AudioPrecisionAPI  # Import the Utilities class and AudioPrecisionAPI class

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ap_server.log"),
        logging.StreamHandler()
    ]
)

class APServer:
    def __init__(self, host="127.0.0.1", port=65432):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.running = True
        self.audio_precision_api = AudioPrecisionAPI()  # Initialize the AudioPrecisionAPI instance
        logging.info(f"Server started on {self.host}:{self.port}")

    def handle_client(self, client_socket):
        """Handle communication with a connected client."""
        try:
            while True:
                data = client_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                logging.info(f"Received: {data}")
                try:
                    command = json.loads(data)
                    response = self.process_command(command)

                    # Check if the client expects a response
                    if command.get("wait_for_response", True):  # Default to True if not specified
                        client_socket.send(response.encode("utf-8"))
                        logging.info(f"Sent response: {response}")
                    else:
                        logging.info("No response sent.")
                except json.JSONDecodeError:
                    logging.error("Invalid JSON received.")
                    client_socket.send(b"Error: Invalid JSON format.")
                except Exception as e:
                    logging.error(f"Error processing command: {e}")
                    client_socket.send(f"Error: {e}".encode("utf-8"))
        except (socket.error, Exception) as e:
            logging.error(f"Connection error: {e}")
        finally:
            client_socket.close()

    def process_command(self, command):
        """Process a command and return a response."""
        if not isinstance(command, dict) or "action" not in command:
            return "Error: Invalid command format."

        action = command["action"]
        command_map = {
            "wake_up": lambda: self.audio_precision_api.wake_up() or "API woke up successfully.",
            "activate_measurement": lambda: self._activate_measurement(command),
            "set_average": lambda: self._set_average(command),
            "generate_timestamp_extension": Utilities.generate_timestamp_extension,
            "construct_path": lambda: self._construct_path(command),
            "get_timestamp_subpath": Utilities.generate_timestamp_subpath,
            "generate_file_prefix": lambda: self._generate_file_prefix(command),
        }

        if action in command_map:
            try:
                return command_map[action]()
            except Exception as e:
                logging.error(f"Error processing action '{action}': {e}")
                return f"Error: {e}"
        else:
            return "Error: Unknown action."

    def _activate_measurement(self, command):
        measurement_name = command.get("measurement_name")
        if not measurement_name or not isinstance(measurement_name, str):
            return "Error: 'measurement_name' must be a non-empty string."
        self.audio_precision_api.activate_measurement(measurement_name)
        return "Measurement activation initiated."

    def _set_average(self, command):
        averages = command.get("averages")
        if not isinstance(averages, int) or averages <= 0:
            return "Error: 'averages' must be a positive integer."
        return self.audio_precision_api.set_average(averages)

    def _construct_path(self, command):
        paths = command.get("paths")
        if not paths or not isinstance(paths, list):
            return "Error: 'paths' must be a non-empty list of strings."
        if not all(isinstance(p, str) for p in paths):
            return "Error: All elements in 'paths' must be strings."
        return Utilities.construct_path(paths)

    def _generate_file_prefix(self, command):
        strings = command.get("strings")
        if not strings or not isinstance(strings, list):
            return "Error: 'strings' must be a non-empty list of strings."
        if not all(isinstance(s, str) for s in strings):
            return "Error: All elements in 'strings' must be strings."
        return Utilities.generate_file_prefix(strings)

    def start(self):
        """Start accepting client connections."""
        print("Server is running...")
        logging.info("Waiting for connections...")
        while self.running:
            client_socket, addr = self.server.accept()
            logging.info(f"Connection from {addr}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def stop(self):
        """Stop the server."""
        self.running = False
        self.server.close()
        logging.info("Server stopped.")

if __name__ == "__main__":
    server = APServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()