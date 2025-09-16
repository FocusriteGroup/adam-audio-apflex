import time
import logging
from serial_device import SerialDevice

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_basic_connection():
    """Test basic connection without VID/PID filtering."""
    print("\n=== Testing Basic Connection (No VID/PID Filter) ===")
    
    device = SerialDevice()
    
    print(f"Attempting to connect...")
    success = device.connect()
    print(f"Connection successful: {success}")
    
    if success:
        print(f"Connected to: {device.current_port}")
        print(f"Is connected: {device.is_connected()}")
        
        # Test writing some data
        print("Testing write...")
        device.write("Hello\n")
        
        time.sleep(1)
        
        # Test reading
        print("Testing read...")
        data = device.read(100)
        print(f"Read data: {data}")
    
    device.disconnect()
    print("Disconnected")

def test_with_vid_pid():
    """Test connection with specific VID/PID."""
    print("\n=== Testing Connection with VID/PID ===")
    
    # Example VID/PID - adjust these for your device
    vid = 0x0C2E  # Honeywell VID
    pid = 0x0B6A  # Honeywell PID
    
    device = SerialDevice(vendor_id=vid, product_id=pid)
    
    print(f"Looking for device with VID=0x{vid:04X}, PID=0x{pid:04X}")
    success = device.connect()
    print(f"Connection successful: {success}")
    
    if success:
        print(f"Connected to: {device.current_port}")
    else:
        print("Device not found or connection failed")
    
    device.disconnect()

def test_context_manager():
    """Test using the device as a context manager."""
    print("\n=== Testing Context Manager ===")
    
    try:
        with SerialDevice() as device:
            if device.is_connected():
                print(f"Connected via context manager to: {device.current_port}")
                device.write("Test message\n")
                time.sleep(0.5)
                response = device.readline()
                print(f"Response: {response}")
            else:
                print("Failed to connect via context manager")
    except Exception as e:
        print(f"Context manager error: {e}")

def test_monitoring():
    """Test automatic monitoring and reconnection."""
    print("\n=== Testing Monitoring and Reconnection ===")
    
    device = SerialDevice(retry_interval=2)
    
    # Start monitoring
    device.start_monitoring()
    
    print("Monitoring started. Connect/disconnect your device to see reconnection...")
    print("Will monitor for 30 seconds...")
    
    start_time = time.time()
    while time.time() - start_time < 30:
        status = "Connected" if device.is_connected() else "Disconnected"
        port = device.current_port if device.current_port else "None"
        print(f"Status: {status}, Port: {port}")
        time.sleep(3)
    
    device.stop_monitoring()
    device.disconnect()
    print("Monitoring test completed")

def list_available_ports():
    """List all available serial ports."""
    print("\n=== Available Serial Ports ===")
    import serial.tools.list_ports
    
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found")
        return
    
    for port in ports:
        print(f"Port: {port.device}")
        print(f"  Description: {port.description}")
        print(f"  VID: 0x{port.vid:04X} (VID={port.vid})" if port.vid else "  VID: None")
        print(f"  PID: 0x{port.pid:04X} (PID={port.pid})" if port.pid else "  PID: None")
        print(f"  Serial Number: {port.serial_number}")
        print()

def interactive_test():
    """Interactive test menu."""
    device = SerialDevice()
    
    while True:
        print("\n=== Serial Device Interactive Test ===")
        print("1. Connect")
        print("2. Disconnect") 
        print("3. Check connection status")
        print("4. Write data")
        print("5. Read data")
        print("6. Read line")
        print("7. Start monitoring")
        print("8. Stop monitoring")
        print("9. List ports")
        print("0. Exit")
        
        choice = input("Enter choice: ").strip()
        
        if choice == "1":
            success = device.connect()
            print(f"Connect result: {success}")
            
        elif choice == "2":
            device.disconnect()
            print("Disconnected")
            
        elif choice == "3":
            connected = device.is_connected()
            port = device.current_port
            print(f"Connected: {connected}, Port: {port}")
            
        elif choice == "4":
            if device.is_connected():
                data = input("Enter data to write: ")
                success = device.write(data + "\n")
                print(f"Write result: {success}")
            else:
                print("Device not connected")
                
        elif choice == "5":
            if device.is_connected():
                size = int(input("Enter number of bytes to read (default 100): ") or "100")
                data = device.read(size)
                print(f"Read data: {data}")
            else:
                print("Device not connected")
                
        elif choice == "6":
            if device.is_connected():
                data = device.readline()
                print(f"Read line: {data}")
            else:
                print("Device not connected")
                
        elif choice == "7":
            device.start_monitoring()
            print("Monitoring started")
            
        elif choice == "8":
            device.stop_monitoring()
            print("Monitoring stopped")
            
        elif choice == "9":
            list_available_ports()
            
        elif choice == "0":
            device.stop_monitoring()
            device.disconnect()
            break
            
        else:
            print("Invalid choice")

if __name__ == "__main__":
    print("Serial Device Test Script")
    print("=" * 50)
    
    # First, list available ports
    list_available_ports()
    
    # Run tests
    test_basic_connection()
    test_with_vid_pid()
    test_context_manager()
    
    # Uncomment to test monitoring (takes 30 seconds)
    # test_monitoring()
    
    # Uncomment for interactive testing
    # interactive_test()
    
    print("\nAll tests completed!")