# Test Suite – Sub-Pro SN/FW Workstation

## Overview

The test suite covers the two pure-logic layers of the application: the database and the serial-number validator. These are the layers where bugs are most likely to cause silent data corruption or incorrectly accepted/rejected barcodes in production.

GUI screens and device communication are not covered by automated tests because they require either a running Kivy event loop or a physical device on the network. They are verified manually.

| File | Scope | Tests |
|---|---|---|
| `tests/test_database.py` | `app/db/database.py` — all CRUD operations | 48 |
| `tests/test_sn_validator.py` | `app/services/sn_validator.py` — format validation and decoding | 81 |
| **Total** | | **129** |

All 129 tests pass on Python 3.9 with pytest 8.4.

---

## How to Run

From the repository root, with the virtual environment active:

```powershell
python -m pytest SubPro_SN_FW_Workstation/tests/ -v
```

With HTML report:

```powershell
python -m pytest SubPro_SN_FW_Workstation/tests/ -v `
    --html=SubPro_SN_FW_Workstation/logs/test_report.html `
    --self-contained-html
```

Requirements:

```
pytest
pytest-html   # optional, for HTML report
```

---

## Shared Infrastructure

### `conftest.py`

Provides two pytest fixtures available to all test files:

#### `db` fixture (function-scoped)

```python
@pytest.fixture
def db(tmp_path):
    from app.db.database import Database
    return Database(tmp_path / "test.db")
```

Creates a fresh, isolated SQLite database in a temporary directory for every test. No test shares state with any other test.

#### `db_with_gs` fixture (function-scoped)

Extends `db` with two A8S golden samples (`CIGS00001`, `CIGS00002`) and one A10S golden sample (`CJGS00001`) pre-registered.

---

## Database Tests (`test_database.py`)

### TestSchemaAndSeeding (4 tests)

Verifies the database is correctly initialised on first open.

| Test | What it checks |
|---|---|
| `test_all_tables_created` | All six expected tables exist after `Database()` construction |
| `test_default_config_keys_present` | `device_name`, `target_fw_version`, `fw_bin_path` seeded with correct defaults |
| `test_default_parts_seeded` | All five default part rows present (DSP Board, UI Board, AMP+PSU, Amp Module, Woofer Driver) |
| `test_seed_is_idempotent` | Opening the same database file twice does not duplicate seed rows |

---

### TestConfig (4 tests)

Verifies key/value configuration storage.

| Test | What it checks |
|---|---|
| `test_get_missing_key_returns_default` | Unknown keys return `''` or a caller-supplied default |
| `test_set_and_get` | Written values are immediately readable |
| `test_set_overwrites` | Second `set_config` call replaces the first value |
| `test_set_new_key` | Arbitrary new keys can be created at runtime |

---

### TestPassword (8 tests)

Verifies the salted-hash password system.

| Test | What it checks |
|---|---|
| `test_no_password_on_fresh_db` | `has_password()` returns `False` on a new database |
| `test_set_creates_password` | `has_password()` returns `True` after `set_password()` |
| `test_correct_password_accepted` | `check_password()` returns `True` for the stored password |
| `test_wrong_password_rejected` | `check_password()` returns `False` for a different string |
| `test_empty_string_not_auto_accepted` | Empty string is not accepted as any password |
| `test_check_before_set_returns_false` | `check_password()` is safe to call before any password is set |
| `test_password_change` | After `set_password('new')`, only the new password is accepted |
| `test_same_plaintext_different_hash` | Two `set_password('same')` calls produce different stored hashes (unique random salts) |

---

### TestGoldenSamples (9 tests)

Verifies the golden-sample registry.

| Test | What it checks |
|---|---|
| `test_add_and_retrieve_a8s` | Adding a GS and reading it back for A8S variant |
| `test_add_multiple_per_variant` | Multiple GS entries per variant are supported |
| `test_get_all_variants` | `get_golden_samples()` with no filter returns all variants |
| `test_is_golden_true` | Registered SNs are identified as golden samples |
| `test_is_golden_false_for_production_sn` | Production SNs are not false-positives |
| `test_is_golden_case_insensitive` | Lookup is case-insensitive (`cigs00001` matches `CIGS00001`) |
| `test_remove_golden_sample` | Removed GS is no longer detected by `is_golden_sample()` |
| `test_duplicate_sn_raises` | Adding the same SN twice raises an exception (UNIQUE constraint) |
| `test_invalid_variant_raises` | Adding a GS with an invalid variant string raises an exception (CHECK constraint) |

---

### TestPartsConfig (5 tests)

Verifies the configurable parts list.

| Test | What it checks |
|---|---|
| `test_default_parts_present` | 5 default parts seeded on first open |
| `test_add_custom_part` | New parts can be added and appear in `get_parts_config()` |
| `test_update_part` | Existing parts can be edited (prefix and required flag) |
| `test_remove_part` | Removed parts no longer appear in the list |
| `test_required_flag` | `required=False` is stored and returned correctly |

---

### TestUnits (6 tests)

Verifies the unit provisioning lifecycle.

| Test | What it checks |
|---|---|
| `test_create_unit_returns_id` | `create_unit()` returns a positive integer ID |
| `test_created_unit_is_incomplete` | Freshly created unit has `result = 'INCOMPLETE'` |
| `test_update_unit_fw` | Firmware columns are written by `update_unit_fw()` |
| `test_complete_unit_pass` | `complete_unit('PASS')` sets the result correctly |
| `test_complete_unit_fail` | `complete_unit('FAIL')` sets the result correctly |
| `test_multiple_units` | Multiple units coexist independently in the database |

---

### TestPartScanning (4 tests)

Verifies component SN recording and re-assignment detection.

| Test | What it checks |
|---|---|
| `test_add_part_scan` | A part scan is recorded with correct name, SN, and null `previous_unit_id` |
| `test_add_multiple_parts` | All five parts can be recorded for a single unit |
| `test_reassignment_detected` | A part SN previously on unit A is detected when scanned for unit B; `previous_unit_id` is set |
| `test_no_reassignment_for_new_part` | A never-seen part SN returns `None` from `get_latest_unit_for_part_sn()` |

---

### TestFiltering (4 tests)

Verifies the query filter logic used by the History screen.

| Test | What it checks |
|---|---|
| `test_filter_by_sn_partial` | Partial SN match returns only matching units |
| `test_filter_by_sn_no_match` | Non-matching filter returns empty list |
| `test_no_filter_returns_all` | Unfiltered query returns all units |
| `test_results_ordered_newest_first` | Results are ordered by `timestamp DESC, id DESC`; the most recently inserted unit appears first, with `id` as a tiebreaker within the same second |

---

### TestExport (4 tests)

Verifies CSV export output.

| Test | What it checks |
|---|---|
| `test_export_creates_file` | Export creates the file at the given path |
| `test_export_contains_correct_data` | CSV contains correct product SN, variant, result, and part SNs |
| `test_export_reassignment_flagged` | Re-assigned parts include `[reassigned from #N]` in the `parts` column |
| `test_export_respects_sn_filter` | Export applies the same SN filter as `get_units()` |

---

## SN Validator Tests (`test_sn_validator.py`)

### TestLength (5 tests)

| Test | What it checks |
|---|---|
| `test_exactly_9_chars_is_valid` | A 9-character SN passes |
| `test_too_short_fails` | SNs shorter than 9 characters are rejected with a length error |
| `test_too_long_fails` | SNs longer than 9 characters are rejected |
| `test_empty_string_fails` | Empty string is rejected |
| `test_whitespace_stripped` | Leading/trailing whitespace is stripped before validation |

---

### TestPrefix (3 tests)

| Test | What it checks |
|---|---|
| `test_alpha_prefix_valid` | Two-letter prefix passes |
| `test_digit_in_prefix_fails` | A digit in the prefix position is rejected |
| `test_prefix_lowercase_accepted` | Lowercase input is normalised to uppercase before validation |

---

### TestYearCode (38 parametrised + 2 tests)

| Test | What it checks |
|---|---|
| `test_valid_year_codes[0-9, A-Z]` | All 36 valid year codes are accepted (parametrised; G is tested with its valid pair GS) |
| `test_invalid_year_code_fails` | Non-alphanumeric year code (`!`) is rejected |
| `test_g_without_s_is_invalid_month` | Year code `G` paired with a non-`S` month code is rejected |

---

### TestMonthCode (10 tests)

| Test | What it checks |
|---|---|
| `test_month_codes[1,2,9,A,B,C]` | All valid month codes are accepted |
| `test_month_codes[0,D,E]` | Invalid month codes are rejected |
| `test_s_month_code_only_valid_with_gs` | Month code `S` paired with a non-`G` year code is rejected |

---

### TestSequentialNumber (5 tests)

| Test | What it checks |
|---|---|
| `test_all_digits_valid` | Five decimal digits pass |
| `test_leading_zeros_valid` | `00001` is a valid sequential number |
| `test_all_zeros_valid` | `00000` is syntactically valid |
| `test_non_digit_in_number_fails` | A non-digit character in positions 4-8 is rejected |
| `test_letter_in_number_fails` | Letters in the number section are rejected |

---

### TestGoldenSampleFormat (4 tests)

| Test | What it checks |
|---|---|
| `test_gs_format_detected` | SNs with `GS` at positions 2-3 are identified as golden-sample format |
| `test_non_gs_format_not_detected` | Production SNs are not false-positives |
| `test_gs_format_validates_ok` | Golden-sample SNs pass full validation |
| `test_g_without_s_fails` | `G` year code without `S` month code fails full validation |

---

### TestProductVariant (4 tests)

| Test | What it checks |
|---|---|
| `test_ci_is_a8s` | `CI` prefix maps to `'A8S'` |
| `test_cj_is_a10s` | `CJ` prefix maps to `'A10S'` |
| `test_unknown_prefix_returns_none` | Unknown prefix returns `None` |
| `test_lowercase_handled` | Lowercase input is normalised |

---

### TestPartSNValidation (6 tests)

| Test | What it checks |
|---|---|
| `test_correct_prefix_passes` | Correct part prefix is accepted |
| `test_wrong_prefix_fails` | Wrong prefix returns a descriptive error including the part name |
| `test_invalid_format_fails_before_prefix` | Format error is caught before prefix check |
| `test_prefix_case_insensitive` | Lowercase part SNs are accepted |
| `test_variant_aware_a8s_amp` | A8S Amp Module prefix `AF` is accepted for A8S |
| `test_variant_aware_a10s_amp_wrong_variant` | A8S Amp Module prefix `AF` is rejected when A10S prefix `AG` is expected |

---

### TestDecodeSN (5 tests)

| Test | What it checks |
|---|---|
| `test_decode_production_sn` | `CI6400001` decodes to year 2026, month 4, number 1, not GS |
| `test_decode_golden_sample` | `CIGS00001` decodes with null year/month and `is_golden_sample=True` |
| `test_decode_a10s` | `CJ6500001` decodes to year 2026, month 5 |
| `test_decode_year_letter_code` | Year code `A` decodes to 2030 |
| `test_decode_october` | Month code `A` decodes to month 10 |

---

### TestGetPrefix (1 test)

| Test | What it checks |
|---|---|
| `test_returns_uppercase_prefix` | `get_prefix()` returns the two-character prefix, upper-cased |

---

## Known Gaps

| Area | Reason not tested |
|---|---|
| GUI screens | Require a running Kivy event loop; tested manually |
| `DeviceService` / `OCADevice` | Require a physical device on the network |
| Unlock screen | Placeholder; no logic implemented yet |
| Date range filtering in `get_units` | Relies on ISO string comparison; covered by manual spot-checks |
