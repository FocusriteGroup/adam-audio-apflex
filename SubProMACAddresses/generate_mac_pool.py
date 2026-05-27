"""
Generate a CSV file with fictitious (locally administered) MAC addresses for testing.

Locally administered MACs have the second-least-significant bit of the first octet set to 1,
e.g. prefix 02:xx:xx:xx:xx:xx — these will never collide with real OUI assignments.

Usage:
    python generate_mac_pool.py --count 100 --prefix 02:AB:CD --output mac_pool.csv
"""

import argparse
import csv
import random


def generate_mac_addresses(count: int, prefix: str, seed=None) -> list[str]:
    """Generate `count` unique MAC addresses with the given prefix.

    Args:
        count: Number of MAC addresses to generate.
        prefix: OUI prefix in colon-separated hex, e.g. "02:AB:CD".
                Must be exactly 3 octets (6 hex chars separated by colons).
        seed: Optional RNG seed for reproducibility.

    Returns:
        Sorted list of MAC address strings in AA:BB:CC:DD:EE:FF format.
    """
    prefix_parts = prefix.upper().split(":")
    if len(prefix_parts) != 3:
        raise ValueError(f"Prefix must be exactly 3 octets (e.g. '02:AB:CD'), got: {prefix!r}")
    for part in prefix_parts:
        if len(part) != 2 or not all(c in "0123456789ABCDEF" for c in part):
            raise ValueError(f"Invalid prefix octet: {part!r}")

    max_pool = 256 ** 3  # 16,777,216 combinations for 3 suffix octets
    if count > max_pool:
        raise ValueError(f"count={count} exceeds maximum for a 3-octet suffix ({max_pool})")

    rng = random.Random(seed)
    suffix_ints = rng.sample(range(max_pool), count)

    macs = []
    for val in suffix_ints:
        o4 = (val >> 16) & 0xFF
        o5 = (val >> 8) & 0xFF
        o6 = val & 0xFF
        mac = f"{prefix_parts[0]}:{prefix_parts[1]}:{prefix_parts[2]}:{o4:02X}:{o5:02X}:{o6:02X}"
        macs.append(mac)

    return sorted(macs)


def write_csv(macs: list[str], output_path: str) -> None:
    """Write MAC addresses to a CSV file with a header row."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["mac_address"])
        for mac in macs:
            writer.writerow([mac])
    print(f"Written {len(macs)} MAC addresses to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a CSV pool of fictitious MAC addresses.")
    parser.add_argument(
        "--count", type=int, default=100,
        help="Number of MAC addresses to generate (default: 100)"
    )
    parser.add_argument(
        "--prefix", default="02:AB:CD",
        help="3-octet OUI prefix in hex, e.g. '02:AB:CD' (default: '02:AB:CD'). "
             "Prefix 02:xx:xx denotes locally administered — safe for testing."
    )
    parser.add_argument(
        "--output", default="SubProMACAddresses/mac_pool.csv",
        help="Output CSV file path (default: SubProMACAddresses/mac_pool.csv)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Optional RNG seed for reproducible output"
    )
    args = parser.parse_args()

    macs = generate_mac_addresses(args.count, args.prefix, args.seed)
    write_csv(macs, args.output)


if __name__ == "__main__":
    main()
