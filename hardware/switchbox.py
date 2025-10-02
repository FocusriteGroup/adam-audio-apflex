"""
SwitchBox Audio Routing Control

Advanced control for audio routing switch boxes used in 
Audio Precision production line for channel switching and device management.
"""
from .serial_device import SerialDevice
import threading
import time
import logging

SWITCHBOX_LOGGER = logging.getLogger("SwitchBox")

class SwitchBox(SerialDevice):
    """Class for managing a SwitchBox device."""

    def __init__(self, baudrate=9600, product_id=0x000A, vendor_id=0x2E8A, timeout=3, retry_interval=2, on_connect=None, on_disconnect=None):
        """
        Initialize the SwitchBox.

        Args:
            baudrate (int): The baud rate for the serial communication (default: 9600).
            product_id (int): The Product ID of the SwitchBox in hexadecimal (default: 0x000A).
            vendor_id (int): The Vendor ID of the SwitchBox in hexadecimal (default: 0x2E8A).
            timeout (float): Timeout for reading from the serial port in seconds.
            retry_interval (int): Time in seconds to wait before retrying connection.
            on_connect (callable): Callback function for successful connection.
            on_disconnect (callable): Callback function for disconnection.
        """
        super().__init__(baudrate, product_id, vendor_id, timeout, retry_interval, on_connect, on_disconnect)
        self.box_status = None
        self.channel = None
        self._message_thread = None
        self._stop_message_thread = threading.Event()
        self._message_received_event = threading.Event()  # Event to signal when a message is received
        self.status_updated_event = threading.Event()
        

    def start_listening(self):
        """
        Start the thread to listen for messages from the SwitchBox.
        """
        if self._message_thread is None or not self._message_thread.is_alive():
            self._stop_message_thread.clear()
            self._message_thread = threading.Thread(target=self._listen_for_messages_thread, daemon=True)
            self._message_thread.start()
            SWITCHBOX_LOGGER.info("Started listening thread for SwitchBox messages.")

    def stop_listening(self):
        """
        Stop the thread that listens for messages from the SwitchBox.
        """
        if self._message_thread and self._message_thread.is_alive():
            self._stop_message_thread.set()
            self._message_thread.join()
            SWITCHBOX_LOGGER.info("Stopped listening thread for SwitchBox messages.")

    def wait_for_message(self, timeout=None):
        """
        Wait for a message to be received by the listener.

        Args:
            timeout (float): Maximum time to wait for a message in seconds. If None, wait indefinitely.

        Returns:
            bool: True if a message was received, False if the timeout occurred.
        """
        return self._message_received_event.wait(timeout)

    def wait_for_status_update(self, timeout=None):
        """
        Wait for the status to be updated.

        Args:
            timeout (float): Maximum time to wait for the status update in seconds. If None, wait indefinitely.

        Returns:
            bool: True if the status was updated, False if the timeout occurred.
        """
        updated = self.status_updated_event.wait(timeout)
        if updated:
            SWITCHBOX_LOGGER.info("Status update detected.")
        else:
            SWITCHBOX_LOGGER.warning("Timeout while waiting for status update.")
        
        # Reset the event for future updates
        self.status_updated_event.clear()
        return updated

    def _listen_for_messages_thread(self):
        """
        Internal method to run `listen_for_messages` in a thread.
        """
        if not self.serial_connected or not self.serial_connection or not self.serial_connection.is_open:
            SWITCHBOX_LOGGER.warning("_listen_for_messages_thread: Serial connection is not established.")
            return

        SWITCHBOX_LOGGER.info("Listening for messages from the SwitchBox...")
        try:
            while not self._stop_message_thread.is_set():
                if self.serial_connection.in_waiting > 0:
                    message = self.serial_connection.readline().decode(errors='ignore').strip()
                    SWITCHBOX_LOGGER.info(f"Received message: {message}")
                    self._message_received_event.set()  # Signal that a message was received
                    
                    self.update_status(message)

                    
                    
                time.sleep(0.1)  # Prevent CPU overuse
        except Exception as e:
            SWITCHBOX_LOGGER.error(f"Error while listening for messages: {e}")
        finally:
            SWITCHBOX_LOGGER.info("Stopped listening for messages.")

    def update_status(self, message):
        """Update the status of the SwitchBox based on a received message."""
        if len(message) == 1:
            message = message.zfill(2)

        if len(message) == 2 and all(bit in "01" for bit in message):
            with self._lock:
                self.channel = 2 if message[0] == "1" else 1
                self.box_status = "Open" if message[1] == "1" else "Closed"
                SWITCHBOX_LOGGER.info(f"SwitchBox status updated: channel={self.channel}, box_status={self.box_status}")
                
                # Set the event to signal that the status has been updated
                self.status_updated_event.set()

    def get_status(self):
        """
        Send a `GET_STATUS` message to the SwitchBox without waiting for a response.
        """
        self.send_command("GET_STATUS")
        self.wait_for_status_update(timeout=5)
        with self._lock:
            SWITCHBOX_LOGGER.info(f"SwitchBox status: channel={self.channel}, box_status={self.box_status}")
            return {"channel": self.channel, "box_status": self.box_status}

    def switch_to_channel(self, target_channel):
        """
        Switch the SwitchBox to the specified channel.
        """
        if target_channel not in [1, 2]:
            SWITCHBOX_LOGGER.error("switch_to_channel: Invalid channel. Only channel 1 or 2 is supported.")
            raise ValueError("Invalid channel. Only channel 1 or 2 is supported.")
        
        with self._lock:  # Protect access to self.channel
            if self.channel == target_channel:
                SWITCHBOX_LOGGER.info(f"SwitchBox already on channel {target_channel}")
                return self.channel
        
        command = "SET_CHANNEL_1" if target_channel == 1 else "SET_CHANNEL_2"
        
        self.send_command(command)

        SWITCHBOX_LOGGER.info(f"SwitchBox switched to channel {target_channel}")
        self.wait_for_status_update(timeout=5)

        return self.channel
    
    def open_box(self):
        """
        Open the SwitchBox.
        """
        with self._lock:  # Protect access to self.box_status
            if self.box_status == "Open":
                SWITCHBOX_LOGGER.info("SwitchBox is already open.")
                return self.box_status

        self.send_command("OPEN_BOX")

        while True:
            with self._lock:
                if self.box_status == "Open":
                    break

        SWITCHBOX_LOGGER.info("SwitchBox opened.")

        return self.box_status

    def send_command(self, command):
        """
        Send a custom command to the SwitchBox.

        Args:
            command (str): The command string to send.
        """
        with self._lock:
            if not self.serial_connected or not self.serial_connection or not self.serial_connection.is_open:
                SWITCHBOX_LOGGER.warning("send_command: Serial connection is not established.")
                return

            try:
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(command.encode() + b"\n")  # Send the custom command
                SWITCHBOX_LOGGER.info(f"Command '{command}' sent.")
                self._message_received_event.wait(timeout=5)  # Wait for a response
                if not self._message_received_event.is_set():
                    SWITCHBOX_LOGGER.warning(f"No response received for command '{command}'.")

                self._message_received_event.clear()  # Reset the event for the next message
                
            except Exception as e:
                SWITCHBOX_LOGGER.error(f"Error while sending command '{command}': {e}")