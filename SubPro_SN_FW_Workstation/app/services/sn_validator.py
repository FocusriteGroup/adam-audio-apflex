"""
Serial-number validation for ADAM Audio Sub-Pro products.

Format (9 characters):
  [0-1]  Part ID         — two uppercase letters (A-Z)
  [2]    Year code       — 0-9 / A-Z  (0 = 2020 … Z = 2055)
                           'G' for golden samples
  [3]    Month hex       — 1-9 / A(Oct) / B(Nov) / C(Dec)
                           'S' for golden samples (paired with 'G')
  [4-8]  Sequential No.  — 5 decimal digits (00001 … 99999)

Golden-sample encoding: positions 2-3 == 'GS', digits can be any value.
"""

SN_LENGTH = 9

# Year codes: '0'=2020 … '9'=2029, 'A'=2030 … 'Z'=2055
_YEAR_MAP: dict = {str(i): 2020 + i for i in range(10)}
_YEAR_MAP.update({chr(ord('A') + i): 2030 + i for i in range(26)})

# Month hex codes: '1'=Jan … '9'=Sep, 'A'=Oct, 'B'=Nov, 'C'=Dec
_MONTH_MAP: dict = {str(i): i for i in range(1, 10)}
_MONTH_MAP.update({'A': 10, 'B': 11, 'C': 12})

_VALID_YEAR_CODES  = set(_YEAR_MAP.keys())
_VALID_MONTH_CODES = set(_MONTH_MAP.keys())

GS_YEAR_CODE  = 'G'
GS_MONTH_CODE = 'S'

# Known product prefixes → variant name
PRODUCT_PREFIXES: dict = {
    'CI': 'A8S',
    'CJ': 'A10S',
}


# ── Public API ────────────────────────────────────────────────────────────────

def validate_sn(sn: str) -> tuple:
    """
    Validate a serial number fully.

    Returns (ok: bool, error_message: str).
    On success error_message is ''.
    """
    sn = sn.strip().upper()

    if len(sn) != SN_LENGTH:
        return False, (
            f'Invalid length: expected {SN_LENGTH} characters, got {len(sn)}.'
        )

    prefix = sn[:2]
    if not prefix.isalpha():
        return False, (
            f'Invalid prefix "{prefix}": first two characters must be letters.'
        )

    year_code  = sn[2]
    month_code = sn[3]
    number_part = sn[4:]

    # Golden-sample encoding: positions 2-3 must BOTH be 'GS' together.
    # 'G' in year position is only valid when 'S' is in month position.
    is_gs = (year_code == GS_YEAR_CODE and month_code == GS_MONTH_CODE)

    if year_code == GS_YEAR_CODE and not is_gs:
        # G in year but not S in month — invalid hybrid
        return False, (
            f'Invalid month code "{month_code}" for golden-sample year code "G". '
            f'Expected "S".'
        )

    if not is_gs:
        if year_code not in _VALID_YEAR_CODES:
            return False, (
                f'Invalid year code "{year_code}". '
                f'Expected 0-9 or A-Z (0=2020 ... Z=2055).'
            )
        if month_code not in _VALID_MONTH_CODES:
            return False, (
                f'Invalid month code "{month_code}". '
                f'Expected 1-9, A (Oct), B (Nov), or C (Dec).'
            )
    if not number_part.isdigit():
        return False, (
            f'Invalid sequential number "{number_part}": must be 5 decimal digits.'
        )

    return True, ''


def get_product_variant(sn: str) -> 'str | None':
    """Return 'A8S' or 'A10S' for a product SN, or None if prefix is unknown."""
    return PRODUCT_PREFIXES.get(sn.strip().upper()[:2])


def is_golden_sample_format(sn: str) -> bool:
    """Return True if the SN encodes the golden-sample date (GS in positions 2-3)."""
    sn = sn.strip().upper()
    return len(sn) == SN_LENGTH and sn[2] == GS_YEAR_CODE and sn[3] == GS_MONTH_CODE


def get_prefix(sn: str) -> str:
    """Return the two-character prefix of a SN, upper-cased."""
    return sn.strip().upper()[:2]


def validate_part_sn(sn: str, part_name: str, expected_prefix: str) -> tuple:
    """
    Validate a part SN: full format check + prefix match.

    Returns (ok: bool, error_message: str).
    """
    ok, err = validate_sn(sn)
    if not ok:
        return False, err
    prefix = get_prefix(sn)
    exp = expected_prefix.strip().upper()
    if prefix != exp:
        return False, (
            f'Wrong part for {part_name}: '
            f'expected prefix "{exp}", got "{prefix}".'
        )
    return True, ''


def decode_sn(sn: str) -> dict:
    """
    Decode a valid SN into its components.
    Returns a dict with keys: prefix, year, month, number, is_golden_sample.
    Assumes validate_sn() already passed.
    """
    sn = sn.strip().upper()
    year_code  = sn[2]
    month_code = sn[3]
    is_gs = (year_code == GS_YEAR_CODE and month_code == GS_MONTH_CODE)
    return {
        'prefix':          sn[:2],
        'year':            _YEAR_MAP.get(year_code) if not is_gs else None,
        'month':           _MONTH_MAP.get(month_code) if not is_gs else None,
        'number':          int(sn[4:]),
        'is_golden_sample': is_gs,
    }
