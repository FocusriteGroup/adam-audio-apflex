import socket
import threading
import json
import queue
from ap_utilities import Utilities, AudioPrecisionAPI
from ap_logger import Logger
import argparse


class CommandServer:

    def __init__(self, host="127.0.0.1", port=65432, use_ui=False):
        self.host = host
        self.port = port
        self.utilities = Utilities()
        self.audio_precision_api = AudioPrecisionAPI(server_host=self.host, server_port=self.port)
        self.log_queue = queue.Queue()
        self.logger = Logger(log_queue=self.log_queue,
                             use_ui=use_ui,
                             server=self)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.bind((self.host, self.port))
        except OSError as e:
            raise RuntimeError(f"Failed to bind to {self.host}:{self.port} - {e}") from e
        self.server.listen(5)
        self.running = True

    def log(self, message):
        """Add a log message to the queue."""
        if self.log_queue:
            self.log_queue.put(message)

    def handle_client(self, client_socket):
        """Handle incoming client connections."""
        try:
            while True:
                data = client_socket.recv(1024).decode("utf-8")
                
                if not data:
                    break
                self.log(f"Received data: {data}")
                command = json.loads(data)
                response = self.process_command(command)
                if response:  # Only send a response if one is expected
                    self.log(f"Sending response: {response}")  # Debugging output
                    client_socket.send(response.encode("utf-8"))
        except (json.JSONDecodeError, socket.error) as e:
            self.log(f"Error in handle_client: {e}")
        finally:
            client_socket.close()

    def process_command(self, command):
        """Process a command and return the result."""
        try:
            if not isinstance(command, dict):
                return "Error: Invalid command format."

            # Handle commands from the client
            if "action" in command:
                if command["action"] == "set_averages":
                    averages = command.get("averages")
                    if averages is None:
                        return "Error: 'averages' is required."
                    threading.Thread(target=self.audio_precision_api.set_averages, args=(averages,)).start()
                    return None
                elif command["action"] == "get_timestamp_subpath":
                    return self.utilities.generate_timestamp_subpath()
                elif command["action"] == "generate_timestamp_extension":
                    return self.utilities.generate_timestamp_extension()
                elif command["action"] == "construct_path":
                    paths = command.get("paths")
                    if not paths or not isinstance(paths, list):
                        return "Error: 'paths' must be a list of strings."
                    if not all(isinstance(p, str) for p in paths):
                        return "Error: All elements in 'paths' must be strings."
                    return self.utilities.construct_path(paths)
                elif command["action"] == "generate_file_prefix":
                    strings = command.get("strings")
                    if not strings or not isinstance(strings, list):
                        return "Error: 'strings' must be a list of strings."
                    if not all(isinstance(s, str) for s in strings):
                        return "Error: All elements in 'strings' must be strings."
                    return self.utilities.generate_file_prefix(strings)
                elif command["action"] == "wake_up":
                    self.audio_precision_api.wake_up()
                    return "API woke up successfully."
                else:
                    return "Error: Unknown command."
            else:
                return "Error: Command must contain an 'action'."
        except (KeyError, TypeError, ValueError) as e:
            return f"Error: {e}"

    def start(self):
        """Start the server."""
        self.logger.start()
        self.log(f"Server started on {self.host}:{self.port}")
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        """Accept incoming client connections."""
        self.log("Waiting for connections...")
        while self.running:
            try:
                client_socket, addr = self.server.accept()
                self.log(f"Connection received from {addr}")
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.start()
            except OSError as e:
                if self.running:
                    self.log(f"Error accepting connection: {e}")

    def stop(self):
        """Stop the server."""
        self.running = False
        self.server.close()
        self.logger.stop()
        self.log("Server stopped.")

    @classmethod
    def run(cls):
        """Run the server as a self-contained application."""

        parser = argparse.ArgumentParser(description="Command Server with optional UI.")
        parser.add_argument("--use-ui", action="store_true", help="Enable the user interface.")
        args = parser.parse_args()

        server = cls(use_ui=args.use_ui)
        server.start()

        try:
            if args.use_ui:
                server.logger.start_ui()
            else:
                threading.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.stop()


if __name__ == "__main__":
    CommandServer.run()
