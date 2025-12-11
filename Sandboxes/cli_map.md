# CLI Map: `aes70-cli.exe`

## (root)

**Options:**
- `-v, --version` — ,  Print version information
- `-h, --help` — ,     Print help

**Commands:**
- `audio-input` — Get, set or monitor the audio input mode of an A-Series device
- `bass-management` — Get, set or monitor the bass management mode of an A-Series subwoofer
- `delay` — Get, set or monitor the delay of an A-Series speaker
- `discover` — Discover and list compatible A-Series devices
- `factory-filters` — Get, set or monitor the coefficients of factory filters of an A-Series device
- `firmware` — Get the firmware version or update the firmware of an A-Series device
- `gain` — Get, set or monitor the gain of an A-Series device
- `identify` — Identify an A-Series device
- `mode` — Get, set or monitor the mode of an A-Series device
- `model-description` — Get the model description of an A-Series device
- `mute` — Get, set or monitor the mute state of an A-Series device
- `phase-delay` — Get, set or monitor the phase delay of an A-Series subwoofer
- `reboot` — Reboot an A-Series device
- `serial-number` — Get or set the serial number of an A-Series device
- `user-filters` — Get, set or monitor the coefficients of user filters of an A-Series device
- `gain-calibration` — Get, set or monitor the gain calibration of an A-Subs devices
- `factory-settings` — Factory settings commands for A-Subs devices
### audio-input

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current audio input mode
- `set` — Set the audio input mode [aes3 | analogue_xlr | analogue_rca]
- `monitor` — Monitor audio input mode changes
#### audio-input get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### audio-input set

**Options:**
- `--position` — <POSITION>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### audio-input monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### bass-management

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current bass management state
- `set` — Set the bass management state [stereo-bass | stereo | wide | lfe]
- `monitor` — Monitor bass management state changes
#### bass-management get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### bass-management set

**Options:**
- `--position` — <POSITION>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### bass-management monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### delay

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current delay in milliseconds
- `set` — Set the delay in milliseconds [0.0 to 10.0]
- `monitor` — Monitor delay changes
#### delay get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### delay set

**Options:**
- `--value` — <VALUE>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### delay monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### discover

**Options:**
- `--timeout` — <TIMEOUT>  The command timeout in seconds [default: 60]
- `-h, --help` — ,               Print help
### factory-filters

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get-meta-coefficients` — Get meta coefficients of a respective filter in the signal chain
- `set-meta-coefficients` — Set meta coefficients of a respective filter in the signal chain
- `get-normalized-coefficients` — Get normalized coefficients of a respective filter in the signal chain
- `set-normalized-coefficients` — Set normalized coefficients of a respective filter in the signal chain
- `monitor-coefficients` — Monitor the filter coefficients of filters in the signal chain
#### factory-filters get-meta-coefficients

**Options:**
- `--index` — <INDEX>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-filters set-meta-coefficients

**Options:**
- `--index` — <INDEX>
- `--filter-type` — <FILTER_TYPE>
- `--frequency` — <FREQUENCY>
- `--q` — <Q>
- `--gain` — <GAIN>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-filters get-normalized-coefficients

**Options:**
- `--index` — <INDEX>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-filters set-normalized-coefficients

**Options:**
- `--index` — <INDEX>
- `--coefficients` — <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-filters monitor-coefficients

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### firmware

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get-version` — Get the current firmware version
- `update` — Update firmware
#### firmware get-version

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### firmware update

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `--directory` — <DIRECTORY>
- `-h, --help` — ,
### gain

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current gain level in dB
- `set` — Set the gain level in dB speaker: [-60.0 .. 12.0], subwoofer: [-30.0 .. 0.0]
- `monitor` — Monitor gain level changes
#### gain get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### gain set

**Options:**
- `--value` — <VALUE>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### gain monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### identify

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### mode

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current mode
- `set` — Set the mode [internal_dsp | backplate]
- `monitor` — Monitor mode changes
#### mode get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### mode set

**Options:**
- `--position` — <POSITION>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### mode monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### model-description

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current model description
#### model-description get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### mute

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current mute state
- `set` — Set the mute state [normal | mute]
- `monitor` — Monitor mute state changes
#### mute get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### mute set

**Options:**
- `--position` — <POSITION>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### mute monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### phase-delay

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current phase delay
- `set` — Set the phase delay [deg0, deg45, deg90, deg135, deg180, deg225, deg270, deg315]
- `monitor` — Monitor phase delay changes
#### phase-delay get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### phase-delay set

**Options:**
- `--position` — <POSITION>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### phase-delay monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### reboot

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `--delay-ms` — <DELAY_MS>
- `-h, --help` — ,
### serial-number

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current serial number
#### serial-number get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### user-filters

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get-meta-coefficients` — Get meta coefficients of a respective filter in the signal chain
- `set-meta-coefficients` — Set meta coefficients of a respective filter in the signal chain
- `get-normalized-coefficients` — Get normalized coefficients of a respective filter in the signal chain
- `set-normalized-coefficients` — Set normalized coefficients of a respective filter in the signal chain
- `monitor-coefficients` — Monitor the filter coefficients of filters in the signal chain
#### user-filters get-meta-coefficients

**Options:**
- `--index` — <INDEX>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### user-filters set-meta-coefficients

**Options:**
- `--index` — <INDEX>
- `--filter-type` — <FILTER_TYPE>
- `--frequency` — <FREQUENCY>
- `--q` — <Q>
- `--gain` — <GAIN>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### user-filters get-normalized-coefficients

**Options:**
- `--index` — <INDEX>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### user-filters set-normalized-coefficients

**Options:**
- `--index` — <INDEX>
- `--coefficients` — <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS> <COEFFICIENTS>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### user-filters monitor-coefficients

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### gain-calibration

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get` — Get the current gain calibration in dB
- `set` — Set the gain calibration in dB : [-2.0 .. 2.0]
- `restore-factory` — Restore gain calibration to factory defaults
- `monitor` — Monitor gain calibration changes
#### gain-calibration get

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### gain-calibration set

**Options:**
- `--value` — <VALUE>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### gain-calibration restore-factory

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### gain-calibration monitor

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
### factory-settings

**Options:**
- `-h, --help` — ,  Print help

**Commands:**
- `get-serial-number` — Get the serial number
- `set-serial-number` — Set the serial number
- `monitor-serial-number` — Monitor serial number changes
- `get-mac-address` — Get the MAC address
- `set-mac-address` — Set the MAC address with format "XX:XX:XX:XX:XX:XX"
- `monitor-mac-address` — Monitor MAC address changes
- `lock` — Lock factory settings
- `unlock` — Unlock factory settings
#### factory-settings get-serial-number

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings set-serial-number

**Options:**
- `--value` — <VALUE>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings monitor-serial-number

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings get-mac-address

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings set-mac-address

**Options:**
- `--value` — <VALUE>
#### factory-settings monitor-mac-address

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings lock

**Options:**
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,
#### factory-settings unlock

**Options:**
- `--value` — <VALUE>
- `--target` — <TARGET>
- `--discovery-timeout` — <DISCOVERY_TIMEOUT>
- `--target-ip` — <TARGET_IP>
- `--port` — <PORT>
- `--protocol` — <PROTOCOL>
- `--timeout` — <TIMEOUT>
- `-h, --help` — ,