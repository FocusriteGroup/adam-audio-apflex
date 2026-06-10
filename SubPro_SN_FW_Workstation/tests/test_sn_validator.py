"""
test_sn_validator.py – pytest tests for app/services/sn_validator.py

Coverage targets:
  - validate_sn: length, prefix, year code, month code, sequential number
  - Golden-sample format detection
  - Product variant lookup
  - Part SN validation with prefix check
  - SN decoding
"""
import pytest
from app.services import sn_validator as v


# ---------------------------------------------------------------------------
# validate_sn – length
# ---------------------------------------------------------------------------

class TestLength:

    def test_exactly_9_chars_is_valid(self):
        ok, err = v.validate_sn('CI6400001')
        assert ok
        assert err == ''

    def test_too_short_fails(self):
        ok, err = v.validate_sn('CI64000')
        assert not ok
        assert 'length' in err.lower()

    def test_too_long_fails(self):
        ok, err = v.validate_sn('CI64000011')
        assert not ok
        assert 'length' in err.lower()

    def test_empty_string_fails(self):
        ok, err = v.validate_sn('')
        assert not ok

    def test_whitespace_stripped(self):
        ok, _ = v.validate_sn('  CI6400001  ')
        assert ok


# ---------------------------------------------------------------------------
# validate_sn – prefix
# ---------------------------------------------------------------------------

class TestPrefix:

    def test_alpha_prefix_valid(self):
        ok, _ = v.validate_sn('CI6400001')
        assert ok

    def test_digit_in_prefix_fails(self):
        ok, err = v.validate_sn('1I6400001')
        assert not ok
        assert 'prefix' in err.lower() or 'letter' in err.lower()

    def test_prefix_lowercase_accepted(self):
        ok, _ = v.validate_sn('ci6400001')
        assert ok


# ---------------------------------------------------------------------------
# validate_sn – year code
# ---------------------------------------------------------------------------

class TestYearCode:

    @pytest.mark.parametrize('year_code', list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    def test_valid_year_codes(self, year_code):
        if year_code == 'G':
            # G is only valid paired with S in month position (golden sample)
            ok, _ = v.validate_sn(f'CI{year_code}S00001')
            assert ok
        else:
            ok, _ = v.validate_sn(f'CI{year_code}100001')
            assert ok, f'Year code {year_code} should be valid'

    def test_invalid_year_code_fails(self):
        # No valid code maps to '!'
        ok, err = v.validate_sn('CI!100001')
        assert not ok

    def test_g_without_s_is_invalid_month(self):
        # G in year position requires S in month position; G+1 should fail on month code
        ok, err = v.validate_sn('CIG100001')
        assert not ok
        assert 'month' in err.lower()


# ---------------------------------------------------------------------------
# validate_sn – month code
# ---------------------------------------------------------------------------

class TestMonthCode:

    @pytest.mark.parametrize('month_code,expected', [
        ('1', True), ('2', True), ('9', True),
        ('A', True), ('B', True), ('C', True),
        ('0', False),   # 0 is not a valid month
        ('D', False),   # D is not a valid month code
        ('E', False),
    ])
    def test_month_codes(self, month_code, expected):
        ok, _ = v.validate_sn(f'CI6{month_code}00001')
        assert ok == expected

    def test_s_month_code_only_valid_with_gs(self):
        # S alone (without G in year) is invalid
        ok, err = v.validate_sn('CI6S00001')
        assert not ok


# ---------------------------------------------------------------------------
# validate_sn – sequential number
# ---------------------------------------------------------------------------

class TestSequentialNumber:

    def test_all_digits_valid(self):
        ok, _ = v.validate_sn('CI6400001')
        assert ok

    def test_leading_zeros_valid(self):
        ok, _ = v.validate_sn('CI6400001')
        assert ok

    def test_all_zeros_valid(self):
        ok, _ = v.validate_sn('CI6400000')
        assert ok

    def test_non_digit_in_number_fails(self):
        ok, err = v.validate_sn('CI640X001')
        assert not ok
        assert 'digit' in err.lower() or 'number' in err.lower()

    def test_letter_in_number_fails(self):
        ok, err = v.validate_sn('CI640ABCD')
        assert not ok


# ---------------------------------------------------------------------------
# Golden sample format
# ---------------------------------------------------------------------------

class TestGoldenSampleFormat:

    def test_gs_format_detected(self):
        assert v.is_golden_sample_format('CIGS00001') is True
        assert v.is_golden_sample_format('CJGS00001') is True

    def test_non_gs_format_not_detected(self):
        assert v.is_golden_sample_format('CI6400001') is False

    def test_gs_format_validates_ok(self):
        ok, _ = v.validate_sn('CIGS00001')
        assert ok

    def test_g_without_s_fails(self):
        ok, _ = v.validate_sn('CIG400001')
        assert not ok


# ---------------------------------------------------------------------------
# Product variant
# ---------------------------------------------------------------------------

class TestProductVariant:

    def test_ci_is_a8s(self):
        assert v.get_product_variant('CI6400001') == 'A8S'

    def test_cj_is_a10s(self):
        assert v.get_product_variant('CJ6500001') == 'A10S'

    def test_unknown_prefix_returns_none(self):
        assert v.get_product_variant('XX6400001') is None

    def test_lowercase_handled(self):
        assert v.get_product_variant('ci6400001') == 'A8S'


# ---------------------------------------------------------------------------
# Part SN validation
# ---------------------------------------------------------------------------

class TestPartSNValidation:

    def test_correct_prefix_passes(self):
        ok, err = v.validate_part_sn('ED6400001', 'DSP Board', 'ED')
        assert ok
        assert err == ''

    def test_wrong_prefix_fails(self):
        ok, err = v.validate_part_sn('AF6400001', 'DSP Board', 'ED')
        assert not ok
        assert 'DSP Board' in err

    def test_invalid_format_fails_before_prefix(self):
        ok, err = v.validate_part_sn('ED640', 'DSP Board', 'ED')
        assert not ok
        assert 'length' in err.lower()

    def test_prefix_case_insensitive(self):
        ok, _ = v.validate_part_sn('ed6400001', 'DSP Board', 'ED')
        assert ok

    def test_variant_aware_a8s_amp(self):
        ok, _ = v.validate_part_sn('AF6400001', 'Amp Module', 'AF')
        assert ok

    def test_variant_aware_a10s_amp_wrong_variant(self):
        ok, err = v.validate_part_sn('AF6400001', 'Amp Module', 'AG')
        assert not ok
        assert 'Amp Module' in err


# ---------------------------------------------------------------------------
# Decode SN
# ---------------------------------------------------------------------------

class TestDecodeSN:

    def test_decode_production_sn(self):
        decoded = v.decode_sn('CI6400001')
        assert decoded['prefix'] == 'CI'
        assert decoded['year'] == 2026
        assert decoded['month'] == 4
        assert decoded['number'] == 1
        assert decoded['is_golden_sample'] is False

    def test_decode_golden_sample(self):
        decoded = v.decode_sn('CIGS00001')
        assert decoded['prefix'] == 'CI'
        assert decoded['year'] is None
        assert decoded['month'] is None
        assert decoded['is_golden_sample'] is True

    def test_decode_a10s(self):
        decoded = v.decode_sn('CJ6500001')
        assert decoded['prefix'] == 'CJ'
        assert decoded['year'] == 2026
        assert decoded['month'] == 5

    def test_decode_year_letter_code(self):
        # 'A' year code = 2030
        decoded = v.decode_sn('CIA100001')
        assert decoded['year'] == 2030

    def test_decode_october(self):
        # Month A = October
        decoded = v.decode_sn('CI6A00001')
        assert decoded['month'] == 10


# ---------------------------------------------------------------------------
# get_prefix
# ---------------------------------------------------------------------------

class TestGetPrefix:

    def test_returns_uppercase_prefix(self):
        assert v.get_prefix('CI6400001') == 'CI'
        assert v.get_prefix('ed6400001') == 'ED'
