"""
test_database.py – pytest tests for app/db/database.py

Coverage targets:
  - Schema creation and seeding
  - Config read/write
  - Password hashing and verification
  - Golden sample CRUD and variant validation gate
  - Parts config CRUD
  - Unit lifecycle (create → fw update → complete)
  - Part scanning, re-assignment detection
  - Filtering and export
"""
import csv
import pathlib
import pytest


# ---------------------------------------------------------------------------
# Schema and seeding
# ---------------------------------------------------------------------------

class TestSchemaAndSeeding:

    def test_all_tables_created(self, db):
        tables = {r[0] for r in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert tables >= {'config', 'golden_samples', 'parts_config',
                          'units', 'parts_scanned', 'password'}

    def test_default_config_keys_present(self, db):
        assert db.get_config('device_name') == 'SubPro'
        assert db.get_config('target_fw_version') == ''
        assert db.get_config('fw_bin_path') == ''

    def test_default_parts_seeded(self, db):
        parts = db.get_parts_config()
        names = [p['name'] for p in parts]
        assert 'DSP Board' in names
        assert 'UI Board' in names
        assert 'AMP+PSU' in names
        assert 'Amp Module' in names
        assert 'Woofer Driver' in names

    def test_seed_is_idempotent(self, tmp_path):
        """Opening the same DB twice must not duplicate seed rows."""
        from app.db.database import Database
        path = tmp_path / "seed.db"
        Database(path)
        db2 = Database(path)
        assert len(db2.get_parts_config()) == 5


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:

    def test_get_missing_key_returns_default(self, db):
        assert db.get_config('no_such_key') == ''
        assert db.get_config('no_such_key', 'fallback') == 'fallback'

    def test_set_and_get(self, db):
        db.set_config('target_fw_version', '1.0.0rc2')
        assert db.get_config('target_fw_version') == '1.0.0rc2'

    def test_set_overwrites(self, db):
        db.set_config('device_name', 'First')
        db.set_config('device_name', 'Second')
        assert db.get_config('device_name') == 'Second'

    def test_set_new_key(self, db):
        db.set_config('custom_key', 'hello')
        assert db.get_config('custom_key') == 'hello'


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------

class TestPassword:

    def test_no_password_on_fresh_db(self, db):
        assert db.has_password() is False

    def test_set_creates_password(self, db):
        db.set_password('secret')
        assert db.has_password() is True

    def test_correct_password_accepted(self, db):
        db.set_password('correct')
        assert db.check_password('correct') is True

    def test_wrong_password_rejected(self, db):
        db.set_password('correct')
        assert db.check_password('wrong') is False

    def test_empty_string_not_auto_accepted(self, db):
        db.set_password('notempty')
        assert db.check_password('') is False

    def test_check_before_set_returns_false(self, db):
        assert db.check_password('anything') is False

    def test_password_change(self, db):
        db.set_password('old')
        db.set_password('new')
        assert db.check_password('new') is True
        assert db.check_password('old') is False

    def test_same_plaintext_different_hash(self, db):
        """Two set_password calls must produce different hashes (different salts)."""
        db.set_password('same')
        h1 = db._conn.execute("SELECT hash FROM password WHERE id=1").fetchone()[0]
        db.set_password('same')
        h2 = db._conn.execute("SELECT hash FROM password WHERE id=1").fetchone()[0]
        assert h1 != h2


# ---------------------------------------------------------------------------
# Golden Samples
# ---------------------------------------------------------------------------

class TestGoldenSamples:

    def test_add_and_retrieve_a8s(self, db):
        db.add_golden_sample('A8S', 'CIGS00001', 'unit 1')
        samples = db.get_golden_samples('A8S')
        assert len(samples) == 1
        assert samples[0]['serial_number'] == 'CIGS00001'
        assert samples[0]['variant'] == 'A8S'

    def test_add_multiple_per_variant(self, db):
        db.add_golden_sample('A8S', 'CIGS00001')
        db.add_golden_sample('A8S', 'CIGS00002')
        db.add_golden_sample('A10S', 'CJGS00001')
        assert len(db.get_golden_samples('A8S')) == 2
        assert len(db.get_golden_samples('A10S')) == 1

    def test_get_all_variants(self, db):
        db.add_golden_sample('A8S',  'CIGS00001')
        db.add_golden_sample('A10S', 'CJGS00001')
        assert len(db.get_golden_samples()) == 2

    def test_is_golden_true(self, db_with_gs):
        assert db_with_gs.is_golden_sample('CIGS00001') is True
        assert db_with_gs.is_golden_sample('CJGS00001') is True

    def test_is_golden_false_for_production_sn(self, db_with_gs):
        assert db_with_gs.is_golden_sample('CI6400001') is False

    def test_is_golden_case_insensitive(self, db):
        db.add_golden_sample('A8S', 'CIGS00001')
        assert db.is_golden_sample('cigs00001') is True

    def test_remove_golden_sample(self, db):
        gs_id = db.add_golden_sample('A8S', 'CIGS00001')
        db.remove_golden_sample(gs_id)
        assert db.get_golden_samples('A8S') == []
        assert db.is_golden_sample('CIGS00001') is False

    def test_duplicate_sn_raises(self, db):
        db.add_golden_sample('A8S', 'CIGS00001')
        with pytest.raises(Exception):
            db.add_golden_sample('A8S', 'CIGS00001')  # UNIQUE constraint

    def test_invalid_variant_raises(self, db):
        with pytest.raises(Exception):
            db.add_golden_sample('A11S', 'CIGS00001')  # CHECK constraint


# ---------------------------------------------------------------------------
# Parts Configuration
# ---------------------------------------------------------------------------

class TestPartsConfig:

    def test_default_parts_present(self, db):
        parts = db.get_parts_config()
        assert len(parts) == 5

    def test_add_custom_part(self, db):
        pid = db.add_part_config('Tweeter', 'TC', 'TD', required=True)
        parts = db.get_parts_config()
        names = [p['name'] for p in parts]
        assert 'Tweeter' in names

    def test_update_part(self, db):
        parts = db.get_parts_config()
        dsp = next(p for p in parts if p['name'] == 'DSP Board')
        db.update_part_config(dsp['id'], 'DSP Board', 'EE', 'EE', False)
        updated = next(p for p in db.get_parts_config() if p['name'] == 'DSP Board')
        assert updated['prefix_a8s'] == 'EE'
        assert updated['required'] == 0

    def test_remove_part(self, db):
        pid = db.add_part_config('Temp Part', 'TP', 'TP', True)
        db.remove_part_config(pid)
        names = [p['name'] for p in db.get_parts_config()]
        assert 'Temp Part' not in names

    def test_required_flag(self, db):
        pid = db.add_part_config('Optional Part', 'OP', 'OP', False)
        part = next(p for p in db.get_parts_config() if p['id'] == pid)
        assert part['required'] == 0


# ---------------------------------------------------------------------------
# Unit Lifecycle
# ---------------------------------------------------------------------------

class TestUnits:

    def test_create_unit_returns_id(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        assert isinstance(uid, int)
        assert uid > 0

    def test_created_unit_is_incomplete(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        units = db.get_units()
        unit = next(u for u in units if u['id'] == uid)
        assert unit['result'] == 'INCOMPLETE'
        assert unit['product_sn'] == 'CI6400001'
        assert unit['variant'] == 'A8S'

    def test_update_unit_fw(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        db.update_unit_fw(uid, '1.0.0rc1', True, '1.0.0rc2')
        unit = next(u for u in db.get_units() if u['id'] == uid)
        assert unit['fw_version_found'] == '1.0.0rc1'
        assert unit['fw_flashed'] == 1
        assert unit['fw_version_final'] == '1.0.0rc2'

    def test_complete_unit_pass(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        db.complete_unit(uid, 'PASS')
        unit = next(u for u in db.get_units() if u['id'] == uid)
        assert unit['result'] == 'PASS'

    def test_complete_unit_fail(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        db.complete_unit(uid, 'FAIL')
        unit = next(u for u in db.get_units() if u['id'] == uid)
        assert unit['result'] == 'FAIL'

    def test_multiple_units(self, db):
        db.create_unit('CI6400001', 'A8S')
        db.create_unit('CJ6500001', 'A10S')
        assert len(db.get_units()) == 2


# ---------------------------------------------------------------------------
# Part Scanning
# ---------------------------------------------------------------------------

class TestPartScanning:

    def test_add_part_scan(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        db.add_part_scan(uid, 'DSP Board', 'ED6400001')
        parts = db.get_parts_for_unit(uid)
        assert len(parts) == 1
        assert parts[0]['part_sn'] == 'ED6400001'
        assert parts[0]['part_name'] == 'DSP Board'
        assert parts[0]['previous_unit_id'] is None

    def test_add_multiple_parts(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        for name, sn in [('DSP Board', 'ED6400001'), ('UI Board', 'DB6400001'),
                         ('AMP+PSU', 'FD6400001'), ('Amp Module', 'AF6400001'),
                         ('Woofer Driver', 'BH6400001')]:
            db.add_part_scan(uid, name, sn)
        assert len(db.get_parts_for_unit(uid)) == 5

    def test_reassignment_detected(self, db):
        uid1 = db.create_unit('CI6400001', 'A8S')
        db.add_part_scan(uid1, 'Amp Module', 'AF6400001')

        uid2 = db.create_unit('CI6400002', 'A8S')
        prev = db.get_latest_unit_for_part_sn('AF6400001')
        assert prev == uid1

        db.add_part_scan(uid2, 'Amp Module', 'AF6400001', previous_unit_id=prev)
        parts = db.get_parts_for_unit(uid2)
        assert parts[0]['previous_unit_id'] == uid1

    def test_no_reassignment_for_new_part(self, db):
        uid = db.create_unit('CI6400001', 'A8S')
        prev = db.get_latest_unit_for_part_sn('ED9900001')
        assert prev is None


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:

    def _setup_units(self, db):
        uid1 = db.create_unit('CI6400001', 'A8S')
        db.complete_unit(uid1, 'PASS')
        uid2 = db.create_unit('CJ6500001', 'A10S')
        db.complete_unit(uid2, 'FAIL')
        return uid1, uid2

    def test_filter_by_sn_partial(self, db):
        self._setup_units(db)
        results = db.get_units(product_sn_filter='CI64')
        assert len(results) == 1
        assert results[0]['product_sn'] == 'CI6400001'

    def test_filter_by_sn_no_match(self, db):
        self._setup_units(db)
        results = db.get_units(product_sn_filter='ZZ99')
        assert results == []

    def test_no_filter_returns_all(self, db):
        self._setup_units(db)
        assert len(db.get_units()) == 2

    def test_results_ordered_newest_first(self, db):
        """get_units orders by timestamp DESC; same-second inserts may share timestamp.
        Verify both units are returned and the product_sn of the second appears first."""
        import time
        db.create_unit('CI6400001', 'A8S')
        time.sleep(0.01)   # ensure different timestamps
        db.create_unit('CI6400002', 'A8S')
        results = db.get_units()
        assert results[0]['product_sn'] == 'CI6400002'
        assert results[1]['product_sn'] == 'CI6400001'


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

class TestExport:

    def test_export_creates_file(self, db, tmp_path):
        uid = db.create_unit('CI6400001', 'A8S')
        db.update_unit_fw(uid, '1.0.0rc1', True, '1.0.0rc2')
        db.add_part_scan(uid, 'DSP Board', 'ED6400001')
        db.complete_unit(uid, 'PASS')

        out = tmp_path / 'export.csv'
        db.export_csv(out)
        assert out.exists()

    def test_export_contains_correct_data(self, db, tmp_path):
        uid = db.create_unit('CI6400001', 'A8S')
        db.update_unit_fw(uid, '1.0.0rc2', False, '1.0.0rc2')
        db.add_part_scan(uid, 'DSP Board', 'ED6400001')
        db.complete_unit(uid, 'PASS')

        out = tmp_path / 'export.csv'
        db.export_csv(out)

        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]['product_sn'] == 'CI6400001'
        assert rows[0]['variant'] == 'A8S'
        assert rows[0]['result'] == 'PASS'
        assert 'DSP Board=ED6400001' in rows[0]['parts']

    def test_export_reassignment_flagged(self, db, tmp_path):
        uid1 = db.create_unit('CI6400001', 'A8S')
        db.add_part_scan(uid1, 'Amp Module', 'AF6400001')
        db.complete_unit(uid1, 'PASS')

        uid2 = db.create_unit('CI6400002', 'A8S')
        db.add_part_scan(uid2, 'Amp Module', 'AF6400001', previous_unit_id=uid1)
        db.complete_unit(uid2, 'PASS')

        out = tmp_path / 'export.csv'
        db.export_csv(out, product_sn_filter='CI6400002')

        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        assert 'reassigned' in rows[0]['parts']

    def test_export_respects_sn_filter(self, db, tmp_path):
        for sn in ['CI6400001', 'CI6400002', 'CJ6500001']:
            uid = db.create_unit(sn, 'A8S' if sn.startswith('CI') else 'A10S')
            db.complete_unit(uid, 'PASS')

        out = tmp_path / 'export.csv'
        db.export_csv(out, product_sn_filter='CI64')

        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert all(r['product_sn'].startswith('CI64') for r in rows)
