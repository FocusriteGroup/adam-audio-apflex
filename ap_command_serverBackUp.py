import socket
import threading
import json
import datetime
import os
import tkinter as tk
from tkinter import scrolledtext
import time  # Import time module for timestamps

class Utilities:
    """Handles various utility functions."""

    def generate_timestamp_subpath(self):
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m/%d/%H_%M_%S")
        return os.path.normpath(subpath)

    def convert_timestamp_path_to_extension(self, timestamp_path):
        """Convert a timestamp path to an underscore-separated extension format."""
        normalized_path = os.path.normpath(timestamp_path)
        parts = normalized_path.split(os.path.sep)
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

class CommandServer:
    """A simple TCP server to receive and process commands."""

    def __init__(self, host="127.0.0.1", port=65432, use_ui=False):
        self.host = host
        self.port = port
        self.utilities = Utilities()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.use_ui = use_ui
        self.ui = None
        if self.use_ui:
            self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        print("Initializing UI...")  # Debug print
        self.ui = tk.Tk()
        self.ui.title("Command Server")
        # Adjust the width and height of the ScrolledText widget
        self.text_area = scrolledtext.ScrolledText(self.ui, wrap=tk.WORD, width=160, height=20)  # Increased width to 80
        self.text_area.pack(padx=10, pady=10)
        self.text_area.insert(tk.END, "Server started...\n")
        self.text_area.configure(state="disabled")

    def log_to_ui(self, message, include_timestamp=True):
        """Log a message to the UI, optionally with a timestamp."""
        if self.ui:
            if include_timestamp:
                timestamp = time.strftime("[%d.%m.%Y %H:%M:%S]")  # Format: [DD.MM.YYYY HH:MM:SS]
                message = f"{timestamp} {message}"
            self.text_area.configure(state="normal")
            self.text_area.insert(tk.END, f"{message}\n")
            self.text_area.configure(state="disabled")
            self.text_area.see(tk.END)

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
                
                # Log messages
                received_message = f"Received: {command}"
                responded_message = f"Responded: {response}"
                
                # Log to console
                print(received_message)
                print(responded_message)
                
                # Log to UI (timestamps are added automatically)
                self.log_to_ui(received_message)
                self.log_to_ui(responded_message)
        except Exception as e:
            error_message = f"Error: {e}"
            print(error_message)  # Console output
            self.log_to_ui(error_message)  # UI output
        finally:
            client_socket.close()

    def process_command(self, command):
        """Process a command and return the result."""
        try:
            if command["action"] == "get_timestamp_subpath":
                return self.utilities.generate_timestamp_subpath()
            elif command["action"] == "convert_timestamp_path_to_extension":
                return self.utilities.convert_timestamp_path_to_extension(command["timestamp_path"])
            elif command["action"] == "construct_path":
                return self.utilities.construct_path(command["paths"])
            else:
                return "Error: Unknown command."
        except Exception as e:
            return f"Error: {e}"

    def start(self):
        """Start the server."""
        print(f"Server started on {self.host}:{self.port}")
        self.log_to_ui(f"Server started on {self.host}:{self.port}")
        threading.Thread(target=self.accept_connections, daemon=True).start()
        if self.use_ui:
            print("Starting UI main loop...")
            self.ui.mainloop()
        else:
            # Keep the main thread alive when not using the UI
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                print("Server stopped.")

    def accept_connections(self):
        """Accept incoming client connections."""
        print("Waiting for connections...")
        self.log_to_ui("Waiting for connections...")
        while True:
            client_socket, addr = self.server.accept()
            log_message = f"Connection received from {addr}"
            print(log_message)
            self.log_to_ui(log_message)
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_handler.start()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Command Server with optional UI.")
    parser.add_argument("--use-ui", action="store_true", help="Enable the user interface.")
    args = parser.parse_args()

    server = CommandServer(use_ui=args.use_ui)
    server.start()