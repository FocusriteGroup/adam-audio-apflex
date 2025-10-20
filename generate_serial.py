
"""
generate_serial.py

ADAM Audio Serial Number Generator
---------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-20

This script generates ADAM Audio serial numbers using a mandatory 2-letter product code as prefix.
It maintains a persistent counter in a file and encodes year/month/counter in the serial number.

Usage:
    python generate_serial.py -p IA
    python generate_serial.py -p IB --counter-file production_counter.txt
    python generate_serial.py -p XX --info
"""


import argparse
import os
import sys
from datetime import datetime

def read_counter(counter_file):
    """
    Read the current counter value from the specified file.
    If the file does not exist, create it with value 0.
    Args:
        counter_file (str): Path to the counter file.
    Returns:
        int: The current counter value.
    Exits on error.
    """
    try:
        if not os.path.exists(counter_file):
            # Create file with initial value 0 if it does not exist
            with open(counter_file, 'w', encoding='utf-8') as f:
                f.write('0')
            return 0
        # Read and parse the counter value
        with open(counter_file, 'r', encoding='utf-8') as f:
            counter = int(f.read().strip())
            return counter
    except (ValueError, IOError) as e:
        print(f"Error reading counter file: {e}", file=sys.stderr)
        sys.exit(1)

def write_counter(counter_file, counter):
    """
    Write the new counter value to the specified file.
    Args:
        counter_file (str): Path to the counter file.
        counter (int): New counter value to write.
    Exits on error.
    """
    try:
        with open(counter_file, 'w', encoding='utf-8') as f:
            f.write(str(counter))
    except IOError as e:
        print(f"Error writing counter file: {e}", file=sys.stderr)
        sys.exit(1)

def generate_serial_number(counter, product_code):
    """
    Generate an ADAM Audio serial number using a mandatory 2-letter product code as prefix.
    Format: [Prefix][Year][Month][Counter-5-digits]
    Example: IA51000001
    Args:
        counter (int): Serial counter value.
        product_code (str): 2-letter product code (prefix).
    Returns:
        str: Generated serial number.
    Raises:
        ValueError: If product_code is not a valid 2-letter string.
    """
    # Validate product_code
    if not (product_code and isinstance(product_code, str) and len(product_code) == 2 and product_code.isalpha()):
        raise ValueError("Product code must be a 2-letter string.")
    prefix = product_code.upper()

    # Get current date for year and month
    now = datetime.now()
    year_code = now.year % 10  # Last digit of year (2025 -> 5)

    # Month codes mapping
    month_codes = {
        1: '1',   # Jan
        2: '2',   # Feb
        3: '3',   # Mar
        4: '4',   # Apr
        5: '5',   # May
        6: '6',   # Jun
        7: '7',   # Jul
        8: '8',   # Aug
        9: '9',   # Sep
        10: 'A',  # Oct
        11: 'B',  # Nov
        12: 'C'   # Dec
    }
    month_code = month_codes[now.month]

    # Build the serial number string
    serial_number = f"{prefix}{year_code}{month_code}{counter:05d}"
    return serial_number

def main():
    """
    Main entry point for ADAM Audio serial number generator.
    Parses command-line arguments, manages counter, and prints serial number.
    """
    parser = argparse.ArgumentParser(
        description='ADAM Audio Serial Number Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -p IA                              # Uses 'counter.txt' as counter file
  %(prog)s -p IB -f production_counter.txt    # Uses specific counter file
  %(prog)s -p XX --counter-file /path/to/counter.txt
  %(prog)s -p IA --info                       # Show extra info
        """
    )

    parser.add_argument(
        '-f', '--counter-file',
        default='counter.txt',
        help='Path to counter file (default: counter.txt)'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Show extra information about the generated serial number'
    )

    parser.add_argument(
        '-p', '--product',
        type=str,
        required=True,
        help='Mandatory 2-letter product code to use as serial prefix (e.g. "IA")'
    )

    args = parser.parse_args()

    # Step 1: Read current counter value from file
    counter = read_counter(args.counter_file)

    # Step 2: Increment counter for new serial number
    new_counter = counter + 1

    # Step 3: Generate serial number using product code
    serial_number = generate_serial_number(new_counter, product_code=args.product)

    # Step 4: Output serial number to stdout
    print(serial_number)

    # Step 5: Optionally print extra info to stderr
    if args.info:
        prefix = serial_number[:2]
        year_code = serial_number[2]
        month_code = serial_number[3]
        counter_part = serial_number[4:]

        print(f"Prefix: {prefix}", file=sys.stderr)
        print(f"Year code: {year_code} (20{datetime.now().year % 10})", file=sys.stderr)
        print(f"Month code: {month_code} ({datetime.now().strftime('%b')})", file=sys.stderr)
        print(f"Counter: {counter_part} (#{new_counter})", file=sys.stderr)
        print(f"Counter file: {args.counter_file}", file=sys.stderr)

    # Step 6: Save new counter value to file
    write_counter(args.counter_file, new_counter)

if __name__ == '__main__':
    main()
