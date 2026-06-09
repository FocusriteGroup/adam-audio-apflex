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
        help="Set audio input (aes3, analogue-xlr)")
    set_audio_parser.add_argument("mode", type=str,
        help="Input mode (aes3, analogue-xlr)")
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
    parser_extract_csv = subparsers.add_parser(
        "extract_csv_columns",
        help="Extract selected CSV columns (from row 2 onward) into a new CSV file",
    )
    parser_extract_csv.add_argument("input_path", type=str, help="Path to the source CSV file")
    parser_extract_csv.add_argument(
        "columns",
        type=int,
        nargs="+",
        help="Zero-based column indices to extract (e.g. 0 1 2)",
    )
    parser_extract_csv.add_argument("output_filename", type=str, help="Output CSV filename")
    parser_extract_csv.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Output directory (defaults to input file directory)",
    )
    parser_extract_csv.add_argument("--server", action="store_true", help="Run extraction via ADAM service")
    parser_split_ap = subparsers.add_parser(
        "split_ap_distortion_csv",
        help="Split an AP Level & Distortion CSV into per-metric files (F, H2, H3, Total)",
    )
    parser_split_ap.add_argument("input_path", type=str, help="Path to the source AP measurement CSV file")
    parser_split_ap.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Output directory (defaults to input file directory)",
    )
    parser_split_ap.add_argument(
        "--fraction",
        type=int,
        default=None,
        dest="fraction",
        help="If set, apply 1/n-octave smoothing to each metric file (e.g. 3 = 1/3 octave)",
    )
    parser_split_ap.add_argument(
        "--output-prefix",
        dest="output_prefix",
        default=None,
        help="Base name for output files (default: input file stem)",
    )
    parser_split_ap.add_argument("--server", action="store_true", help="Run via ADAM service")
    parser_smooth = subparsers.add_parser(
        "octave_smooth_ap_csv",
        help="Apply 1/n-octave smoothing to all Y columns of an AP measurement CSV",
    )
    parser_smooth.add_argument("input_path", type=str, help="Path to the source AP CSV file")
    parser_smooth.add_argument(
        "--fraction",
        type=int,
        default=3,
        dest="fraction",
        help="Octave fraction denominator (e.g. 3 = 1/3 octave, default: 3)",
    )
    parser_smooth.add_argument(
        "--output-filename",
        dest="output_filename",
        default=None,
        help="Output filename (default: <stem>_smooth<fraction>.csv)",
    )
    parser_smooth.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Output directory (defaults to input file directory)",
    )
    parser_smooth.add_argument("--server", action="store_true", help="Run via ADAM service")
    parser_merge_ap = subparsers.add_parser(
        "merge_ap_distortion_csvs",
        help="Merge two or more AP Level & Distortion CSV files into per-metric combined files (F, H2, H3, Total)",
    )
    parser_merge_ap.add_argument(
        "input_paths",
        type=str,
        nargs="+",
        help="Two or more source AP measurement CSV file paths",
    )
    parser_merge_ap.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Output directory (defaults to directory of the first input file)",
    )
    parser_merge_ap.add_argument(
        "--fraction",
        type=int,
        default=None,
        dest="fraction",
        help="If set, apply 1/n-octave smoothing to each merged metric file (e.g. 3 = 1/3 octave)",
    )
    parser_merge_ap.add_argument(
        "--output-prefix",
        dest="output_prefix",
        default=None,
        help="Base name for output files (default: longest common prefix of input file stems)",
    )
    parser_merge_ap.add_argument("--server", action="store_true", help="Run via ADAM service")
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
        help="Upload measurement data to local matcher DB")
    upload_measurement_parser.add_argument("measurement_path", type=str,
        help="Path to measurement file")
    upload_measurement_parser.add_argument("--serial-number", "-s",
        dest="serial_number", required=True, help="Explicit device serial number")
    upload_measurement_parser.add_argument("--json-directory", type=str,
        default="measurements", help="Deprecated: JSON upload path is no longer used")
    upload_measurement_parser.add_argument("--server", action="store_true",
        help="Deprecated for upload_measurement: service mode is disabled")
    upload_measurement_parser.add_argument("--write-db", action="store_true",
        help="Optional compatibility flag; upload_measurement writes to DB by default")
    upload_measurement_parser.add_argument("--db-path", type=str,
        default="Matching_App/Data/db/matcher.db",
        help="Local matcher DB path used with --write-db (default: Matching_App/Data/db/matcher.db)")

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
        help="Bass management mode (stereo, wide, lfe)")
    set_bass_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_bass_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    get_bm_bypass_parser = subparsers.add_parser("get_bass_management_bypass",
        help="Get bass management bypass state from OCA device")
    get_bm_bypass_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_bm_bypass_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_bm_bypass_parser = subparsers.add_parser("set_bass_management_bypass",
        help="Set bass management bypass state on OCA device")
    set_bm_bypass_parser.add_argument("position", type=str,
        help="Bypass state (enabled, disabled)")
    set_bm_bypass_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_bm_bypass_parser.add_argument("port", type=int, nargs="?", default=None,
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

    # MAC address parsers (factory-settings EOL)
    get_mac_parser = subparsers.add_parser("get_mac_address",
        help="Get the MAC address from the OCA device")
    get_mac_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_mac_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_mac_parser = subparsers.add_parser("set_mac_address",
        help="Set the MAC address on the OCA device (format: XX:XX:XX:XX:XX:XX)")
    set_mac_parser.add_argument("value", type=str,
        help="MAC address in format XX:XX:XX:XX:XX:XX")
    set_mac_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_mac_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Serial number parsers (factory-settings EOL)
    get_serial_parser = subparsers.add_parser("get_serial_number",
        help="Get the serial number from the OCA device")
    get_serial_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_serial_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    set_serial_parser = subparsers.add_parser("set_serial_number",
        help="Set the serial number on the OCA device")
    set_serial_parser.add_argument("value", type=str,
        help="Serial number string")
    set_serial_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    set_serial_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Model description (read-only)
    get_model_parser = subparsers.add_parser("get_model_description",
        help="Get the model description from the OCA device")
    get_model_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    get_model_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    firmware_version_parser = subparsers.add_parser("get_firmware_version",
        help="Get the firmware version from the OCA device")
    firmware_version_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    firmware_version_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Add ASubs initialization parser
    init_parser = subparsers.add_parser("init_sub",
        help="Initialize ASubs with default settings (internal-dsp, gain 0, unmuted, phase 0, calibration 0, analogue-xlr input, wide bass management)")
    init_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    init_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional for device name)")

    # Add References setup parser
    setup_refs_parser = subparsers.add_parser("setup_references",
        help="Setup References directory by copying DefaultReferences if it doesn't exist")
    setup_refs_parser.add_argument("path", type=str,
        help="Target path where References directory should be created")
    setup_refs_parser.add_argument("--mono", action="store_true",
        help="Use mono references from DefaultReferences/Mono/ instead of stereo")

    # Golden Sample check
    golden_sample_parser = subparsers.add_parser("is_golden_sample",
        help="Check whether the scanned serial number matches the Golden Sample serial number")
    golden_sample_parser.add_argument("scanned_serial", type=str,
        help="Serial number scanned from the device under test")
    golden_sample_parser.add_argument("golden_sample_serial", type=str,
        help="Golden Sample serial number stored in the project parameters")
    golden_sample_parser.add_argument("measure_golden_sample", type=lambda x: x.lower() == "true",
        help="True if the Golden Sample should be measured, False if an EOL unit should be measured")

    default_serial_parser = subparsers.add_parser("is_default_serial",
        help="Check whether the scanned serial number matches the expected default serial number")
    default_serial_parser.add_argument("scanned_serial", type=str,
        help="Serial number scanned from the device under test")
    default_serial_parser.add_argument("default_serial", type=str,
        help="Default serial number stored in the project parameters")
    default_serial_parser.add_argument("measure_default", type=lambda x: x.lower() == "true",
        help="True if the default-serial unit should be measured, False if a production unit should be measured")

    # System build verification
    verify_system_parser = subparsers.add_parser("verify_system",
        help="Verify two modules form a matched pair and link them to a system serial number")
    verify_system_parser.add_argument("system_sn", type=str,
        help="System serial number")
    verify_system_parser.add_argument("module_sn_1", type=str,
        help="First module serial number")
    verify_system_parser.add_argument("module_sn_2", type=str,
        help="Second module serial number")
    verify_system_parser.add_argument("--db-path", type=str,
        default="Matching_App/Data/db/matcher.db",
        help="Local matcher DB path (default: Matching_App/Data/db/matcher.db)")

    # Compensate L/R imbalance using a diff CSV
    compensate_parser = subparsers.add_parser("compensate_lr_diff",
        help="Apply L/R compensation: L+=0.5*diff, R-=0.5*diff (stereo RMS CSV + mono diff CSV)")
    compensate_parser.add_argument("input_path", type=str,
        help="Path to the stereo RMS measurement CSV (AP format, 4 header rows, X,Y,X,Y)")
    compensate_parser.add_argument("diff_path", type=str,
        help="Path to the mono L-R diff CSV (AP format, 4 header rows, X,Y in dB)")
    compensate_parser.add_argument("output_path", type=str,
        help="Path where the compensated CSV is written")

    # Per-measurement compensated L-R difference (two inputs, two outputs)
    comp_pair_parser = subparsers.add_parser("extract_compensated_lr_diff_pair",
        help="Write a compensated L-R diff CSV for each of two stereo RMS measurements")
    comp_pair_parser.add_argument("diff_path", type=str,
        help="Path to the mono mic L-R diff CSV (AP format)")
    comp_pair_parser.add_argument("input1_path", type=str,
        help="Path to the first stereo RMS measurement CSV")
    comp_pair_parser.add_argument("output1_path", type=str,
        help="Output CSV path for the first measurement's compensated L-R diff")
    comp_pair_parser.add_argument("input2_path", type=str,
        help="Path to the second stereo RMS measurement CSV")
    comp_pair_parser.add_argument("output2_path", type=str,
        help="Output CSV path for the second measurement's compensated L-R diff")

    # Same as above but combined into a single stereo CSV
    comp_combined_parser = subparsers.add_parser("extract_compensated_lr_diff_combined",
        help="Write compensated L-R diff of two stereo RMS measurements into one stereo CSV")
    comp_combined_parser.add_argument("diff_path", type=str,
        help="Path to the mono mic L-R diff CSV (AP format)")
    comp_combined_parser.add_argument("input1_path", type=str,
        help="Path to the first stereo RMS measurement CSV")
    comp_combined_parser.add_argument("input2_path", type=str,
        help="Path to the second stereo RMS measurement CSV")
    comp_combined_parser.add_argument("output_path", type=str,
        help="Output CSV path (single stereo X,Y,X,Y file)")

    # Filter reference by limits
    filter_ref_parser = subparsers.add_parser("filter_reference_by_limits",
        help="Filter a reference measurement CSV to include only frequencies within limits ranges")
    filter_ref_parser.add_argument("reference_path", type=str,
        help="Path to the reference measurement CSV file (can be stereo or mono)")
    filter_ref_parser.add_argument("limits_path", type=str,
        help="Path to the limits CSV file (always mono)")
    filter_ref_parser.add_argument("--output-filename", type=str, default=None,
        help="Output filename (defaults to <reference_name>_filtered.csv)")
    filter_ref_parser.add_argument("--output-dir", type=str, default=None,
        help="Output directory (defaults to reference file directory)")

    # ---------------------------------------------------------------------------
    # MAC provisioning
    # ---------------------------------------------------------------------------

    provision_mac_parser = subparsers.add_parser("provision_mac",
        help="Assign a unique MAC address to a device that has passed EOL testing")
    provision_mac_parser.add_argument("target", type=str,
        help="OCA device name or IP address")
    provision_mac_parser.add_argument("serial", type=str,
        help="Device serial number (already validated by the AP sequence)")
    provision_mac_parser.add_argument("default_mac", type=str,
        help="Factory default MAC address, e.g. 02:00:00:00:00:00")
    provision_mac_parser.add_argument("port", type=int, nargs="?", default=None,
        help="OCA device port (optional)")
    provision_mac_parser.add_argument("--arp-delay", dest="arp_delay", type=float, default=None,
        help="Override ARP flush delay in seconds (default: 3.0). Use 0 to stress-test OCA read-back.")

    init_mac_db_parser = subparsers.add_parser("init_mac_db",
        help="Initialise the MAC address provisioning database (run once during setup)")

    set_mac_range_parser = subparsers.add_parser("set_mac_range",
        help="Configure the MAC address pool range for provisioning")
    set_mac_range_parser.add_argument("start_mac", type=str,
        help="First MAC address in the range, e.g. 02:AB:CD:00:00:00")
    set_mac_range_parser.add_argument("end_mac", type=str,
        help="Last MAC address in the range (inclusive)")
    set_mac_range_parser.add_argument("--warn-threshold", dest="warn_threshold", type=int, default=20,
        help="Warn when remaining MACs drop to this value (default: 20)")

    get_mac_pool_status_parser = subparsers.add_parser("get_mac_pool_status",
        help="Show current MAC pool status (total / assigned / remaining)")

    export_mac_log_parser = subparsers.add_parser("export_mac_log",
        help="Export MAC provisioning log (SN <-> MAC assignments) to a CSV file")
    export_mac_log_parser.add_argument("output_path", type=str,
        help="Path for the output CSV file")
    export_mac_log_parser.add_argument("--status", type=str, default=None,
        choices=["reserved", "written", "verified", "rolled_back"],
        help="Filter by provisioning status (default: all entries)")
    export_mac_log_parser.add_argument("--serial", type=str, default=None,
        help="Filter to a single serial number")

    register_gs_parser = subparsers.add_parser("register_golden_sample",
        help="Register a serial number as a golden sample (prevents re-provisioning)")
    register_gs_parser.add_argument("serial", type=str,
        help="Serial number to register as golden sample")
    register_gs_parser.add_argument("--note", type=str, default=None,
        help="Optional note describing the unit (e.g. its purpose)")

    return parser
