# Filter Reference by Limits Feature

## Übersicht

Das neue Feature `filter_reference_by_limits` ermöglicht es, eine Referenzmessung basierend auf den Frequenzbereichen einer Limits-Datei zu filtern. Dies ist nützlich, um Referenzen auf die tatsächlich getesteten Frequenzbereiche zu beschränken.

## Funktionalität

### Hauptmerkmale

1. **Automatische Frequenzbereich-Erkennung**: Das Feature identifiziert automatisch die Frequenzbereiche aus der Limits-Datei
2. **Lücken-Erkennung**: Lücken zwischen Frequenzbereichen werden automatisch erkannt (Schwellenwert: Frequenzverhältnis > 2.0)
3. **Stereo/Mono-Unterstützung**: Funktioniert sowohl mit Stereo- als auch Mono-Referenzen
4. **Limits sind immer Mono**: Die Limits-Dateien sind immer im Mono-Format
5. **Automatische Interpolation**: Wenn keine Referenzfrequenzen im Limits-Bereich vorhanden sind, werden Werte logarithmisch-linear interpoliert

### Verwendung

#### Als Python-Funktion

```python
from analysis.csv_processing import filter_reference_by_limits

output_path = filter_reference_by_limits(
    reference_path="path/to/reference.csv",
    limits_path="path/to/limits.csv",
    output_filename="filtered_reference.csv",  # Optional
    output_dir="path/to/output"  # Optional
)
```

#### Als CLI-Command

```bash
python adam_workstation.py filter_reference_by_limits <reference_path> <limits_path> [--output-filename <name>] [--output-dir <dir>]
```

**Beispiel:**
```bash
python adam_workstation.py filter_reference_by_limits ^
    "DefaultReferences\GoldenSample\RMS.csv" ^
    "DefaultReferences\GoldenSample\Limits\RMS.csv" ^
    --output-filename "RMS_filtered.csv"
```

### Funktionsweise

1. **Limits einlesen**: Die Funktion liest die Limits-CSV und extrahiert alle Frequenzwerte
2. **Bereiche identifizieren**: Durch Analyse der Frequenzabstände werden zusammenhängende Bereiche identifiziert
   - Ein Bereich endet, wenn das Verhältnis zwischen zwei aufeinanderfolgenden Frequenzen > 2.0 ist
3. **Referenz filtern**: Die Referenz-CSV wird eingelesen und nur Frequenzen behalten, die innerhalb der identifizierten Bereiche liegen
4. **Interpolation (falls nötig)**: Wenn keine Referenzfrequenzen im Limits-Bereich gefunden werden:
   - Logarithmisch-lineare Interpolation wird angewendet
   - Frequenzen werden auf logarithmischer Skala interpoliert
   - dB-Werte werden linear interpoliert
   - Extrapolation mit Randwerten für Frequenzen außerhalb des Referenzbereichs
5. **Ausgabe schreiben**: Eine neue CSV-Datei mit den gefilterten/interpolierten Daten wird erstellt

### Beispiel

**Limits-Datei** (RMS.csv):
```
Hz,dB
20,3
300,3
300,4.5
700,4.5
700,2
2000,2
2000,4.5
8000,4.5
```

**Referenz-Datei** (test_reference.csv):
```
Hz,dBSPL,Hz,dBSPL
20,95,20,95
50,96,50,96
...
8000,113,8000,113
10000,114,10000,114
20000,116,20000,116
```

**Gefilterte Referenz** (test_reference_filtered.csv):
```
Hz,dBSPL,Hz,dBSPL
20,95,20,95
300,99,300,99
700,103,700,103
2000,107,2000,107
8000,113,8000,113
```

Die gefilterte Referenz enthält nur Frequenzen innerhalb des Bereichs 20-8000 Hz (dem Bereich der Limits).

### Beispiel 2: Interpolation bei fehlenden Frequenzen

**Limits-Datei** (RMS.csv):
```
Hz,dB
20,3
300,3
700,2
2000,4.5
8000,4.5
```

**Sparse Referenz-Datei** (sparse_reference.csv):
```
Hz,dBSPL,Hz,dBSPL
10,90,10,90
25000,120,25000,120
```

**Interpolierte Referenz** (sparse_reference_filtered.csv):
```
Hz,dBSPL,Hz,dBSPL
20.0,92.66,20.0,92.66
300.0,103.04,300.0,103.04
700.0,106.29,700.0,106.29
2000.0,110.32,2000.0,110.32
8000.0,115.63,8000.0,115.63
```

Die Werte wurden logarithmisch-linear zwischen 10 Hz (90 dBSPL) und 25000 Hz (120 dBSPL) interpoliert.

### Parameter

- `reference_path` (str): Pfad zur Referenzmessung (Stereo oder Mono)
- `limits_path` (str): Pfad zur Limits-Datei (immer Mono)
- `output_filename` (str, optional): Name der Ausgabedatei (Standard: `<reference_name>_filtered.csv`)
- `output_dir` (str, optional): Ausgabeverzeichnis (Standard: Verzeichnis der Referenzdatei)

### Fehlerbehandlung

Die Funktion wirft Exceptions in folgenden Fällen:
- `FileNotFoundError`: Wenn eine der Eingabedateien nicht existiert
- `ValueError`: Wenn das CSV-Format ungültig ist oder keine Frequenzen im definierten Bereich gefunden werden

### Integration

Das Feature ist vollständig in die bestehende Workstation-Architektur integriert:
- **Modul**: `analysis/csv_processing.py`
- **CLI-Parser**: `cli/workstation_parser.py`
- **Workstation-Handler**: `adam_workstation.py`

## Technische Details

### Lücken-Erkennung

Die Lücken-Erkennung basiert auf dem Verhältnis zwischen aufeinanderfolgenden Frequenzen:

```python
if freq_curr / freq_prev > 2.0:
    # Lücke erkannt - neuer Bereich beginnt
```

Dieser Schwellenwert von 2.0 funktioniert gut für typische Audio-Frequenz-Abstände und ermöglicht eine zuverlässige Erkennung von Lücken.

### Interpolationsmethode

Wenn keine Referenzfrequenzen im Limits-Bereich gefunden werden, kommt logarithmisch-lineare Interpolation zum Einsatz:

**Warum logarithmisch-linear?**
- Frequenzen werden auf logarithmischer Skala betrachtet (so wie das menschliche Gehör)
- dB-Werte werden linear interpoliert (physikalisch korrekt)
- Verwendet `numpy.interp` für schnelle Berechnung

**Algorithmus:**
```python
log_ref_freq = np.log10(reference_frequencies)
log_target_freq = np.log10(target_frequencies)
interpolated_db = np.interp(log_target_freq, log_ref_freq, db_values)
```

**Extrapolation:** Bei Frequenzen außerhalb des Referenzbereichs werden automatisch die Randwerte verwendet (konstante Extrapolation).

**Voraussetzungen:** Benötigt numpy (wird automatisch mit requirements.txt installiert)

### CSV-Format

Das Feature unterstützt das Standard-AP-CSV-Format mit 4 Header-Zeilen:
1. Messungsname
2. Kanal-Beschreibungen
3. X/Y-Rollen
4. Einheiten (Hz, dBSPL, etc.)

## Changelog

- **2026-05-20 v2**: Interpolationsfunktion hinzugefügt
  - Logarithmisch-lineare Interpolation bei fehlenden Frequenzen
  - Automatische Erkennung, ob Filterung oder Interpolation benötigt wird
  - Unterstützung für Stereo und Mono bei Interpolation
  
- **2026-05-20 v1**: Initiale Implementierung
  - Grundlegende Filterfunktionalität
  - Automatische Lücken-Erkennung
  - CLI-Integration
  - Stereo/Mono-Unterstützung
