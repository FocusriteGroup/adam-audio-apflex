import socket
import json
from datetime import datetime

def discover_service():
    """Auto-discover ADAM Service IP."""
    try:
        # Verwende die Workstation für Discovery
        import subprocess
        import sys
        
        # Verwende adam_connector für Discovery
        result = subprocess.run([
            sys.executable, "adam_connector.py", "--find"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            service_ip = result.stdout.strip()
            print(f"✅ Auto-discovered ADAM Service: {service_ip}")
            return service_ip
        else:
            print("❌ Auto-discovery failed")
            return None
    except Exception as e:
        print(f"❌ Discovery error: {e}")
        return None

def test_switchbox_logging():
    """Test SwitchBox operation logging to ADAM Service."""
    # Auto-discover oder fallback
    service_host = discover_service()
    if not service_host:
        service_host = "192.168.14.91"  # Manual fallback
        print(f"Using manual fallback: {service_host}")
    
    service_port = 65432
    
    # Test verschiedene SwitchBox-Operationen
    test_cases = [
        {
            "name": "SwitchBox set_channel success",
            "command": {
                "action": "log_workstation_task",
                "workstation_id": "TEST-WORKSTATION-001",
                "task_type": "switchbox",
                "operation": "set_channel",
                "result": "success",
                "task_data": {"channel": 1, "response_time": 0.15},
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "SwitchBox open_box success", 
            "command": {
                "action": "log_workstation_task",
                "workstation_id": "TEST-WORKSTATION-001",
                "task_type": "switchbox",
                "operation": "open_box",
                "result": "success",
                "task_data": {"duration": 3.2, "box_status": "open"},
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "SwitchBox set_channel error",
            "command": {
                "action": "log_workstation_task",
                "workstation_id": "TEST-WORKSTATION-001",
                "task_type": "switchbox",
                "operation": "set_channel",
                "result": "error",
                "task_data": {"channel": 2, "error": "Hardware not responding"},
                "timestamp": datetime.now().isoformat()
            }
        }
    ]
    
    print("Testing ADAM Service Workstation Logging...")
    print(f"Connecting to: {service_host}:{service_port}")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(5.0)  # 5 Sekunden Timeout
                client_socket.connect((service_host, service_port))
                
                # Command senden
                command_json = json.dumps(test_case['command'])
                print(f"Sending: {command_json}")
                client_socket.send(command_json.encode("utf-8"))
                
                # Response empfangen
                response = client_socket.recv(1024).decode("utf-8")
                print(f"Response: {response}")
                
                # Response parsen und validieren
                try:
                    response_data = json.loads(response)
                    if response_data.get("status") == "logged":
                        print("✅ SUCCESS: Message logged successfully")
                    else:
                        print(f"❌ UNEXPECTED: {response_data}")
                except json.JSONDecodeError:
                    print(f"❌ ERROR: Invalid JSON response: {response}")
                    
        except socket.timeout:
            print("❌ ERROR: Connection timeout")
        except ConnectionRefusedError:
            print("❌ ERROR: Connection refused - is ADAM Service running?")
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("\nCheck the ADAM Service log for the logged messages:")
    print("  File: logs/adam_audio/adam_service_log_2025-09-29.log")
    print("\nExpected log entries:")
    print("  WORKSTATION[TEST-WORKSTATION-001] SWITCHBOX.set_channel result=success...")
    print("  WORKSTATION[TEST-WORKSTATION-001] SWITCHBOX.open_box result=success...")
    print("  WORKSTATION[TEST-WORKSTATION-001] SWITCHBOX.set_channel result=error...")

def test_scanner_logging():
    """Test Scanner operation logging (für später)."""
    service_host = "192.168.14.191"
    service_port = 65432
    
    test_command = {
        "action": "log_workstation_task",
        "workstation_id": "TEST-WORKSTATION-001",
        "task_type": "scanner",
        "operation": "scan_serial",
        "result": "success",
        "task_data": {"serial_number": "A7X-2024-001234", "scan_time": 1.5},
        "timestamp": datetime.now().isoformat()
    }
    
    print("\nTesting Scanner Logging...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(5.0)
            client_socket.connect((service_host, service_port))
            client_socket.send(json.dumps(test_command).encode("utf-8"))
            response = client_socket.recv(1024).decode("utf-8")
            print(f"Scanner Test Response: {response}")
    except Exception as e:
        print(f"Scanner Test Error: {e}")

if __name__ == "__main__":
    # Service Connection Test
    print("ADAM Service Workstation Logging Test")
    print("====================================")
    
    # SwitchBox Tests (fokussiert auf SwitchBox wie gewünscht)
    test_switchbox_logging()
    
    # Optional: Scanner Test (für später)
    # test_scanner_logging()