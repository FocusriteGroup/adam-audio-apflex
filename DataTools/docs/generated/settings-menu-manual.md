# DataTools Settings Menu

This guide provides comprehensive documentation for the DataTools Settings menu.
It covers configuration tasks, user workflows, troubleshooting, and UI features.

## Purpose and Scope

This manual documents all configuration options accessible through the Settings menu:

- Password-protected access control
- CSV delimiter and decimal separator configuration
- Export folder and database path management
- Settings password change and security

## Prerequisites

Before using the Settings menu, ensure the following:

- DataTools is running and the home screen is visible.
- You know the current settings password.
- All required target folders and database files exist on your system.

## Quick Start

1. Select the Settings tile on the home screen.
2. Enter the correct password and click Unlock.
3. Modify settings using the Edit or Browse buttons.
4. Click Apply to save your changes.
5. Click Close to exit the Settings menu.

## Home Screen

![Home Screen](../screenshots/settings-menu/01_home.png)

The home screen displays feature tiles for different DataTools functions.
Click the Settings tile to access the configuration area.

## Accessing the Settings Menu

![Enter Password Dialog](../screenshots/settings-menu/02_enter_password_dialog.png)

The Settings menu requires authentication for security.
Enter your password and click Unlock to proceed.

## Field Reference

| Field | Purpose | Edit Method |
| --- | --- | --- |
| Last used input folder | Most recent input folder for file operations | Read-only |
| CSV delimiter | Character separating CSV fields | Edit |
| Decimal separator | Decimal format (internally enforced to period) | Edit |
| Default export folder | Default destination for exports | Browse |
| Matching DB path | Path to Matching database | Browse |
| SN FW Workstation DB path | Path to SN/FW Workstation database | Browse |
| MAC addresses DB path | Path to MAC addresses database | Browse |
| DataTools DB path | Internal application configuration database | Read-only |
| Settings password | Password for Settings menu access | Change |

## The Settings Panel

![Settings Panel](../screenshots/settings-menu/03_settings_popup.png)

The Settings panel displays all configuration parameters.
Each field shows its current value and an action button:
- **Edit**: Modify text values via a large-text input dialog
- **Browse**: Select file or folder paths using native file dialogs
- **Change**: Modify the Settings password securely
- **View**: Display read-only field values

## Detailed Workflows

### Editing Text Values

![Value Edit Dialog](../screenshots/settings-menu/04_value_edit_dialog.png)

To modify text values such as the CSV delimiter:

1. Click Edit next to the field you want to change.
2. A text input dialog opens with the current value pre-filled.
3. Modify the text as needed.
4. Click Save to confirm. The new value is immediately stored.
5. (Optional) Click Apply in the Settings panel for confirmation.

### Configuring Paths

To set database or folder paths:

1. Click Browse next to the path field.
2. A native file or folder selection dialog opens.
3. Navigate to and select the desired file or folder.
4. The new path is immediately displayed and stored.
5. (Optional) Click Apply in the Settings panel to confirm.

### Changing the Settings Password

![Change Password Dialog](../screenshots/settings-menu/05_change_password_dialog.png)

To update your Settings password:

1. In the Settings password row, click Change.
2. Enter your current password in the first field.
3. Enter your new password in the second field.
4. Re-enter the new password in the confirmation field.
5. Click Update Password to save the change.

## User Interface Features

- **Path Truncation**: Long file paths are displayed on one line, truncated intelligently
  to keep the filename and relevant directory components visible.
- **Auto Focus**: When a dialog opens with multiple input fields, focus automatically
  moves to the first field for faster data entry.
- **Password Security**: Passwords are never displayed in clear text—always masked with asterisks.
- **Error Highlighting**: Validation errors are shown in red to make failures immediately visible.
- **Immediate Persistence**: All changes are immediately written to the database.

## Troubleshooting

### Password is rejected

- The error text is highlighted in red for clear feedback.
- Verify that CAPS LOCK is not enabled (passwords are case-sensitive).
- Ensure you are entering the correct password.
- Contact your system administrator if you cannot remember your password.

### Cannot select a path

- Verify that the drive or network location is accessible and connected.
- Check that you have read permissions for the selected folder or file.
- For network paths, ensure the resource is online and reachable.

### Changes are not saved

- Click Apply in the Settings panel to ensure changes are persisted.
- Note: The Decimal separator field is internally normalized to a period.

## Version Information

This manual is automatically generated by `docs/scripts/generate_settings_markdown.py`.
Screenshots and documentation are refreshed together by default.
