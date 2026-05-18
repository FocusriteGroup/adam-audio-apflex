"""
fill_test_db.py  –  Vollständiger Systemtest der Matching-Pipeline.

Ablauf:
  1. Synthetische Frequenzgänge generieren (realistisch + variiert pro Treiber)
  2. Alle IA/IB-Treiber via MeasurementUpload in die DB schreiben
  3. Matching per Hungarian-Algorithmus ausführen (compute_pairs)
  4. Alle gematchten Paare als 'paired' bestätigen (confirm_pair)
  5. verify_system für jedes Paar aufrufen und Ergebnis reporten

Verwendung:
    python fill_test_db.py [--count N] [--digits D] [--csv CSV_PATH]
                           [--rmse-threshold F] [--db DB_PATH]

Beispiele:
    python fill_test_db.py --count 10
    python fill_test_db.py --count 20 --rmse-threshold 2.0
    python fill_test_db.py --count 5 --csv "C:\\Pfad\\zu\\datei.csv"
"""

import argparse
import logging
import os
import sys
import sqlite3
from datetime import datetime

import numpy as np

# Workstation-Module aus dem übergeordneten Repo-Root einbinden
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import MeasurementUpload, MeasurementParser
from app.matcher import compute_pairs
from app.database import init_db, get_matched_pairs, confirm_pair, get_frequency_vector, get_driver_levels, lookup_driver, DB_PATH as _DEFAULT_DB

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> logging.Logger:
    """Konfiguriert das Logging auf die Konsole.

    INFO  = normaler Ablauf
    DEBUG = Details (nur mit --verbose)
    WARNING/ERROR = Probleme
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)-7s] %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, stream=sys.stdout)

    # Externe Module (kivy, watchdog etc.) nicht auf DEBUG fluten
    for noisy in ("kivy", "watchdog", "PIL", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("systemtest")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CSV = (
    r"C:\Users\ThiloRode\OneDrive - Focusrite Group\Dokumente"
    r"\H715Drivers\Measurements\2026\5_11\2026_05_11_14_18_32.csv"
)
WORKSTATION_ID = "systemtest"


# ──────────────────────────────────────────────────────────────────────────────
# Synthetische Frequenzgänge
# ──────────────────────────────────────────────────────────────────────────────

def _base_curve(freqs: np.ndarray) -> np.ndarray:
    """Erzeugt eine realistische Kopfhörer-ähnliche Basiskurve."""
    log_f = np.log10(np.clip(freqs, 20, 20000))
    log_min, log_max = np.log10(20), np.log10(20000)
    t = (log_f - log_min) / (log_max - log_min)  # 0..1

    # Grobe Kurve: leichter Anstieg im Mitten-Hochtonbereich, Abfall zu den Extremen
    curve = (
        90.0
        - 8.0 * (t - 0.55) ** 2 * 30      # Schale um ~3 kHz
        - 3.0 * np.exp(-((t - 0.0) / 0.1) ** 2)  # Tiefton-Abfall
        - 4.0 * np.exp(-((t - 1.0) / 0.12) ** 2)  # Hochton-Abfall
    )
    return curve


def make_pair_signature(
    freqs: np.ndarray,
    pair_index: int,
    seed: int,
    pair_spread_db: float = 3.0,
) -> tuple[float, np.ndarray]:
    """Erzeugt den paar-spezifischen Offset + spektrale Form.

    Beide Treiber eines Paares (IA und IB) teilen exakt dieselbe Signatur,
    damit ihr RMSE nur durch within_noise bestimmt wird.
    """
    pair_rng = np.random.default_rng(seed * 10000 + pair_index)
    pair_offset = pair_rng.uniform(-pair_spread_db / 2, pair_spread_db / 2)
    # Sanfter Random-Walk mit begrenzter Amplitude
    raw = pair_rng.normal(0, 0.02, len(freqs))   # kleinere Schritte → RMSE bleibt klein
    pair_shape = np.cumsum(raw)
    pair_shape -= pair_shape.mean()
    return pair_offset, pair_shape


def generate_synthetic_response(
    freqs: np.ndarray,
    pair_offset: float,
    pair_shape: np.ndarray,
    rng: np.random.Generator,
    within_pair_noise_db: float = 0.15,
) -> list[float]:
    """Erzeugt einen synthetischen Frequenzgang für einen einzelnen Treiber.

    pair_offset und pair_shape sind für IA und IB eines Paares identisch;
    nur within_noise unterscheidet die beiden Treiber.
    within_pair_noise_db muss deutlich < RMSE-Threshold liegen.
    """
    base = _base_curve(freqs)
    within_noise = rng.normal(0, within_pair_noise_db / 3, len(freqs))
    levels = base + pair_offset + pair_shape + within_noise
    return levels.tolist()


def build_upload_data(
    serial: str,
    freqs: list[float],
    levels: list[float],
) -> dict:
    """Baut ein upload_data-Dict wie MeasurementUpload.prepare_upload es erzeugen würde."""
    return {
        "workstation_id": WORKSTATION_ID,
        "serial_number": serial,
        "timestamp": datetime.now().isoformat(),
        "measurement_data": {
            "channels": {
                "Ch1": {
                    "frequencies": freqs,
                    "levels": levels,
                    "unit": "dBSPL",
                    "data_points": len(levels),
                }
            },
            "data_points": len(levels),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# verify_system (direkt ohne argparse, da kein tkinter in Tests)
# ──────────────────────────────────────────────────────────────────────────────

def verify_system(db_path: str, system_sn: str, sn1: str, sn2: str, log: logging.Logger) -> bool:
    """Vereinfachte verify_system-Logik analog zu AdamWorkstation.verify_system."""
    log.debug("verify_system: db=%s  system=%s  sn1=%s  sn2=%s", db_path, system_sn, sn1, sn2)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("""
        CREATE TABLE IF NOT EXISTS system_builds (
            system_serial TEXT PRIMARY KEY,
            module_1 TEXT NOT NULL,
            module_2 TEXT NOT NULL,
            built_at TEXT NOT NULL
        )
    """)
    con.commit()
    cur = con.cursor()

    cur.execute("SELECT status, partner FROM drivers WHERE serial = ?", (sn1,))
    row1 = cur.fetchone()
    cur.execute("SELECT status, partner FROM drivers WHERE serial = ?", (sn2,))
    row2 = cur.fetchone()

    if row1 is None:
        log.error("verify_system FAIL: Modul %s nicht in DB gefunden", sn1)
        con.close()
        return False
    if row2 is None:
        log.error("verify_system FAIL: Modul %s nicht in DB gefunden", sn2)
        con.close()
        return False

    status1, partner1 = row1
    status2, partner2 = row2
    log.debug("  %s → status=%s  partner=%s", sn1, status1, partner1)
    log.debug("  %s → status=%s  partner=%s", sn2, status2, partner2)

    if status1 not in {"matched", "paired"}:
        log.error("verify_system FAIL: %s hat ungültigen Status '%s' (erwartet matched/paired)", sn1, status1)
        con.close()
        return False
    if status2 not in {"matched", "paired"}:
        log.error("verify_system FAIL: %s hat ungültigen Status '%s' (erwartet matched/paired)", sn2, status2)
        con.close()
        return False

    if partner1 != sn2:
        log.error("verify_system FAIL: Partner von %s ist '%s', erwartet '%s'", sn1, partner1, sn2)
        con.close()
        return False
    if partner2 != sn1:
        log.error("verify_system FAIL: Partner von %s ist '%s', erwartet '%s'", sn2, partner2, sn1)
        con.close()
        return False

    now = datetime.now().isoformat()
    if status1 == "matched" or status2 == "matched":
        log.debug("  Auto-pairing %s ↔ %s", sn1, sn2)
        cur.execute(
            "UPDATE drivers SET status='paired', matched_at=? WHERE serial IN (?, ?)",
            (now, sn1, sn2),
        )

    cur.execute(
        "DELETE FROM system_builds WHERE module_1 IN (?, ?) OR module_2 IN (?, ?)",
        (sn1, sn2, sn1, sn2),
    )
    cur.execute(
        "INSERT OR REPLACE INTO system_builds (system_serial, module_1, module_2, built_at) "
        "VALUES (?, ?, ?, ?)",
        (system_sn, sn1, sn2, now),
    )
    con.commit()
    con.close()
    log.debug("  system_builds Eintrag für %s geschrieben", system_sn)
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Hauptprogramm
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Vollständiger Matching-Systemtest")
    parser.add_argument("--count", type=int, default=10,
                        help="Anzahl Treiber-Paare (Standard: 10)")
    parser.add_argument("--digits", type=int, default=4,
                        help="Ziffernbreite der Seriennummer (Standard: 4 → IA0001)")
    parser.add_argument("--csv", default=None,
                        help="Echte CSV statt synthetischer Daten verwenden")
    parser.add_argument("--rmse-threshold", type=float, default=1.0,
                        help="RMSE-Schwelle für den Matcher in dB (Standard: 1.0)")
    parser.add_argument("--db", default=_DEFAULT_DB,
                        help=f"Pfad zur SQLite-DB (Standard: {_DEFAULT_DB})")
    parser.add_argument("--seed", type=int, default=42,
                        help="Zufalls-Seed für reproduzierbare Ergebnisse (Standard: 42)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="DEBUG-Ausgaben aktivieren")
    args = parser.parse_args()

    log = _setup_logging(args.verbose)
    rng = np.random.default_rng(args.seed)

    errors: list[str] = []   # alle Fehler sammeln → Gesamtbewertung am Ende

    log.info("=" * 60)
    log.info("Matching-Systemtest gestartet")
    log.info("  Paare      : %d", args.count)
    log.info("  Modus      : %s", f"Echte CSV: {args.csv}" if args.csv else "Synthetische Frequenzgänge")
    log.info("  RMSE-Limit : %.2f dB", args.rmse_threshold)
    log.info("  DB         : %s", args.db)
    log.info("  Seed       : %d", args.seed)
    log.info("=" * 60)

    # ── Schritt 1: DB initialisieren ──────────────────────────────────────────
    log.info("── Schritt 1: DB initialisieren")
    try:
        init_db()
        log.info("   DB initialisiert: %s", args.db)
        if not os.path.isfile(args.db):
            msg = f"DB-Datei nicht gefunden nach init_db(): {args.db}"
            log.error("   %s", msg)
            errors.append(msg)
        else:
            log.debug("   DB-Datei existiert (%d Bytes)", os.path.getsize(args.db))
    except Exception as exc:
        msg = f"init_db() Ausnahme: {exc}"
        log.error("   %s", msg)
        errors.append(msg)

    # ── Schritt 2: Frequenzbasis vorbereiten ──────────────────────────────────
    log.info("── Schritt 2: Frequenzgänge vorbereiten")
    base_freqs: list[float]
    base_levels: list[float] | None = None

    if args.csv:
        if not os.path.isfile(args.csv):
            msg = f"CSV-Datei nicht gefunden: {args.csv}"
            log.error("   %s", msg)
            errors.append(msg)
            sys.exit(1)
        try:
            parsed = MeasurementParser.parse_measurement_csv(args.csv)
            ch1 = parsed["channels"].get("Ch1")
            if ch1 is None:
                raise ValueError("Kein Kanal 'Ch1' in der CSV")
            base_freqs = ch1["frequencies"]
            base_levels = ch1["levels"]
            log.info("   CSV gelesen: %d Punkte (%.0f – %.0f Hz), Einheit: %s",
                     len(base_freqs), base_freqs[0], base_freqs[-1], ch1.get("unit", "?"))
            log.debug("   Pegel-Bereich: %.2f – %.2f dB", min(base_levels), max(base_levels))
        except Exception as exc:
            msg = f"CSV-Parsing fehlgeschlagen: {exc}"
            log.error("   %s", msg)
            errors.append(msg)
            sys.exit(1)
    else:
        base_freqs = list(np.logspace(np.log10(20), np.log10(20000), 500))
        log.info("   Synthetisch: %d Punkte (20 – 20000 Hz)", len(base_freqs))

    # ── Schritt 3: Treiber einfügen ───────────────────────────────────────────
    log.info("── Schritt 3: Treiber in DB schreiben")
    inserted, skipped = 0, 0
    expected_serials: list[str] = []

    for i in range(1, args.count + 1):
        num = str(i).zfill(args.digits)
        for j, prefix in enumerate(("IA", "IB")):
            serial = f"{prefix}{num}"
            expected_serials.append(serial)

            if args.csv:
                levels = base_levels
            else:
                if j == 0:  # einmal pro Paar berechnen, IA und IB teilen sig
                    pair_offset, pair_shape = make_pair_signature(
                        np.array(base_freqs), pair_index=i, seed=args.seed
                    )
                levels = generate_synthetic_response(
                    np.array(base_freqs),
                    pair_offset=pair_offset,
                    pair_shape=pair_shape,
                    rng=rng,
                )
            log.debug("   Schreibe %s: %d Punkte, Pegel %.2f – %.2f dB",
                      serial, len(levels), min(levels), max(levels))

            upload_data = build_upload_data(serial, base_freqs, levels)
            try:
                result = MeasurementUpload.write_measurement_local_db(upload_data, serial, args.db)
            except Exception as exc:
                msg = f"{serial}: write_measurement_local_db Ausnahme: {exc}"
                log.error("   FEHLER  %s", msg)
                errors.append(msg)
                skipped += 1
                continue

            if result.get("status") == "success":
                log.info("   OK      %s", serial)
                inserted += 1
            else:
                err = result.get("error", "unbekannt")
                if err == "duplicate":
                    log.warning("   SKIP    %s  (bereits vorhanden)", serial)
                else:
                    msg = f"{serial}: DB-Schreiben fehlgeschlagen – {err}"
                    log.error("   FEHLER  %s", msg)
                    errors.append(msg)
                skipped += 1

    log.info("   → Eingefügt: %d, übersprungen/Fehler: %d", inserted, skipped)
    if inserted != args.count * 2:
        msg = f"Erwartet {args.count * 2} Inserts, aber nur {inserted} erfolgreich"
        log.warning("   WARNUNG: %s", msg)
        errors.append(msg)

    # ── Schritt 3b: DB-Inhalte verifizieren ──────────────────────────────────
    log.info("── Schritt 3b: DB-Inhalte verifizieren")

    # Frequenzvektor prüfen
    fv = get_frequency_vector()
    if fv is None:
        msg = "Frequenzvektor nicht in DB gespeichert"
        log.error("   FEHLER: %s", msg)
        errors.append(msg)
    else:
        if len(fv) != len(base_freqs):
            msg = f"Frequenzvektor-Länge: DB={len(fv)}, erwartet={len(base_freqs)}"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
        elif abs(fv[0] - base_freqs[0]) > 0.01 or abs(fv[-1] - base_freqs[-1]) > 0.01:
            msg = f"Frequenzvektor-Werte weichen ab: DB [{fv[0]:.2f}..{fv[-1]:.2f}], erwartet [{base_freqs[0]:.2f}..{base_freqs[-1]:.2f}]"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
        else:
            log.info("   OK      Frequenzvektor: %d Punkte (%.1f – %.1f Hz)", len(fv), fv[0], fv[-1])

    # Jeden Treiber einzeln prüfen
    verify_errors = 0
    for i in range(1, args.count + 1):
        num = str(i).zfill(args.digits)
        for j, prefix in enumerate(("IA", "IB")):
            serial = f"{prefix}{num}"
            expected_side = "left" if prefix == "IA" else "right"

            # 1. lookup_driver: existiert + korrekte Seite + Status unmatched
            driver = lookup_driver(serial)
            if driver is None:
                msg = f"{serial}: nicht in DB gefunden"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
                verify_errors += 1
                continue
            if driver["side"] != expected_side:
                msg = f"{serial}: side='{driver['side']}', erwartet '{expected_side}'"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
                verify_errors += 1
            if driver["status"] != "unmatched":
                msg = f"{serial}: status='{driver['status']}', erwartet 'unmatched'"
                log.warning("   WARNUNG: %s", msg)
                # kein hard error – könnte bereits in der DB gewesen sein
            log.debug("   CHECK   %s  side=%s  status=%s", serial, driver["side"], driver["status"])

            # 2. get_driver_levels: Pegel zurücklesen und Länge + Bereich prüfen
            freqs_db, levels_db = get_driver_levels(serial)
            if freqs_db is None or levels_db is None:
                msg = f"{serial}: Pegel nicht aus DB lesbar"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
                verify_errors += 1
                continue
            if len(levels_db) != len(base_freqs):
                msg = f"{serial}: Pegellänge DB={len(levels_db)}, erwartet={len(base_freqs)}"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
                verify_errors += 1
            elif any(not np.isfinite(v) for v in levels_db):
                msg = f"{serial}: Pegel enthalten NaN/Inf-Werte"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
                verify_errors += 1
            elif (max(levels_db) - min(levels_db)) > 200:
                msg = f"{serial}: Pegelspanne {max(levels_db)-min(levels_db):.1f} dB erscheint unrealistisch groß (> 200 dB)"
                log.warning("   WARNUNG: %s", msg)
                errors.append(msg)
            else:
                log.debug("   CHECK   %s  levels: %d Punkte, %.1f – %.1f dB (Spanne %.1f dB)",
                          serial, len(levels_db), min(levels_db), max(levels_db),
                          max(levels_db) - min(levels_db))

    if verify_errors == 0:
        log.info("   OK      Alle %d Treiber korrekt in DB geschrieben", inserted)
    else:
        log.error("   → %d Verifikationsfehler", verify_errors)


    log.info("── Schritt 4: Matching (Hungarian-Algorithmus, RMSE ≤ %.2f dB)", args.rmse_threshold)
    try:
        n_pairs = compute_pairs(
            rmse_threshold=args.rmse_threshold,
            freq_min=200,
            freq_max=8000,
        )
        log.info("   → %d Paar(e) gefunden (erwartet: %d)", n_pairs, args.count)
        if n_pairs != args.count:
            msg = f"Matching: {n_pairs} Paare gefunden, erwartet {args.count}"
            log.warning("   WARNUNG: %s", msg)
            errors.append(msg)
    except Exception as exc:
        msg = f"compute_pairs() Ausnahme: {exc}"
        log.error("   FEHLER: %s", msg)
        errors.append(msg)
        n_pairs = 0

    # ── Schritt 5: Pairs bestätigen ───────────────────────────────────────────
    log.info("── Schritt 5: Pairs bestätigen (confirm_pair)")
    try:
        matched = get_matched_pairs()
        log.debug("   get_matched_pairs() lieferte %d Einträge", len(matched))
    except Exception as exc:
        msg = f"get_matched_pairs() Ausnahme: {exc}"
        log.error("   FEHLER: %s", msg)
        errors.append(msg)
        matched = []

    confirmed, failed_confirm = 0, 0
    for left_sn, right_sn in matched:
        log.debug("   confirm_pair(%s, %s)", left_sn, right_sn)
        try:
            ok = confirm_pair(left_sn, right_sn)
        except Exception as exc:
            msg = f"confirm_pair({left_sn}, {right_sn}) Ausnahme: {exc}"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
            failed_confirm += 1
            continue

        if ok:
            log.info("   OK      %s ↔ %s", left_sn, right_sn)
            confirmed += 1
        else:
            msg = f"confirm_pair fehlgeschlagen: {left_sn} ↔ {right_sn}"
            log.error("   FEHLER  %s", msg)
            errors.append(msg)
            failed_confirm += 1

    log.info("   → Bestätigt: %d, fehlgeschlagen: %d", confirmed, failed_confirm)

    # ── Schritt 6: verify_system ──────────────────────────────────────────────
    log.info("── Schritt 6: verify_system")
    verified, failed_verify = 0, 0
    for i, (left_sn, right_sn) in enumerate(matched, start=1):
        system_sn = f"SYS{str(i).zfill(args.digits)}"
        try:
            ok = verify_system(args.db, system_sn, left_sn, right_sn, log)
        except Exception as exc:
            msg = f"verify_system({system_sn}) Ausnahme: {exc}"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
            failed_verify += 1
            continue

        if ok:
            log.info("   OK      %s  (%s + %s)", system_sn, left_sn, right_sn)
            verified += 1
        else:
            msg = f"verify_system fehlgeschlagen: {system_sn} ({left_sn} + {right_sn})"
            log.error("   FEHLER  %s", msg)
            errors.append(msg)
            failed_verify += 1

    log.info("   → Verifiziert: %d, fehlgeschlagen: %d", verified, failed_verify)

    # ── Schritt 6b: system_builds-Einträge in DB prüfen ─────────────────────
    log.info("── Schritt 6b: system_builds-Einträge in DB prüfen")
    try:
        con = sqlite3.connect(args.db)
        cur = con.cursor()
        cur.execute("SELECT system_serial, module_1, module_2, built_at FROM system_builds ORDER BY system_serial")
        rows = cur.fetchall()
        con.close()
        log.info("   system_builds enthält %d Einträge (erwartet: %d)", len(rows), verified)
        if len(rows) != verified:
            msg = f"system_builds: {len(rows)} Einträge, erwartet {verified}"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
        for sys_sn, mod1, mod2, built_at in rows:
            # Prüfen ob beide Module als 'paired' in drivers stehen
            con2 = sqlite3.connect(args.db)
            cur2 = con2.cursor()
            cur2.execute("SELECT status FROM drivers WHERE serial = ?", (mod1,))
            r1 = cur2.fetchone()
            cur2.execute("SELECT status FROM drivers WHERE serial = ?", (mod2,))
            r2 = cur2.fetchone()
            con2.close()
            s1 = r1[0] if r1 else "NICHT GEFUNDEN"
            s2 = r2[0] if r2 else "NICHT GEFUNDEN"
            if s1 == "paired" and s2 == "paired":
                log.info("   OK      %s → %s (%s) + %s (%s)  gebaut: %s",
                         sys_sn, mod1, s1, mod2, s2, built_at[:19])
            else:
                msg = f"{sys_sn}: {mod1} status='{s1}', {mod2} status='{s2}' – erwartet jeweils 'paired'"
                log.error("   FEHLER: %s", msg)
                errors.append(msg)
    except Exception as exc:
        msg = f"system_builds Prüfung Ausnahme: {exc}"
        log.error("   FEHLER: %s", msg)
        errors.append(msg)

    # ── Schritt 6c: Negativtests – falsche Paare müssen abgelehnt werden ─────
    log.info("── Schritt 6c: Negativtests (verify_system muss falsche Paare ablehnen)")

    # Baue eine Liste aller bestätigten Paare als (left, right)-Tupel
    paired_list = [(l, r) for l, r in matched]
    negative_cases: list[tuple[str, str, str]] = []  # (system_sn, sn1, sn2)

    if len(paired_list) >= 2:
        # Fall 1: zwei IA-Module (gleiches Präfix → kein gültiges Paar)
        ia_0 = paired_list[0][0]
        ia_1 = paired_list[1][0]
        negative_cases.append(("NEG_SAME_SIDE", ia_0, ia_1))

        # Fall 2: vertauschtes Paar – IA aus Paar 0, IB aus Paar 1
        ia_0 = paired_list[0][0]
        ib_1 = paired_list[1][1]
        negative_cases.append(("NEG_WRONG_PARTNER", ia_0, ib_1))

    if len(paired_list) >= 1:
        # Fall 3: Modul, das nicht in der DB existiert
        ia_real = paired_list[0][0]
        negative_cases.append(("NEG_UNKNOWN_MODULE", ia_real, "XX9999"))

        # Fall 4: System-SN bereits vergeben, aber mit falschem Paar → muss ablehnen
        # (IA und IB aus verschiedenen Paaren)
        if len(paired_list) >= 2:
            ia_wrong = paired_list[0][0]   # schon mit ib_0 paired
            ib_wrong = paired_list[1][1]   # schon mit ia_1 paired
            negative_cases.append(("NEG_CROSS_PAIR", ia_wrong, ib_wrong))

    neg_passed = 0
    neg_failed = 0
    for sys_sn, sn1, sn2 in negative_cases:
        try:
            result = verify_system(args.db, sys_sn, sn1, sn2, log)
        except Exception as exc:
            msg = f"Negativtest {sys_sn} warf Ausnahme statt False: {exc}"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
            neg_failed += 1
            continue

        if result is False:
            log.info("   OK (abgelehnt)  %s → verify_system(%s, %s) = False  ✓", sys_sn, sn1, sn2)
            neg_passed += 1
        else:
            msg = f"Negativtest NICHT abgelehnt: {sys_sn} verify_system({sn1}, {sn2}) gab True zurück"
            log.error("   FEHLER: %s", msg)
            errors.append(msg)
            neg_failed += 1

    log.info("   → Negativtests bestanden: %d / %d", neg_passed, len(negative_cases))

    all_ok = (
        not errors
        and n_pairs == args.count
        and confirmed == args.count
        and verified == args.count
        and neg_failed == 0
    )

    log.info("=" * 60)
    log.info("Zusammenfassung")
    log.info("  Treiber eingefügt  : %d / %d", inserted, args.count * 2)
    log.info("  Pairs gefunden     : %d / %d", n_pairs, args.count)
    log.info("  Pairs bestätigt    : %d / %d", confirmed, args.count)
    log.info("  Systems verifiziert: %d / %d", verified, args.count)
    log.info("  Negativtests       : %d / %d", neg_passed, len(negative_cases))
    if errors:
        log.info("  Fehler / Warnungen :")
        for e in errors:
            log.error("    ✗  %s", e)
    log.info("  Ergebnis: %s", "PASS ✓" if all_ok else "FEHLER ✗")
    log.info("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()


