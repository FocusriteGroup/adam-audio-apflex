"""
SQLite database for the Sub-Pro SN/FW Workstation.

Tables
------
config          — key/value app settings
golden_samples  — multiple GS serials per product variant
parts_config    — configurable parts list with per-variant SN prefixes
units           — one record per processed complete unit
parts_scanned   — one record per part SN per unit
password        — single-row salted-hash password store
"""
import csv
import hashlib
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Schema ─────────────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS golden_samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    variant       TEXT    NOT NULL CHECK(variant IN ('A8S','A10S')),
    serial_number TEXT    NOT NULL UNIQUE,
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS parts_config (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    prefix_a8s   TEXT    NOT NULL,
    prefix_a10s  TEXT    NOT NULL,
    required     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS units (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_sn       TEXT    NOT NULL,
    variant          TEXT    NOT NULL,
    fw_version_found TEXT,
    fw_flashed       INTEGER NOT NULL DEFAULT 0,
    fw_version_final TEXT,
    result           TEXT    NOT NULL DEFAULT 'INCOMPLETE',
    timestamp        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS parts_scanned (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id          INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    part_name        TEXT    NOT NULL,
    part_sn          TEXT    NOT NULL,
    previous_unit_id INTEGER REFERENCES units(id),
    timestamp        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS password (
    id   INTEGER PRIMARY KEY CHECK(id = 1),
    hash TEXT    NOT NULL,
    salt TEXT    NOT NULL
);
"""

_DEFAULT_CONFIG: Dict[str, str] = {
    'device_name':       'SubPro',
    'target_fw_version': '',
    'fw_bin_path':       '',
}

_DEFAULT_PARTS = [
    ('DSP Board',    'ED', 'ED', 1),
    ('UI Board',     'DB', 'DB', 1),
    ('AMP+PSU',      'FD', 'FD', 1),
    ('Amp Module',   'AF', 'AG', 1),
    ('Woofer Driver','BH', 'BI', 1),
]


class Database:
    def __init__(self, db_path: Path):
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._seed()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _seed(self):
        for k, v in _DEFAULT_CONFIG.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))
        for name, pa8, pa10, req in _DEFAULT_PARTS:
            self._conn.execute(
                "INSERT OR IGNORE INTO parts_config (name,prefix_a8s,prefix_a10s,required)"
                " VALUES (?,?,?,?)", (name, pa8, pa10, req))
        self._conn.commit()

    def _ts(self) -> str:
        return datetime.now().isoformat(timespec='seconds')

    # ── Config ────────────────────────────────────────────────────────────────

    def get_config(self, key: str, default: str = '') -> str:
        row = self._conn.execute(
            "SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default

    def set_config(self, key: str, value: str):
        self._conn.execute(
            "INSERT INTO config(key,value) VALUES(?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))
        self._conn.commit()

    # ── Password ──────────────────────────────────────────────────────────────

    def has_password(self) -> bool:
        return self._conn.execute(
            "SELECT COUNT(*) FROM password").fetchone()[0] > 0

    def set_password(self, plaintext: str):
        salt = os.urandom(32).hex()
        h = hashlib.sha256((salt + plaintext).encode()).hexdigest()
        self._conn.execute(
            "INSERT INTO password(id,hash,salt) VALUES(1,?,?)"
            " ON CONFLICT(id) DO UPDATE SET hash=excluded.hash, salt=excluded.salt",
            (h, salt))
        self._conn.commit()

    def check_password(self, plaintext: str) -> bool:
        row = self._conn.execute(
            "SELECT hash,salt FROM password WHERE id=1").fetchone()
        if not row:
            return False
        h = hashlib.sha256((row['salt'] + plaintext).encode()).hexdigest()
        return h == row['hash']

    # ── Golden Samples ────────────────────────────────────────────────────────

    def get_golden_samples(self, variant: Optional[str] = None) -> List[dict]:
        if variant:
            rows = self._conn.execute(
                "SELECT * FROM golden_samples WHERE variant=? ORDER BY created_at",
                (variant,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM golden_samples ORDER BY variant, created_at").fetchall()
        return [dict(r) for r in rows]

    def add_golden_sample(self, variant: str, serial_number: str, note: str = '') -> int:
        cur = self._conn.execute(
            "INSERT INTO golden_samples(variant,serial_number,note,created_at)"
            " VALUES(?,?,?,?)",
            (variant, serial_number.strip().upper(), note.strip(), self._ts()))
        self._conn.commit()
        return cur.lastrowid

    def remove_golden_sample(self, gs_id: int):
        self._conn.execute("DELETE FROM golden_samples WHERE id=?", (gs_id,))
        self._conn.commit()

    def is_golden_sample(self, serial_number: str) -> bool:
        row = self._conn.execute(
            "SELECT id FROM golden_samples WHERE serial_number=?",
            (serial_number.strip().upper(),)).fetchone()
        return row is not None

    # ── Parts Config ──────────────────────────────────────────────────────────

    def get_parts_config(self) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM parts_config ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def add_part_config(self, name: str, prefix_a8s: str,
                        prefix_a10s: str, required: bool) -> int:
        cur = self._conn.execute(
            "INSERT INTO parts_config(name,prefix_a8s,prefix_a10s,required)"
            " VALUES(?,?,?,?)",
            (name.strip(), prefix_a8s.strip().upper(),
             prefix_a10s.strip().upper(), int(required)))
        self._conn.commit()
        return cur.lastrowid

    def update_part_config(self, part_id: int, name: str, prefix_a8s: str,
                           prefix_a10s: str, required: bool):
        self._conn.execute(
            "UPDATE parts_config SET name=?,prefix_a8s=?,prefix_a10s=?,required=?"
            " WHERE id=?",
            (name.strip(), prefix_a8s.strip().upper(),
             prefix_a10s.strip().upper(), int(required), part_id))
        self._conn.commit()

    def remove_part_config(self, part_id: int):
        self._conn.execute("DELETE FROM parts_config WHERE id=?", (part_id,))
        self._conn.commit()

    # ── Units ─────────────────────────────────────────────────────────────────

    def create_unit(self, product_sn: str, variant: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO units(product_sn,variant,result,timestamp) VALUES(?,?,'INCOMPLETE',?)",
            (product_sn.strip().upper(), variant, self._ts()))
        self._conn.commit()
        return cur.lastrowid

    def update_unit_fw(self, unit_id: int, fw_found: str,
                       fw_flashed: bool, fw_final: str):
        self._conn.execute(
            "UPDATE units SET fw_version_found=?,fw_flashed=?,fw_version_final=?"
            " WHERE id=?",
            (fw_found, int(fw_flashed), fw_final, unit_id))
        self._conn.commit()

    def complete_unit(self, unit_id: int, result: str):
        self._conn.execute(
            "UPDATE units SET result=? WHERE id=?", (result, unit_id))
        self._conn.commit()

    def add_part_scan(self, unit_id: int, part_name: str, part_sn: str,
                      previous_unit_id: Optional[int] = None):
        self._conn.execute(
            "INSERT INTO parts_scanned(unit_id,part_name,part_sn,previous_unit_id,timestamp)"
            " VALUES(?,?,?,?,?)",
            (unit_id, part_name, part_sn.strip().upper(),
             previous_unit_id, self._ts()))
        self._conn.commit()

    def get_latest_unit_for_part_sn(self, part_sn: str) -> Optional[int]:
        """Return the unit_id that last had this part SN assigned, or None."""
        row = self._conn.execute(
            "SELECT unit_id FROM parts_scanned WHERE part_sn=?"
            " ORDER BY id DESC LIMIT 1",
            (part_sn.strip().upper(),)).fetchone()
        return row['unit_id'] if row else None

    def get_product_sn_for_unit(self, unit_id: int) -> Optional[str]:
        """Return the product SN for the given unit_id, or None."""
        row = self._conn.execute(
            "SELECT product_sn FROM units WHERE id=?", (unit_id,)).fetchone()
        return row['product_sn'] if row else None

    def get_units(self, product_sn_filter: str = '',
                  date_from: str = '', date_to: str = '') -> List[dict]:
        query = "SELECT * FROM units WHERE 1=1"
        params = []
        if product_sn_filter:
            query += " AND product_sn LIKE ?"
            params.append(f'%{product_sn_filter.upper()}%')
        if date_from:
            query += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            query += " AND timestamp <= ?"
            params.append(date_to + 'T23:59:59')
        query += " ORDER BY timestamp DESC, id DESC"
        return [dict(r) for r in self._conn.execute(query, params).fetchall()]

    def get_parts_for_unit(self, unit_id: int) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM parts_scanned WHERE unit_id=? ORDER BY id",
            (unit_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Export ────────────────────────────────────────────────────────────────

    def export_csv(self, path: Path, product_sn_filter: str = '',
                   date_from: str = '', date_to: str = ''):
        units = self.get_units(product_sn_filter, date_from, date_to)
        fieldnames = [
            'timestamp', 'product_sn', 'variant',
            'fw_version_found', 'fw_flashed', 'fw_version_final',
            'result', 'parts',
        ]
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for unit in units:
                parts = self.get_parts_for_unit(unit['id'])
                parts_str = '; '.join(
                    f"{p['part_name']}={p['part_sn']}"
                    + (f"[reassigned from {self.get_product_sn_for_unit(p['previous_unit_id']) or p['previous_unit_id']}]"
                       if p['previous_unit_id'] else '')
                    for p in parts
                )
                w.writerow({
                    'timestamp':        unit['timestamp'],
                    'product_sn':       unit['product_sn'],
                    'variant':          unit['variant'],
                    'fw_version_found': unit['fw_version_found'] or '',
                    'fw_flashed':       'Yes' if unit['fw_flashed'] else 'No',
                    'fw_version_final': unit['fw_version_final'] or '',
                    'result':           unit['result'],
                    'parts':            parts_str,
                })
        logger.info('Exported %d units to %s', len(units), path)
