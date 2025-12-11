import os
import re
import time

from oca_tools.oca_utilities import OCP1ToolWrapper

# Discover devices
wrapper = OCP1ToolWrapper(target_ip=None, port=None)
output = wrapper.run_cli_command(command="discover", options={"--timeout": 2})
print("Discovered devices:", output)

time.sleep(.1)  # Small delay to ensure clarity in output

# Use the first discovered device for further commands
devices = output.get("devices", [])
if devices:
    device = devices[0]
    ip = device.get("ip")
    port = int(device.get("port")) if device.get("port") else None
    print(f"Using device: {device.get('name')} at {ip}:{port}")

    # Gain calibration get
    wrapper = OCP1ToolWrapper(target_ip=ip, port=port)
    result_get = wrapper.run_cli_command(command="gain-calibration", subcommand="get")
    print("Get gain calibration:", result_get)

    time.sleep(.1)

    # Gain calibration set
    result_set = wrapper.run_cli_command(command="gain-calibration", subcommand="set", options={"--value": 2.0})
    print("Set gain calibration:", result_set)
    
    time.sleep(.1)

    result_set = wrapper.run_cli_command(command="audio-input", subcommand="set", options={"--position": "analogue-xlr"})
    print(result_set)  # {'success': True, 'raw': 'Done'}

    time.sleep(.1)

    result_get = wrapper.run_cli_command(command="audio-input", subcommand="get")
    print(result_get)  # {'input_mode': 'analogue_xlr', 'raw': ...}

    time.sleep(.1)

    result_set = wrapper.run_cli_command(command="audio-input", subcommand="set", options={"--position": "aes3"})
    print(result_set)  # {'success': True, 'raw': 'Done'}

    time.sleep(.1)

    result_get = wrapper.run_cli_command(command="audio-input", subcommand="get")
    print(result_get)  # {'input_mode': 'aes3', 'raw': ...}

    time.sleep(.1)

    result_set = wrapper.run_cli_command(command="mode", subcommand="set", options={"--position": "internal-dsp"})
    print(result_set)  # {'success': True, 'raw': 'Done'}

    time.sleep(.1)

    result_get = wrapper.run_cli_command(command="mode", subcommand="get")
    print(result_get)  # {'mode': 'Normal', 'raw': ...}

    result_set = wrapper.run_cli_command(command="mode", subcommand="set", options={"--position": "backplate"})
    print(result_set)  # {'success': True, 'raw': 'Done'}

    time.sleep(.1)

    result_get = wrapper.run_cli_command(command="mode", subcommand="get")
    print(result_get)  # {'mode': 'Normal', 'raw': ...}


    

    
else:
    print("No devices discovered. Cannot proceed with gain calibration commands.")

