# SubPro MAC Provisioning Database - Introduction

This section documents the production MAC address provisioning system used during SubPro EOL workflows.

The MAC provisioning stack ensures that each tested unit receives a unique MAC address, that write/verify steps are auditable, and that APx500 can make reliable pass/fail decisions from stdout.

## What This System Does

- Manages an allowed MAC address pool with a forward-only pointer.
- Reserves, writes, and verifies MAC addresses against the physical DUT.
- Stores a full audit trail for each provisioning attempt.
- Supports both first-test and re-test behavior.
- Exposes a workstation CLI contract designed for APx shell-step integration.

## Why The Database Is Critical

The SQLite database is the source of truth for provisioning state. It prevents duplicate assignment, tracks status transitions, and preserves evidence of what happened at each station and time.

Without this state tracking, production would risk MAC collisions, ambiguous re-test behavior, and weak traceability for quality or support investigations.

## Production Context

Typical trigger point in production:

1. Device passes APx EOL checks.
2. APx calls `adam_workstation.py provision_mac <target> <serial> <default_mac>`.
3. Workstation logic uses OCA + database operations to complete provisioning.
4. APx evaluates stdout (`successful` or `Error: ...`).

## Core Data Model At A Glance

The database contains three core tables:

- `mac_range`: configured range plus next free MAC pointer.
- `provisioning_log`: lifecycle/audit rows per serial + MAC assignment.
- `golden_samples`: protected serials that must not be re-provisioned.

## Status Lifecycle

`reserved -> written -> verified`

Failure path:

`reserved` or `written -> rolled_back`

Important rule: MAC allocation is forward-only. Rolled-back MACs are not returned to the pool.

## Operational Guarantees

- One serial gets one tracked provisioning lifecycle.
- Pool exhaustion is detected and reported explicitly.
- Verification failure produces a controlled error result.
- APx-facing stdout remains stable for automation.

## Backup Strategy (Two Layers)

The production setup uses two complementary backup mechanisms.

1. Cloud-synced workstation storage:
- If the database file is stored inside a cloud-synced folder (for example OneDrive), changes are synchronized automatically when internet is available.
- This provides continuous off-machine backup for normal operation.
- During internet outages, data continues to be written locally and sync resumes when connectivity returns.

2. External-drive snapshots:
- After each verified provisioning event, the workstation attempts a best-effort copy to connected removable/USB drives.
- This creates an offline recovery path independent of internet availability and cloud account state.
- The external-drive backup set includes a rolling latest copy plus timestamped archive snapshots.

Together, these layers provide both convenience (cloud sync) and resilience (offline removable media).

## Document Guide

Use these pages for full detail:

- Workflow: [mac_provisioning_workflow.md](mac_provisioning_workflow.md)
- Database schema and behavior: [mac_provisioning_database.md](mac_provisioning_database.md)
- Implementation details: [mac_provisioning_code.md](mac_provisioning_code.md)
- Test coverage and stress validation: [mac_provisioning_tests.md](mac_provisioning_tests.md)

## Intended Audience

- Production engineers and test developers integrating APx flows.
- Software developers extending workstation provisioning logic.
- Quality and operations teams auditing provisioning behavior.
