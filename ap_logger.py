import threading
import time
import tkinter as tk
from tkinter import scrolledtext
import queue

class Logger(threading.Thread):
    """Asynchronous logger that processes messages from a queue."""

    def __init__(self, log_queue, use_ui=False, log_file="server.log", server=None):
        super().__init__(daemon=True)
        self.log_queue = log_queue
        self.use_ui = use_ui
        self.log_file = log_file
        self.running = True 
        self.ui = None
        self.server = server  
        if self.use_ui:
            self.init_ui()

    def init_ui(self):
        """Initialize the user interface for logging."""
        self.ui = tk.Tk()
        self.ui.title("Logger")
        self.text_area = scrolledtext.ScrolledText(self.ui, wrap=tk.WORD, width=160, height=30)
        self.text_area.pack(padx=10, pady=10)
        self.text_area.configure(state="disabled")

        self.ui.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Handle the UI window close event."""
        if self.server:
            self.server.stop()
        self.stop()  
        if self.ui:
            self.ui.destroy()

    def run(self):
        """Process messages from the queue."""
        while self.running or not self.log_queue.empty():
            try:
                message = self.log_queue.get(timeout=1)  
                timestamp = time.strftime("[%d.%m.%Y %H:%M:%S]")
                formatted_message = f"{timestamp} {message}"
                self.log_to_console(formatted_message)
                self.log_to_file(formatted_message)
                if self.use_ui:
                    self.log_to_ui(formatted_message)
            except queue.Empty:
                continue

    def log_to_console(self, message):
        """Log a message to the console."""
        print(message)

    def log_to_file(self, message):
        """Log a message to a file."""
        with open(self.log_file, "a", encoding="utf-8") as file:
            file.write(message + "\n")

    def log_to_ui(self, message):
        """Log a message to the user interface."""
        if self.ui:
            self.text_area.configure(state="normal")
            self.text_area.insert(tk.END, f"{message}\n")
            self.text_area.configure(state="disabled")
            self.text_area.see(tk.END)

    def start_ui(self):
        """Start the UI main loop."""
        if self.use_ui and self.ui:
            self.ui.mainloop()

    def stop(self):
        """Stop the logger."""
        self.running = False
        