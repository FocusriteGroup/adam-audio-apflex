# ADAM Audio Production System

A comprehensive client-server architecture for automating hardware control and device testing in ADAM Audio's production environment. This system provides seamless integration between Audio Precision test equipment, OCA-enabled audio devices, serial hardware, and production workflows.

---

## 🏗️ **System Architecture**

```
┌─────────────────┐    Network (TCP/IP)     ┌─────────────────┐
│ ADAM Workstation│ ──── (192.168.1.x) ───▶│   ADAM Service  │
│                 │                         │                 │
│ - Commands      │    Helper Functions     │ - Calculations  │
│ - Hardware Mgmt │    Biquad Calculations  │ - File Ops      │
│ - LOCAL OCA     │    Logging Requests     │ - Discovery     │
│   (OCP1Wrapper) │                         │ - Trials Mgmt   │
└─────────┬───────┘                         └─────────────────┘
          │ Direct Hardware Access
          ├──── Serial (USB) ────▶ Scanner/SwitchBox
          └──── Network (OCA) ───▶ ADAM Audio Devices
```

### **Core Components**

- **`adam_service.py`** - Centralized calculation and support service
- **`adam_workstation.py`** - Command-line interface for hardware control
- **`adam_connector.py`** - Service discovery and connection management
- **`oca/`** - OCA device communication modules
- **`hardware/`** - Serial device interfaces
- **`serial_managers/`** - Hardware management layer
- **`helpers.py`** - Production utilities and helper functions

---

## 🚀 **Quick Start**

### **1. Start the Service**
```bash
# Auto-discovery and startup
python adam_service.py

# Manual startup with specific parameters
python adam_service.py --host 0.0.0.0 --port 65432 --service-name "ADAMService"
```

### **2. Discover Available Services**
```bash
# Find all ADAM services on network
python adam_connector.py --find

# Find specific service
python adam_connector.py --find --service-name "ADAMService"
```

### **3. Execute Commands**
```bash
# OCA device control (local execution)
python adam_workstation.py --host 192.168.1.166 get_serial_number 192.168.10.20 50001
python adam_workstation.py --host 192.168.1.166 set_mute unmuted 192.168.10.20 50001

# Serial hardware control
python adam_workstation.py --host 192.168.1.166 set_channel 3
python adam_workstation.py --host 192.168.1.166 scan_serial

# Service calculations
python adam_workstation.py --host 192.168.1.166 get_biquad_coefficients bell 3.0 1000 1.4 48000
```

---

## 📋 **Complete Command Reference**

### **🔊 OCA Device Commands**

#### **Device Information**
```bash
# Get device identification
python adam_workstation.py --host <SERVICE_IP> get_serial_number <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> get_model_description <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> get_firmware_version <DEVICE_IP> <PORT>

# Examples
python adam_workstation.py --host 192.168.1.166 get_serial_number 192.168.10.20 50001
python adam_workstation.py --host 192.168.1.166 get_model_description 192.168.10.20 50001
```

#### **Audio Control**
```bash
# Gain control
python adam_workstation.py --host <SERVICE_IP> get_gain <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_gain <VALUE> <DEVICE_IP> <PORT>

# Mute control
python adam_workstation.py --host <SERVICE_IP> get_mute <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_mute <muted|unmuted> <DEVICE_IP> <PORT>

# Examples
python adam_workstation.py --host 192.168.1.166 set_gain 0.5 192.168.10.20 50001
python adam_workstation.py --host 192.168.1.166 set_mute unmuted 192.168.10.20 50001
```

#### **Input/Mode Configuration**
```bash
# Audio input selection
python adam_workstation.py --host <SERVICE_IP> get_audio_input <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_audio_input <POSITION> <DEVICE_IP> <PORT>

# Operating mode control
python adam_workstation.py --host <SERVICE_IP> get_mode <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_mode <POSITION> <DEVICE_IP> <PORT>

# Phase delay adjustment
python adam_workstation.py --host <SERVICE_IP> get_phase_delay <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_phase_delay <POSITION> <DEVICE_IP> <PORT>
```

#### **Biquad Filter Control**
```bash
# Get/Set device biquad filters
python adam_workstation.py --host <SERVICE_IP> get_device_biquad <INDEX> <DEVICE_IP> <PORT>
python adam_workstation.py --host <SERVICE_IP> set_device_biquad <INDEX> '<COEFFICIENTS_JSON>' <DEVICE_IP> <PORT>

# Example
python adam_workstation.py --host 192.168.1.166 get_device_biquad 0 192.168.10.20 50001
python adam_workstation.py --host 192.168.1.166 set_device_biquad 0 '[1.0, 0.5, 0.25, 0.125, 0.0625]' 192.168.10.20 50001
```

### **🔧 Serial Hardware Commands**

#### **SwitchBox Control**
```bash
# Channel switching
python adam_workstation.py --host <SERVICE_IP> set_channel <1|2|3|4>
python adam_workstation.py --host <SERVICE_IP> get_channel

# Box control
python adam_workstation.py --host <SERVICE_IP> open_box
python adam_workstation.py --host <SERVICE_IP> close_box

# Examples
python adam_workstation.py --host 192.168.1.166 set_channel 3
python adam_workstation.py --host 192.168.1.166 open_box
```

#### **Scanner Operations**
```bash
# Barcode scanning
python adam_workstation.py --host <SERVICE_IP> scan_serial
python adam_workstation.py --host <SERVICE_IP> trigger_scan

# Example
python adam_workstation.py --host 192.168.1.166 scan_serial
```

### **📊 Calculation Services**

#### **Biquad Filter Design**
```bash
# Generate biquad coefficients
python adam_workstation.py --host <SERVICE_IP> get_biquad_coefficients <TYPE> <GAIN> <FREQ> <Q> <SAMPLE_RATE>

# Filter types: bell, lowpass, highpass, lowshelf, highshelf, notch
# Examples
python adam_workstation.py --host 192.168.1.166 get_biquad_coefficients bell 3.0 1000 1.4 48000
python adam_workstation.py --host 192.168.1.166 get_biquad_coefficients lowpass 0 5000 0.707 48000
python adam_workstation.py --host 192.168.1.166 get_biquad_coefficients highshelf -2.5 8000 1.0 48000
```

### **📁 File & Path Utilities**
```bash
# Timestamp generation
python adam_workstation.py --host <SERVICE_IP> generate_timestamp_extension
python adam_workstation.py --host <SERVICE_IP> get_timestamp_subpath

# Path construction
python adam_workstation.py --host <SERVICE_IP> construct_path <BASE_PATH> <SUB_PATH>
python adam_workstation.py --host <SERVICE_IP> generate_file_prefix <SERIAL_NUMBER>

# Examples
python adam_workstation.py --host 192.168.1.166 generate_timestamp_extension
python adam_workstation.py --host 192.168.1.166 construct_path "C:/Data" "Measurements"
```

### **📈 Production Tracking**
```bash
# Measurement trial validation
python adam_workstation.py --host <SERVICE_IP> check_measurement_trials <SERIAL> <CSV_PATH> <MAX_TRIALS>

# Example
python adam_workstation.py --host 192.168.1.166 check_measurement_trials "ADAM123456" "C:/Production/trials.csv" 3
```

---

## 🏭 **Production Workflow Integration**

### **Typical Test Sequence**
```bash
#!/bin/bash
# ADAM Audio Production Test Script

SERVICE_IP="192.168.1.166"
DEVICE_IP="192.168.10.20"
DEVICE_PORT="50001"

# 1. Scan device serial number
SERIAL=$(python adam_workstation.py --host $SERVICE_IP scan_serial)
echo "Testing device: $SERIAL"

# 2. Check measurement trials
TRIAL_CHECK=$(python adam_workstation.py --host $SERVICE_IP check_measurement_trials "$SERIAL" "C:/Production/trials.csv" 3)
if [[ $TRIAL_CHECK == *"Maximum"* ]]; then
    echo "Device exceeded trial limit"
    exit 1
fi

# 3. Configure test setup
python adam_workstation.py --host $SERVICE_IP set_channel 1
python adam_workstation.py --host $SERVICE_IP set_mute unmuted $DEVICE_IP $DEVICE_PORT

# 4. Set test configuration
python adam_workstation.py --host $SERVICE_IP set_gain 0.0 $DEVICE_IP $DEVICE_PORT
python adam_workstation.py --host $SERVICE_IP set_audio_input "AES3" $DEVICE_IP $DEVICE_PORT

# 5. Apply measurement filters
COEFFS=$(python adam_workstation.py --host $SERVICE_IP get_biquad_coefficients bell 3.0 1000 1.4 48000)
python adam_workstation.py --host $SERVICE_IP set_device_biquad 0 "$COEFFS" $DEVICE_IP $DEVICE_PORT

# 6. Run Audio Precision measurements
# ... AP test sequence ...

# 7. Reset device
python adam_workstation.py --host $SERVICE_IP set_mute muted $DEVICE_IP $DEVICE_PORT
```

### **Integration with Audio Precision**
```python
# Python integration example
import subprocess
import json

class ADAMTestInterface:
    def __init__(self, service_ip="192.168.1.166"):
        self.service_ip = service_ip
        
    def execute_command(self, command):
        """Execute ADAM workstation command."""
        cmd = ["python", "adam_workstation.py", "--host", self.service_ip] + command
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    
    def setup_device(self, device_ip, device_port):
        """Setup device for testing."""
        self.execute_command(["set_mute", "unmuted", device_ip, str(device_port)])
        self.execute_command(["set_gain", "0.0", device_ip, str(device_port)])
        
    def get_biquad_coefficients(self, filter_type, gain, freq, q, sample_rate):
        """Get biquad coefficients for measurement."""
        result = self.execute_command([
            "get_biquad_coefficients", filter_type, str(gain), 
            str(freq), str(q), str(sample_rate)
        ])
        return json.loads(result)

# Usage in AP test
adam = ADAMTestInterface()
adam.setup_device("192.168.10.20", 50001)
coeffs = adam.get_biquad_coefficients("bell", 3.0, 1000, 1.4, 48000)
```

---

## 🛠️ **Hardware Configuration**

### **Supported OCA Devices**
- **ADAM Audio Studio Monitors** (A-Series, S-Series)
- **ADAM Audio Subwoofers** (Sub Series)
- **Custom OCA-enabled devices** via OCP1 protocol

### **Serial Hardware**
- **SwitchBox**: Custom USB relay controller for audio routing
- **Honeywell Scanners**: USB barcode scanners for device identification
- **Custom Serial Devices**: Extensible via hardware abstraction layer

### **Network Configuration**
```yaml
# Network topology
Production Network: 192.168.1.0/24
  - Service Host: 192.168.1.166:65432
  - Workstations: 192.168.1.100-200
  
OCA Device Network: 192.168.10.0/24
  - ADAM Devices: 192.168.10.20-100
  - Default Port: 50001
```

---

## 📦 **Installation & Setup**

### **Prerequisites**
```bash
# Python 3.8+ required
python --version

# Required packages
pip install pyserial
pip install argparse
pip install json
pip install socket
pip install threading
```

### **Custom Dependencies**
```bash
# ADAM Audio specific modules (internal)
pip install oca_tools
pip install biquad_tools

# Or place in local path:
# oca_tools/oca_utilities.py
# biquad_tools/biquad_designer.py
```

### **Directory Structure**
```
Audio-Precision/
├── adam_service.py              # Main service
├── adam_workstation.py          # Command interface  
├── adam_connector.py            # Service discovery
├── helpers.py                   # Production utilities
├── hardware/                    # Hardware abstraction
│   ├── __init__.py
│   ├── serial_device.py         # Base serial device
│   ├── honeywell_scanner.py     # Scanner interface
│   └── switchbox.py            # SwitchBox interface
├── serial_managers/             # Hardware managers
│   ├── __init__.py
│   ├── scanner_manager.py       # Scanner management
│   └── switchbox_manager.py     # SwitchBox management
├── oca/                         # OCA device modules
│   ├── __init__.py
│   ├── oca_device.py           # OCA hardware interface
│   └── oca_manager.py          # OCA management
├── logs/                        # System logs
│   ├── service/                # Service logs
│   └── workstation/            # Workstation logs
└── README.md                   # This file
```

---

## 📊 **Logging & Monitoring**

### **Service Logs**
```bash
# Service activity
logs/service/adam_service_YYYYMMDD.log

# Log format
2025-10-02 15:30:45 INFO [ADAMService] WORKSTATION[WS-001] OCA.set_mute result=Success - Data: {"target_ip": "192.168.10.20", "port": 50001, "state": "unmuted"}
```

### **Workstation Logs**
```bash
# Workstation activity  
logs/workstation/adam_workstation_YYYYMMDD.log

# Log format
2025-10-02 15:30:45 INFO [AdamWorkstation] Executing 'set_mute' to unmuted on OCA device 192.168.10.20:50001
```

### **Monitoring Commands**
```bash
# Check service status
python adam_connector.py --find --service-name "ADAMService"

# Monitor logs in real-time
tail -f logs/service/adam_service_$(date +%Y%m%d).log
tail -f logs/workstation/adam_workstation_$(date +%Y%m%d).log
```

---

## 🔧 **Configuration**

### **Service Configuration**
```python
# adam_service.py parameters
HOST = "0.0.0.0"                    # Bind to all interfaces
PORT = 65432                        # Service port
DISCOVERY_PORT = 65433              # Discovery broadcast port
SERVICE_NAME = "ADAMService"        # Service identifier
LOG_LEVEL = logging.INFO            # Logging verbosity
```

### **Hardware Configuration**
```python
# Serial device settings
SCANNER_VENDOR_ID = 0x0C2E          # Honeywell scanner
SCANNER_PRODUCT_ID = 0x0B61         
SWITCHBOX_VENDOR_ID = 0x2341        # Arduino-based SwitchBox
SWITCHBOX_PRODUCT_ID = 0x8037

# OCA device settings
DEFAULT_OCA_PORT = 50001            # Standard OCP1 port
OCA_TIMEOUT = 5                     # Connection timeout (seconds)
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Service Discovery Problems**
```bash
# Check if service is running
python adam_connector.py --find

# Check network connectivity
ping 192.168.1.166

# Check firewall settings
netsh advfirewall firewall show rule name="ADAM Service"
```

#### **OCA Device Communication**
```bash
# Test device connectivity
ping 192.168.10.20

# Check OCA port accessibility
telnet 192.168.10.20 50001

# Verify OCA device status
python adam_workstation.py --host 192.168.1.166 get_serial_number 192.168.10.20 50001
```

#### **Serial Hardware Issues**
```bash
# List available serial ports
python -c "import serial.tools.list_ports; [print(p) for p in serial.tools.list_ports.comports()]"

# Check USB device recognition
# Windows: Device Manager > Ports (COM & LPT)
# Linux: lsusb | grep -E "(0C2E|2341)"
```

### **Error Messages**

| Error | Cause | Solution |
|-------|-------|----------|
| `Service not found` | Service not running | Start adam_service.py |
| `Connection refused` | Wrong IP/port | Check service discovery |
| `OCA device timeout` | Device offline | Check device power/network |
| `Serial device not found` | USB disconnected | Reconnect hardware |
| `Maximum trials reached` | Production limit | Check trials CSV file |

---

## 📈 **Performance & Scaling**

### **System Limits**
- **Concurrent Workstations**: 50+ simultaneous connections
- **OCA Device Latency**: <100ms typical response time
- **Serial Operations**: <50ms scan/switch operations
- **Service Throughput**: 1000+ commands/minute

### **Optimization Tips**
```python
# Batch OCA operations for efficiency
def configure_device_batch(device_ip, device_port):
    adam = ADAMTestInterface()
    adam.execute_command(["set_mute", "unmuted", device_ip, str(device_port)])
    adam.execute_command(["set_gain", "0.0", device_ip, str(device_port)]) 
    adam.execute_command(["set_audio_input", "AES3", device_ip, str(device_port)])
    
# Use fire-and-forget logging for performance
adam.log_to_service(operation="batch_setup", wait_for_response=False)
```

---

## 🔒 **Security & Safety**

### **Network Security**
- Service runs on private production network (192.168.1.0/24)
- No internet connectivity required
- Authentication via workstation identification
- All communications logged and auditable

### **Hardware Safety**
- **Relay switching**: Software interlocks prevent invalid states
- **Audio signals**: Mute controls prevent damage during switching
- **Serial communication**: Error handling prevents device lockup
- **Production limits**: Trial counting prevents excessive testing

### **Data Protection**
- All logs stored locally in production environment
- No sensitive data transmitted over network
- CSV files contain only serial numbers and test results
- Automatic log rotation prevents disk space issues

---

## 📚 **API Reference**

### **Service API (JSON over TCP)**
```python
# Command format
{
    "action": "command_name",
    "parameter1": "value1",
    "parameter2": "value2",
    "wait_for_response": true
}

# Response format
{
    "status": "success|error",
    "result": "command_result",
    "timestamp": "2025-10-02T15:30:45"
}
```

### **OCA Manager API**
```python
from oca.oca_manager import OCAManager

# Initialize manager
oca = OCAManager(workstation_id="WS-001", service_client=None)

# Device control
result = oca.get_serial_number("192.168.10.20", 50001)
result = oca.set_gain(0.5, "192.168.10.20", 50001)
result = oca.set_device_biquad(0, [1,0,0,0,0], "192.168.10.20", 50001)
```

### **Hardware Manager API**
```python
from serial_managers.scanner_manager import ScannerManager
from serial_managers.switchbox_manager import SwitchBoxManager

# Hardware control
scanner = ScannerManager("WS-001")
serial_number = scanner.scan_serial()

switchbox = SwitchBoxManager("WS-001")
switchbox.set_channel(3)
```

---

## 🤝 **Contributing**

This system is maintained by ADAM Audio's production engineering team. For modifications or extensions:

1. **Follow existing patterns** in hardware/ and serial_managers/
2. **Add comprehensive logging** for all operations
3. **Test with actual hardware** before deployment
4. **Update documentation** for new commands
5. **Coordinate with production team** for deployment

### **Development Workflow**
```bash
# 1. Create feature branch
git checkout -b feature/new-oca-command

# 2. Implement changes
# - Add to oca/oca_device.py (hardware interface)
# - Add to oca/oca_manager.py (management layer)  
# - Add to adam_workstation.py (command interface)

# 3. Test thoroughly
python adam_workstation.py --host 192.168.1.166 new_command args...

# 4. Update documentation
# - Add to README.md command reference
# - Update help text in argument parser

# 5. Submit for review
git commit -m "Add new OCA command: new_command"
git push origin feature/new-oca-command
```

---

## 📄 **License**

This project is proprietary to ADAM Audio (Focusrite Group). All rights reserved.

**Internal use only - Not for distribution**

---

## 📞 **Support**

For technical support or questions regarding this system:

- **Production Engineering**: Internal ADAM Audio team
- **Hardware Issues**: Contact production floor supervisors  
- **Software Issues**: Repository maintainers
- **OCA Integration**: ADAM Audio DSP team

**Emergency Contact**: Production floor emergency procedures

---

*Last updated: October 2025*
*ADAM Audio Production System v2.0*
