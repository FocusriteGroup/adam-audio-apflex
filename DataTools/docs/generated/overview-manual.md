# DataTools Overview

DataTools is a production-support desktop application for data handling. It is used to process and analyse measurement data produced by the APx500 Flex Production Tool, and consolidates measurement analysis, module matching, device provisioning, and configuration into a single interface.

## Home Screen

![DataTools Home Screen](../screenshots/overview/01_home.png)

The home screen shows four feature tiles. Click a tile to open the corresponding viewer.

## Features

### Matching Viewer

Inspects driver-module matching data from the production database. Module pairs are matched algorithmically by frequency-response similarity so that left and right drivers in a stereo headphone are acoustically consistent.

Key tasks:

- Browse Pool, Matched, Paired, and Assembled states
- Look up any module serial and view its measurement curve
- Overlay many curves in a single chart for batch inspection
- Filter all lists by date range
- Export a read-only CSV snapshot

→ See [Matching Viewer Manual](matching-viewer-manual.md) for detailed workflows.

### Tristar Databases Viewer

Provides a unified read-only view of Serial Number / Firmware (SN/FW) test records and MAC address provisioning status for Tristar production units. It also handles automated MAC address assignment for spare backplate units.

Key tasks:

- Browse all produced units with their test result, firmware, and parts
- Filter by date range or look up a specific serial number
- Check MAC provisioning status per unit
- Provision spare backplate units with a new MAC address via OCA
- Export unit and parts data to CSV

→ See [Tristar Databases Manual](tristar-viewer-manual.md) for detailed workflows.

### Measurements Viewer

Loads Audio Precision APx CSV measurement files, visualises frequency-response charts, and generates reference curves and statistical limit files used by production test programs.

Key tasks:

- Select one or more result folders from the measurements root
- Plot RMS Level, Phase, THD, Rub-and-Buzz, and L-R Compensation curves
- Switch between Raw, Median, and Normalised display modes
- Toggle individual sub-channels (Left / Right / Mono) on and off
- Run analysis to compute median reference curves and ±σ limits
- Export Reference CSV, Limit CSV, PNG chart, and a README summary

→ See [Measurements Viewer Manual](measurements-viewer-manual.md) for detailed workflows.

### Settings

Password-protected configuration panel for all DataTools path and provisioning settings. All values are persisted in a local SQLite store.

Configurable items:

| Setting | Description |
| --- | --- |
| Measurements Root Folder | Root folder containing Measurements/ and References/ sub-folders |
| Matching DB path | SQLite database used by the Matching Viewer |
| SN FW Workstation DB path | SQLite database used by the SN/FW workstation |
| MAC addresses DB path | SQLite database used by the MAC provisioning system |
| Backplate Default Serial | Placeholder serial for unprovisioned backplate units |
| Backplate Default MAC | Placeholder MAC address for unprovisioned backplate units |
| Settings password | Password required to open the Settings panel |

→ See [Settings Manual](settings-menu-manual.md) for detailed workflows.

## Data Folder Layout

All measurement data is organised under a single **Measurements Root Folder** configured in Settings. The structure mirrors the product hierarchy used at the production sites.

```
<Measurements Root>/
├── Measurements/          # Raw APx CSV exports from production
│   ├── EOL/               # End-of-line test results
│   │   └── <Year>/
│   │       └── <Month_Day>/   # One folder per production day
│   └── GoldenSample/      # Reference golden-sample measurements
└── References/            # Generated reference and limit CSVs (mirrors Measurements/)
    ├── EOL/
    │   └── <Year>/
    │       └── <Month_Day>/
    └── GoldenSample/
```

## Quick Start

### First-time setup

1. Click **Settings** and enter the password.
2. Set the **Measurements Root Folder** to your product's data root.
3. Set the **Matching DB path** if you use the Matching Viewer.
4. Set the **SN FW Workstation DB path** and **MAC addresses DB path** if you use Tristar Databases.
5. Click **Apply** and close Settings.

### Inspecting a daily production batch

1. Open **Measurements Viewer**.
2. Click **Select Measurements**, choose **EOL**, and select today's folder.
3. Review the **RMS Level** chart for outliers.
4. If the batch looks representative, run **Analyze** to update the Reference and Limit files.

### Checking module matching status

1. Open **Matching Viewer**.
2. Use **Matched** mode to see all suggested pairs awaiting operator confirmation.
3. Use the serial input to look up a specific module if needed.
