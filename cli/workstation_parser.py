"""
workstation_parser.py

CLI parser setup for ADAM Audio Production Workstation.
"""

import argparse


def build_workstation_parser():
    parser = argparse.ArgumentParser(
        description="ADAM Audio Production Workstation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Globale Parameter
    parser.add_argument("--host", "--service-host", dest="service_host",
                       help="ADAM service IP address (auto-discovered if not specified)")
    parser.add_argument("--service-port", dest="service_port", type=int, default=65432,
                       help="ADAM service port (default: 65432)")
    parser.add_argument("--service-name", default="ADAMService",
                       help="Name of ADAM service to connect to (default: ADAMService)")
    parser.add_argument("--scanner-type", choices=["honeywell"], default="honeywell",
                       help="Type of scanner to use (default: honeywell)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # OCA-Kommandos (nur die, die in OCADevice existieren)
    discover_parser = subparsers.add_parser("discover", help="Discover OCA devices")
    discover_parser.add_argument("--timeout", type=int, default=1, help="Discovery timeout in seconds")

    get_gain_parser = subparsers.add_parser("get_gain_calibration", help="Get gain calibration from OCA device")
    get_gain_parser.add_argument("target", type=str, help="OCA device name or IP address")
    get_gain_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

    set_gain_parser = subparsers.add_parser("set_gain_calibration", help="Set gain calibration on OCA device")
    set_gain_parser.add_argument("value", type=float, help="Gain calibration value")
    set_gain_parser.add_argument("target", type=str, help="OCA device name or IP address")
    set_gain_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

    get_mode_parser = subparsers.add_parser("get_mode", help="Get mode from OCA device")
    get_mode_parser.add_argument("target", type=str, help="OCA device name or IP address")
    get_mode_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

    set_mode_parser = subparsers.add_parser("set_mode", help="Set mode on OCA device")
    set_mode_parser.add_argument("position", type=str, help="Mode to set (e.g. 'internal-dsp', 'backplate')")
    set_mode_parser.add_argument("target", type=str, help="OCA device name or IP address")
    set_mode_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

    get_audio_input_parser = subparsers.add_parser("get_audio_input", help="Get audio input mode from OCA device")
    get_audio_input_parser.add_argument("target", type=str, help="OCA device name or IP address")
    get_audio_input_parser.add_argument("port", type=int, nargs="?", default=None, help="OCA device port (optional for device name)")

    set_audio_parser = subparsers.add_parser("set_audio_input",
        help="Set audio input (aes3, analogue-xlr, analogue-rca)")
    set_audio_parser.add_argument("mode", type=str,
        help="Input mode (aes3, analogue-xlr, analogue-rca)")
    set_audio_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_audio_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Produktions-/Hardware-/Service-Kommandos (NICHT entfernen!)
    parser_timestamp_ext = subparsers.add_parser("generate_timestamp_extension", help="Generate a timestamp extension.")
    parser_timestamp_ext.add_argument("--server", action="store_true", help="Use service for timestamp generation")
    parser_construct_path = subparsers.add_parser("construct_path", help="Construct a path.")
    parser_construct_path.add_argument("paths", type=str, nargs="+", help="List of paths to join.")
    parser_construct_path.add_argument("--server", action="store_true", help="Use service for path construction")
    parser_timestamp_subpath = subparsers.add_parser("get_timestamp_subpath", help="Get a timestamp subpath.")
    parser_timestamp_subpath.add_argument("--server", action="store_true", help="Use service for timestamp generation")
    parser_generate_file_prefix = subparsers.add_parser("generate_file_prefix", help="Generate a file prefix.")
    parser_generate_file_prefix.add_argument("strings", type=str, nargs="+", help="List of strings to combine.")
    parser_generate_file_prefix.add_argument("--server", action="store_true", help="Use service for prefix generation")
    parser_set_channel = subparsers.add_parser("set_channel", help="Set the channel (1 or 2).")
    parser_set_channel.add_argument("channel", type=int, choices=[1, 2], help="Channel to set (1 or 2).")
    subparsers.add_parser("open_box", help="Open the box.")
    subparsers.add_parser("scan_serial", help="Scan the serial number.")
    biquad_parser = subparsers.add_parser("get_biquad_coefficients", help="Get biquad filter coefficients")
    biquad_parser.add_argument("filter_type", choices=["bell", "high_shelf", "low_shelf"], help="Type of biquad filter")
    biquad_parser.add_argument("gain", type=float, help="Gain in dB")
    biquad_parser.add_argument("peak_freq", type=float, help="Peak frequency in Hz")
    biquad_parser.add_argument("Q", type=float, help="Quality factor")
    biquad_parser.add_argument("sample_rate", type=int, help="Sample rate in Hz")
    set_biquad_parser = subparsers.add_parser("set_device_biquad", help="Set biquad filter on OCA device")
    set_biquad_parser.add_argument("index", type=int, help="Biquad index")
    set_biquad_parser.add_argument("coefficients", type=str, help="Koeffizienten-Liste als JSON-String")
    set_biquad_parser.add_argument("target", type=str, help="OCA device name or IP address")
    set_biquad_parser.add_argument("port", type=int, help="OCA device port")
    get_device_biquad_parser = subparsers.add_parser("get_device_biquad", help="Get biquad coefficients from OCA device")
    get_device_biquad_parser.add_argument("index", type=int, help="Biquad index")
    get_device_biquad_parser.add_argument("target", type=str, help="OCA device name or IP address")
    get_device_biquad_parser.add_argument("port", type=int, help="OCA device port")
    check_trials_parser = subparsers.add_parser("check_measurement_trials", help="Check allowed measurement trials for a serial number")
    check_trials_parser.add_argument("serial_number", type=str, help="Serial number to check")
    check_trials_parser.add_argument("csv_path", type=str, help="Path to the CSV file")
    check_trials_parser.add_argument("max_trials", type=int, help="Maximum allowed trials")
    upload_measurement_parser = subparsers.add_parser("upload_measurement",
        help="Upload measurement data to service")
    upload_measurement_parser.add_argument("measurement_path", type=str,
        help="Path to measurement file")
    upload_measurement_parser.add_argument("--serial-number", "-s",
        dest="serial_number", required=True, help="Explicit device serial number")
    upload_measurement_parser.add_argument("--json-directory", type=str,
        default="measurements", help="JSON directory on service")

    # NEU: Parser für Gain Calibration
    calibrate_parser = subparsers.add_parser("calibrate_gain",
        help="Calculate gain difference between input and target measurements at specific frequencies")
    calibrate_parser.add_argument("input_file", type=str,
        help="Path to input measurement CSV file")
    calibrate_parser.add_argument("target_file", type=str,
        help="Path to target measurement CSV file")
    calibrate_parser.add_argument("--frequencies", "-f", type=float, nargs="+", required=True,
        help="List of frequencies (in Hz) to calculate calibration factors for")

    # NEU: Parser für Bass Management
    get_bass_parser = subparsers.add_parser("get_bass_management",
        help="Get bass management mode from OCA device")
    get_bass_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_bass_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_bass_parser = subparsers.add_parser("set_bass_management",
        help="Set bass management mode on OCA device")
    set_bass_parser.add_argument("position", type=str,
        help="Bass management mode (e.g. 'stereo-bass', 'stereo', 'wide', 'lfe')")
    set_bass_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_bass_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # NEU: Parser für Subwoofer Gain
    get_gain_parser = subparsers.add_parser("get_gain",
        help="Get subwoofer gain level (-24 to 0 dB)")
    get_gain_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_gain_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_gain_parser = subparsers.add_parser("set_gain",
        help="Set subwoofer gain level (-24 to 0 dB)")
    set_gain_parser.add_argument("value", type=float,
        help="Gain value in dB (-24 to 0)")
    set_gain_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_gain_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Phase delay parsers
    get_phase_parser = subparsers.add_parser("get_phase_delay",
        help="Get phase delay setting (0-315 degrees)")
    get_phase_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_phase_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_phase_parser = subparsers.add_parser("set_phase_delay",
        help="Set phase delay (deg0, deg45, deg90, deg135, deg180, deg225, deg270, deg315)")
    set_phase_parser.add_argument("position", type=str,
        help="Phase delay setting (deg0, deg45, etc.)")
    set_phase_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_phase_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Mute parsers
    get_mute_parser = subparsers.add_parser("get_mute",
        help="Get mute state")
    get_mute_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_mute_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_mute_parser = subparsers.add_parser("set_mute",
        help="Set mute state (normal, mute)")
    set_mute_parser.add_argument("position", type=str,
        help="Mute state (normal, mute)")
    set_mute_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_mute_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Add ASubs initialization parser
    init_parser = subparsers.add_parser("init_asub",
        help="Initialize ASubs with default settings (internal-dsp, gain 0, unmuted, phase 0, calibration 0)")
    init_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    init_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Add References setup parser
    setup_refs_parser = subparsers.add_parser("setup_references",
        help="Setup References directory by copying DefaultReferences if it doesn't exist")
    setup_refs_parser.add_argument("path", type=str,
        help="Target path where References directory should be created")

    return parser
