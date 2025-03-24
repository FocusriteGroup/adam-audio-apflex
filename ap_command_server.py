import socket
import threading
import json
import queue
from ap_utilities import Utilities, AudioPrecisionAPI
from ap_logger import Logger

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
            raise RuntimeError(f"Failed to bind to {self.host}:{self.port} - {e}")
        self.server.listen(5)
        self.running = True
        self.operation_status = "idle"  # Track the status of the last operation

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
                command = json.loads(data)
                response = self.process_command(command)
                client_socket.send(response.encode("utf-8"))
                self.log(f"Received: {command}")
                self.log(f"Responded: {response}")
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            client_socket.close()

    def process_command(self, command):
        """Process a command and return the result."""
        try:
            if not isinstance(command, dict):
                return "Error: Invalid command format."

            # Handle commands from the client
            if "action" in command:
                if command["action"] == "get_status":
                    return self.operation_status
                elif command["action"] == "set_averages":
                    averages = command.get("averages")
                    if averages is None:
                        return "Error: 'averages' is required."
                    # Offload the API call to a separate thread
                    self.handle_api_call(self.audio_precision_api.set_averages, averages)
                    return "Setting averages in the background."
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
                else:
                    return "Error: Unknown command."
            else:
                return "Error: Command must contain an 'action'."
        except Exception as e:
            return f"Error: {e}"

    def handle_api_call(self, api_function, *args):
        """Run an API function in a separate thread."""
        def api_thread():
            try:
                self.operation_status = "running"
                result = api_function(*args)
                self.operation_status = "complete"
                self.log(f"API call result: {result}")
            except Exception as e:
                self.operation_status = "error"
                self.log(f"Error during API call: {e}")

        threading.Thread(target=api_thread, daemon=True).start()

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
        import argparse

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
