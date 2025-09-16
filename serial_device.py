import serial
import serial.tools.list_ports
import threading
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger("SerialDevice")

class SerialDevice:
    """Base class for serial devices with connection management."""

    def __init__(self, vendor_id=None, product_id=None, baudrate=9600, timeout=3, retry_interval=5):
        """
        Initialize the SerialDevice.

        Args:
            vendor_id (int): The Vendor ID of the device in hexadecimal (e.g., 0x0C2E).
            product_id (int): The Product ID of the device in hexadecimal (e.g., 0x0B6A).
            baudrate (int): The baud rate for the serial communication (default: 9600).
            timeout (float): Timeout for reading from the serial port in seconds.
            retry_interval (int): Time in seconds to wait before retrying connection.
        """
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.baudrate = baudrate
        self.timeout = timeout
        self.retry_interval = retry_interval

        # Connection state
        self.serial_connection = None
        self.connected = False
        self.current_port = None
        
        # Threading
        self.lock = threading.Lock()
        self._stop_monitoring = False
        self._monitor_thread = None

    def find_device(self):
        """
        Find the serial device based on VID/PID.
        
        Returns:
            serial.tools.list_ports.ListPortInfo: Found port info or None
        """
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            # If no VID/PID specified, return first available port
            if self.vendor_id is None and self.product_id is None:
                LOGGER.info(f"Found port (no VID/PID filter): {port.device}")
                return port
            
            # Check VID/PID match
            vid_match = self.vendor_id is None or port.vid == self.vendor_id
            pid_match = self.product_id is None or port.pid == self.product_id
            
            if vid_match and pid_match:
                LOGGER.info(f"Found device: {port.device} (VID=0x{port.vid:04X}, PID=0x{port.pid:04X})")
                return port
        
        return None

    def connect(self):
        """
        Connect to the serial device.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        with self.lock:
            if self.connected:
                LOGGER.info("Device already connected")
                return True
            
            port_info = self.find_device()
            if not port_info:
                LOGGER.warning("Device not found")
                return False
            
            try:
                self.serial_connection = serial.Serial(
                    port_info.device, 
                    baudrate=self.baudrate, 
                    timeout=self.timeout
                )
                self.current_port = port_info.device
                self.connected = True
                LOGGER.info(f"Connected to {port_info.device}")
                return True
                
            except serial.SerialException as e:
                LOGGER.error(f"Failed to connect: {e}")
                self.serial_connection = None
                self.connected = False
                return False

    def disconnect(self):
        """Disconnect from the serial device."""
        with self.lock:
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.close()
                    LOGGER.info(f"Disconnected from {self.current_port}")
                except Exception as e:
                    LOGGER.error(f"Error during disconnect: {e}")
                
            self.serial_connection = None
            self.connected = False
            self.current_port = None

    def is_connected(self):
        """
        Check if device is connected and port is still available.
        
        Returns:
            bool: True if connected and port available, False otherwise
        """
        with self.lock:
            if not self.connected or not self.serial_connection:
                return False
            
            if not self.serial_connection.is_open:
                self.connected = False
                return False
            
            # Check if port still exists
            if not self.find_device():
                self.connected = False
                if self.serial_connection:
                    try:
                        self.serial_connection.close()
                    except:
                        pass
                    self.serial_connection = None
                return False
            
            return True

    def write(self, data):
        """
        Write data to the serial device.
        
        Args:
            data (bytes or str): Data to write
            
        Returns:
            bool: True if write successful, False otherwise
        """
        if not self.is_connected():
            LOGGER.error("Device not connected")
            return False
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            bytes_written = self.serial_connection.write(data)
            LOGGER.debug(f"Wrote {bytes_written} bytes")
            return True
            
        except Exception as e:
            LOGGER.error(f"Write error: {e}")
            return False

    def read(self, size=1):
        """
        Read data from the serial device.
        
        Args:
            size (int): Number of bytes to read
            
        Returns:
            bytes: Read data or empty bytes if error
        """
        if not self.is_connected():
            LOGGER.error("Device not connected")
            return b''
        
        try:
            data = self.serial_connection.read(size)
            if data:
                LOGGER.debug(f"Read {len(data)} bytes")
            return data
            
        except Exception as e:
            LOGGER.error(f"Read error: {e}")
            return b''

    def readline(self):
        """
        Read a line from the serial device.
        
        Returns:
            bytes: Read line or empty bytes if error
        """
        if not self.is_connected():
            LOGGER.error("Device not connected")
            return b''
        
        try:
            data = self.serial_connection.readline()
            if data:
                LOGGER.debug(f"Read line: {data}")
            return data
            
        except Exception as e:
            LOGGER.error(f"Readline error: {e}")
            return b''

    def start_monitoring(self):
        """Start monitoring thread for automatic reconnection."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            LOGGER.info("Monitoring already started")
            return
        
        self._stop_monitoring = False
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
        LOGGER.info("Started connection monitoring")

    def stop_monitoring(self):
        """Stop monitoring thread."""
        self._stop_monitoring = True
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        LOGGER.info("Stopped connection monitoring")

    def _monitor_connection(self):
        """Monitor connection and attempt reconnection if needed."""
        while not self._stop_monitoring:
            if not self.is_connected():
                LOGGER.info("Attempting to reconnect...")
                self.connect()
            
            time.sleep(self.retry_interval)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()
        self.disconnect()