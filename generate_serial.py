#!/usr/bin/env python3
# filepath: generate_serial.py

import argparse
import random
import os
import sys
from datetime import datetime

def read_counter(counter_file):
    """Liest den Zählerstand aus der Datei"""
    try:
        if not os.path.exists(counter_file):
            # Erstelle Datei mit Startwert 0 falls sie nicht existiert
            with open(counter_file, 'w') as f:
                f.write('0')
            return 0
        
        with open(counter_file, 'r') as f:
            counter = int(f.read().strip())
            return counter
    except (ValueError, IOError) as e:
        print(f"Fehler beim Lesen der Zählerdatei: {e}", file=sys.stderr)
        sys.exit(1)

def write_counter(counter_file, counter):
    """Schreibt den neuen Zählerstand in die Datei"""
    try:
        with open(counter_file, 'w') as f:
            f.write(str(counter))
    except IOError as e:
        print(f"Fehler beim Schreiben der Zählerdatei: {e}", file=sys.stderr)
        sys.exit(1)

def generate_serial_number(counter):
    """Generiert eine Seriennummer nach ADAM Audio Schema"""
    
    # Zufällige Auswahl zwischen IA und IB für die ersten beiden Ziffern
    prefix_options = ['IA', 'IB']
    prefix = random.choice(prefix_options)
    
    # Aktuelle Zeit für Jahr und Monat
    now = datetime.now()
    year_code = now.year % 10  # Letzte Ziffer des Jahres (2025 -> 5)
    
    # Monat-Codes basierend auf der Tabelle im Bild
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
    
    # Format: [Prefix][Year][Month][Counter-5-stellig]
    # Beispiel: IA51000001 oder IB51000001
    serial_number = f"{prefix}{year_code}{month_code}{counter:05d}"
    
    return serial_number

def main():
    parser = argparse.ArgumentParser(
        description='ADAM Audio Seriennummer Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s                              # Verwendet 'counter.txt' als Zählerdatei
  %(prog)s -f production_counter.txt    # Verwendet spezifische Zählerdatei
  %(prog)s --counter-file /path/to/counter.txt
        """
    )
    
    parser.add_argument(
        '-f', '--counter-file',
        default='counter.txt',
        help='Pfad zur Zählerdatei (Standard: counter.txt)'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Zeigt zusätzliche Informationen zur generierten Seriennummer'
    )
    
    args = parser.parse_args()
    
    # Zähler lesen
    counter = read_counter(args.counter_file)
    
    # Neuen Zählerstand berechnen (erhöhen)
    new_counter = counter + 1
    
    # Seriennummer generieren
    serial_number = generate_serial_number(new_counter)
    
    # Seriennummer ausgeben
    print(serial_number)
    
    # Zusätzliche Informationen falls gewünscht
    if args.info:
        prefix = serial_number[:2]  # Immer die ersten 2 Zeichen (IA oder IB)
        year_code = serial_number[2]
        month_code = serial_number[3]
        counter_part = serial_number[4:]
        
        print(f"Prefix: {prefix}", file=sys.stderr)
        print(f"Jahr-Code: {year_code} (20{datetime.now().year % 10})", file=sys.stderr)
        print(f"Monat-Code: {month_code} ({datetime.now().strftime('%b')})", file=sys.stderr)
        print(f"Zähler: {counter_part} (#{new_counter})", file=sys.stderr)
        print(f"Zählerdatei: {args.counter_file}", file=sys.stderr)
    
    # Neuen Zählerstand speichern
    write_counter(args.counter_file, new_counter)

if __name__ == '__main__':
    main()