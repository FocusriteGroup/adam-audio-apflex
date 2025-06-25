# adam-audio-apflex

This repository provides a client-server architecture for automating hardware control tasks in a production test environment. It includes command-line tools and utility classes to communicate with serial-connected devices (e.g., SwitchBox, barcode scanners) and remote audio devices via the Open Control Architecture (OCA) protocol. The framework is designed for integration into Audio Precision-based or custom test sequences.

---

## Overview

The core components of this project are:

* **`ap_server.py`**
  A TCP server that listens for JSON-encoded commands and executes them using attached hardware. It manages:

  * Serial-connected SwitchBox for audio routing and relay control
  * Serial barcode scanners for device identification
  * OCA-compatible devices (e.g., amplifiers or DSP units) via the `oca_tools` wrapper

* **`ap_client.py`**
  A flexible command-line client used to send control commands to the server. Each command corresponds to a specific test action or hardware configuration step. Arguments are parsed using `argparse` and sent to the server over TCP. Responses can be printed or processed by calling tools.

* **`ap_utils.py`**
  Core utility module that includes:

  * `Utilities`: Functions for timestamping, file path construction, and file naming conventions
  * `HoneywellScanner`: A USB serial barcode scanner integration (based on Honeywell protocol)
  * `SwitchBox`: Serial-controlled relay module with support for dynamic channel switching and open/close states

* **`check_server.py`**
  Helper script to ensure the server is running before executing test steps. If the server is not active, it launches it in the background and waits until it is ready to accept connections.

---

## Usage

### 1. Start the server

Manually or via helper script:

```bash
python ap_server.py
```

or:

```bash
python check_server.py
```

### 2. Execute commands via the client

The client supports subcommands for every available function. Run with the required arguments:

```bash
python ap_client.py <command> [args...]
```

#### Example: Set the active channel on the SwitchBox

```bash
python ap_client.py set_channel 2
```

#### Example: Query gain of an OCA device

```bash
python ap_client.py get_gain 192.168.1.100 65000
```

#### Example: Scan a barcode and retrieve serial number

```bash
python ap_client.py scan_serial
```

#### Example: Set biquad filter coefficients on an OCA device

```bash
python ap_client.py set_device_biquad 0 '[1, 2, 3, 4, 5]' 192.168.1.100 65000
```

List available commands:

```bash
python ap_client.py -h
```

---

## Detailed Feature Description

### SwitchBox Control

* `set_channel <1|2>`: Switches the relay to the designated channel.
* `open_box`: Opens the relay enclosure, useful for physical access or ventilation.

The `SwitchBox` class automatically connects to the correct USB serial device using vendor and product ID. It manages asynchronous communication and ensures that the status of the box (open/closed) and the current channel is reliably updated.

### Honeywell Scanner Integration

* `scan_serial`: Sends a trigger command to the barcode scanner and listens for the serial response.

The scanner operates via serial-over-USB. It identifies devices by scanning barcodes, which are used for logging or measurement gating.

### OCA Device Control

* `get_serial_number`, `get_model_description`, `get_firmware_version`: Basic identification commands
* `get_gain`, `set_gain`: Read and configure analog gain values
* `get_audio_input`, `set_audio_input`: Change between input sources such as AES3, analog, etc.
* `get_mute`, `set_mute`: Toggle muting state
* `get_mode`, `set_mode`: Switch between device operating modes
* `get_phase_delay`, `set_phase_delay`: Control signal alignment delay
* `get_device_biquad`, `set_device_biquad`: Read or apply biquad IIR filters used in audio tuning

All OCA commands are wrapped using the `OCP1ToolWrapper` class (provided by the external `oca_tools` library). This wrapper handles binary packet formatting and parsing.

### Measurement Gating

* `check_measurement_trials`: Validates how often a device with a specific serial number has been tested.

  * Uses a CSV file to track previous test attempts
  * Blocks devices that exceed a defined maximum number of test trials

This is used to enforce measurement policies (e.g., maximum number of production test attempts).

---

## Dependencies

* Python 3.8 or newer
* `pyserial`: For USB-to-serial communication
* `oca_tools`: Custom package providing the `OCP1ToolWrapper`
* `biquad_tools`: Custom module for generating biquad filter coefficients

---

## Logging

Log files are stored daily under:

* `logs/server/` — Contains command history, device connection events, and errors from the server
* `logs/client/` — Tracks command dispatching, connection attempts, and command-line usage

---

## License

This project is maintained internally by Focusrite Group. License terms are defined in the repository.

---

## Disclaimer

This system interacts with physical hardware, including relays and live audio signals. Only qualified personnel should use it in production environments. Proper safety and validation measures must be followed.
