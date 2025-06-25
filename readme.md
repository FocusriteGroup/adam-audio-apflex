# adam-audio-apflex

This repository provides a client-server architecture for integrating Audio Precision (APx500) measurements with production test automation. It includes command-line tools and utility classes to communicate with external hardware such as serial-connected switch boxes, barcode scanners, and OCA-compatible audio devices. The system is designed to be used as part of a sequence-based test framework.

---

## Overview

The core components of this project are:

* **`ap_server.py`**
  TCP server that listens for commands and interacts with:

  * Serial-connected devices (SwitchBox, HoneywellScanner)
  * OCA devices via the `oca_tools` interface

* **`ap_client.py`**
  Command-line client that parses subcommands and arguments, packages them into JSON, and sends them to the server via TCP. It supports response handling and logging.

* **`ap_utils.py`**
  Contains:

  * `Utilities`: Functions for generating file paths, prefixes, and timestamps
  * `HoneywellScanner`: A serial-based barcode scanner class
  * `SwitchBox`: A serial-controlled channel and relay switch

* **`check_server.py`**
  Utility script to check if the server is running and start it if necessary. Used for robust startup routines.

---

## Usage

### 1. Start the server

Start the TCP server manually or automatically:

```bash
python ap_server.py
```

or:

```bash
python start_server_helper.py
```

### 2. Execute commands via the client

The client script provides a CLI for every supported command. The interface is self-documented through argparse.

```bash
python ap_client.py <command> [args...]
```

#### Example: Set the active channel on the SwitchBox

```bash
python ap_client.py set_channel 2
```

#### Example: Request the gain of an OCA device

```bash
python ap_client.py get_gain 192.168.1.100 65000
```

#### Example: Scan a serial number

```bash
python ap_client.py scan_serial
```

#### Example: Set a biquad filter on an OCA device

```bash
python ap_client.py set_device_biquad 0 '[1, 2, 3, 4, 5]' 192.168.1.100 65000
```

Run `python ap_client.py -h` to list all available commands.

---

## Detailed Feature Description

### SwitchBox Control

* `set_channel <1|2>`: Selects the active audio routing channel.
* `open_box`: Opens a test enclosure using the relay control.

### Honeywell Scanner Integration

* `scan_serial`: Triggers a scan and reads the serial number via serial port.

### OCA Device Control

* `get_serial_number`, `get_model_description`, `get_firmware_version`: Query device information.
* `get_gain`, `set_gain`: Read and write analog gain levels.
* `get_audio_input`, `set_audio_input`: Change audio input routing (e.g., AES3, analog).
* `get_mute`, `set_mute`: Toggle mute state.
* `get_mode`, `set_mode`: Adjust operating mode.
* `get_phase_delay`, `set_phase_delay`: Adjust phase alignment.
* `get_device_biquad`, `set_device_biquad`: Query and apply IIR filter coefficients.

### Measurement Gating

* `check_measurement_trials`: Checks a CSV-based record of test attempts by serial number and blocks tests that exceed the allowed number.

---

## Dependencies

* Python 3.8+
* `pyserial`
* `oca_tools` (provides `OCP1ToolWrapper`)
* `biquad_tools` (provides `Biquad_Filter`)

---

## Logging

Log files are automatically created per day:

* `logs/server/` — Server activity, device events, command handling
* `logs/client/` — Client-side command execution and connection logs

---

## License

This project is maintained internally by Focusrite Group. License terms are defined in the repository.

---

## Disclaimer

This repository interacts with physical hardware and network devices. Ensure proper safety and test procedures are followed when deploying in production environments.
