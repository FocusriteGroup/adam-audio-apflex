"""
DataTools Settings Store
========================

This module provides persistent application settings storage for DataTools.
The storage backend is SQLite to keep the foundation aligned with future
database-driven features.

Design goals:
- Single local database file for DataTools app state
- Simple key/value settings table for early-stage flexibility
- Explicit defaults for production-relevant paths and security controls
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict


class DataToolsSettingsStore:
    """
    Persistent settings manager backed by SQLite.

    The class creates and manages a single DataTools local database file and
    stores app settings in a lightweight key/value table.
    """

    def __init__(self, datatools_root: Path):
        """
        Initialize the settings store.

        Args:
            datatools_root: Absolute path to the DataTools folder.
        """
        self.datatools_root = Path(datatools_root).resolve()
        self.repo_root = self.datatools_root.parent
        self.db_path = self.datatools_root / "Data" / "db" / "datatools.db"

        # Ensure parent directories exist before opening SQLite.
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize_database()
        self._ensure_default_settings()
        self._migrate_legacy_external_paths()

    def _connect(self) -> sqlite3.Connection:
        """Create and return a SQLite connection to the DataTools DB."""
        return sqlite3.connect(str(self.db_path))

    def _initialize_database(self) -> None:
        """Create required tables if they do not exist yet."""
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _default_settings(self) -> Dict[str, str]:
        """
        Build the default settings dictionary.

        Returns:
            Dictionary with all default settings as strings.
        """
        default_export_folder = str((self.datatools_root / "Exports").resolve())
        matching_db_path = str((self.repo_root / "Matching_App" / "Data" / "db" / "matcher.db").resolve())
        sn_fw_db_path = str((self.repo_root / "SubPro_SN_FW_Workstation" / "Data" / "subpro_workstation.db").resolve())
        mac_db_path = str((self.repo_root / "SubProMACAddresses" / "db" / "mac_addresses.db").resolve())

        return {
            "app_password": "admin",
            "last_input_folder": "",
            "default_export_folder": default_export_folder,
            "csv_delimiter": ",",
            "decimal_separator": ".",
            "matching_db_path": matching_db_path,
            "matching_overlay_start": "",
            "matching_overlay_end": "",
            "sn_fw_db_path": sn_fw_db_path,
            "mac_db_path": mac_db_path,
            "datatools_db_path": str(self.db_path),
            "backplate_default_serial": "123456",
            "backplate_default_mac": "DE:AD:BE:EF:00:00",
            "backplate_workstation_id": "DataTools",
            "measurements_root_path": "",
        }

    def _ensure_default_settings(self) -> None:
        """Insert missing default settings without overwriting user values."""
        defaults = self._default_settings()
        with self._connect() as connection:
            cursor = connection.cursor()
            for key, value in defaults.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, value),
                )
            connection.commit()

    def _migrate_legacy_external_paths(self) -> None:
        """
        Correct legacy external database paths that were saved under DataTools.

        Older setup flows stored external DB defaults below the DataTools folder
        (for example DataTools/Matching_App/...). Those paths are invalid for
        the real repository layout and should be upgraded once to the current
        repo-level defaults.
        """
        defaults = self._default_settings()
        legacy_root = self.datatools_root
        keys_to_check = ["matching_db_path", "sn_fw_db_path", "mac_db_path"]

        with self._connect() as connection:
            cursor = connection.cursor()
            for key in keys_to_check:
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                if not row:
                    continue

                current_value = row[0]
                try:
                    current_path = Path(current_value).resolve()
                except (OSError, RuntimeError, ValueError):
                    continue

                if legacy_root not in current_path.parents:
                    continue

                replacement_value = defaults[key]
                if current_value == replacement_value:
                    continue

                cursor.execute(
                    "UPDATE settings SET value = ? WHERE key = ?",
                    (replacement_value, key),
                )

            connection.commit()

    def get_all(self) -> Dict[str, str]:
        """
        Return all settings as a dictionary.

        Returns:
            Dictionary with setting key/value pairs.
        """
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
        return {key: value for key, value in rows}

    def get(self, key: str, default: str = "") -> str:
        """
        Return one setting value.

        Args:
            key: Setting key name.
            default: Fallback when key does not exist.

        Returns:
            Setting value as string.
        """
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        """
        Upsert one setting value.

        Args:
            key: Setting key name.
            value: Setting value to persist.
        """
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def verify_password(self, candidate: str) -> bool:
        """
        Validate a candidate password against the persisted app password.

        Args:
            candidate: User-entered password.

        Returns:
            True if password matches, otherwise False.
        """
        return candidate == self.get("app_password", "admin")

    def update_password(self, new_password: str) -> None:
        """
        Persist a new settings password.

        Args:
            new_password: New plain-text password value.
        """
        if not new_password:
            return
        self.set("app_password", new_password)

    def get_last_input_folder(self) -> str:
        """
        Return the last used input folder.

        Returns:
            Last used input folder path or an empty string.
        """
        return self.get("last_input_folder", "")

    def set_last_input_folder(self, folder_path: str) -> None:
        """
        Persist the last used input folder.

        Args:
            folder_path: Folder path selected in an input workflow.
        """
        self.set("last_input_folder", folder_path or "")
