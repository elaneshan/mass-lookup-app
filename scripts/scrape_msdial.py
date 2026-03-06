"""
MS-DIAL Lipid Database Scraper
================================
Parses MS-DIAL lipid MSP library files.
Downloads from: http://prime.psc.riken.jp/compms/msdial/main.html

MS-DIAL provides several MSP files:
  - MSMS-Public-Neg-VS15.msp   (negative mode)
  - MSMS-Public-Pos-VS15.msp   (positive mode)
  - MassBank-All-Pos.msp
  - MassBank-All-Neg.msp

These are spectral libraries — each entry has a compound name, formula,
exact mass, InChIKey, SMILES, and MS/MS spectrum.

We extract the compound metadata (not the spectra) and add to compounds.db.

Download manually from:
    http://prime.psc.riken.jp/compms/msdial/main.html#MSP
Place in: data/raw/msdial/

Run on server:
    python scripts/scrape_msdial.py
    python scripts/scrape_msdial.py --file data/raw/msdial/MSMS-Public-Pos-VS15.msp
"""

import sqlite3
import re
import time
import argparse
import os
from pathlib import Path

DB_FILE  = "database/compounds.db"
DATA_DIR = Path("data/raw/msdial")
CHUNK    = 5_000

# Field name mappings — MS-DIAL MSP files use various field names
# NOTE: precursormz is stored separately and used to back-calculate neutral mass
FIELD_MAP = {
    'name'           : 'name',
    'precursormz'    : 'precursor_mz',   # adduct ion m/z — NOT neutral mass
    'precursortype'  : 'adduct',
    'formula'        : 'formula',
    'inchikey'       : 'inchikey',
    'smiles'         : 'smiles',
    'exactmass'      : 'exact_mass',     # true neutral mass when present
    'mw'             : 'exact_mass',
    'molecularweight': 'exact_mass',
}

# Adduct offsets for back-calculating neutral mass from precursor m/z
ADDUCT_OFFSETS = {
    '[m+h]+':      1.007276,
    '[m+na]+':     22.989218,
    '[m+k]+':      38.963158,
    '[m+nh4]+':    18.034374,
    '[m+h-h2o]+':  -17.002740 + 1.007276,
    '[m-h]-':      -1.007276,
    '[m+cl]-':     34.969402,
    '[m+fa-h]-':   44.998201,
    '[m-h2o-h]-':  -19.01839,
    '[m+hcoo]-':   44.998201,
}


def parse_msp(filepath):
    """
    Parse MSP file into list of compound dicts.
    MSP format: KEY: VALUE pairs, entries separated by blank lines.
    """
    compounds = []
    current   = {}

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()

            # Blank line = end of entry
            if not line:
                if current:
                    compounds.append(current)
                    current = {}
                continue

            # Skip spectrum lines (just numbers)
            if re.match(r'^\d+\s+\d+', line):
                continue

            # Parse KEY: VALUE
            if ':' in line:
                key, _, value = line.partition(':')
                key   = key.strip().lower().replace(' ', '').replace('_', '')
                value = value.strip()
                mapped = FIELD_MAP.get(key)
                if mapped:
                    current[mapped] = value
                elif key == 'num peaks' or key == 'numpeaks':
                    pass  # skip spectrum count
                elif 'name' in key and 'name' not in current:
                    current['name'] = value

    # Don't forget last entry
    if current:
        compounds.append(current)

    return compounds


def neutral_mass_from_precursor(precursor_mz, adduct_str):
    """Back-calculate neutral mass from adduct ion m/z."""
    if not precursor_mz or not adduct_str:
        return None
    key = adduct_str.strip().lower()
    offset = ADDUCT_OFFSETS.get(key)
    if offset is None:
        return None
    return precursor_mz - offset


def insert_compounds(conn, compounds, source_id_prefix='MSDIAL'):
    cursor   = conn.cursor()
    inserted = 0
    skipped  = 0
    batch    = []

    for i, c in enumerate(compounds):
        name     = c.get('name', '').strip() or None
        formula  = c.get('formula', '').strip() or None
        inchikey = c.get('inchikey', '').strip() or None
        smiles   = c.get('smiles', '').strip() or None
        adduct   = c.get('adduct', '').strip() or None

        # Prefer explicit exact_mass; fall back to back-calculated neutral mass
        mass = None
        mass_str = c.get('exact_mass', '').strip() if c.get('exact_mass') else ''
        if mass_str:
            try:
                mass = float(mass_str)
            except ValueError:
                pass

        if mass is None:
            prec_str = c.get('precursor_mz', '').strip() if c.get('precursor_mz') else ''
            if prec_str:
                try:
                    precursor_mz = float(prec_str)
                    mass = neutral_mass_from_precursor(precursor_mz, adduct)
                except ValueError:
                    pass

        if mass is None:
            skipped += 1
            continue

        # Skip out of metabolomics range
        if mass < 50 or mass > 2000:
            skipped += 1
            continue

        source_id    = inchikey or f"{source_id_prefix}_{i}"
        formula_norm = formula.strip().upper().replace(' ', '') if formula else None

        batch.append((
            'MS-DIAL', source_id, name,
            formula, mass, None, inchikey, formula_norm, smiles
        ))

        if len(batch) >= CHUNK:
            cursor.executemany('''
                INSERT OR IGNORE INTO compounds
                    (source_database, source_id, name, formula, exact_mass,
                     cas, inchikey, formula_normalized, smiles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            conn.commit()
            inserted += len(batch)
            batch = []
            print(f"  Inserted {inserted:,}...", end='\r')

    if batch:
        cursor.executemany('''
            INSERT OR IGNORE INTO compounds
                (source_database, source_id, name, formula, exact_mass,
                 cas, inchikey, formula_normalized, smiles)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
        conn.commit()
        inserted += len(batch)

    return inserted, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, default=None,
                        help='Path to specific .msp file (default: all files in data/raw/msdial/)')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)").fetchall()]
    if 'smiles' not in cols:
        print("ERROR: smiles column missing. Run migrate_add_smiles.py first.")
        conn.close()
        return

    # Find MSP files
    if args.file:
        msp_files = [Path(args.file)]
    else:
        msp_files = list(DATA_DIR.glob("*.msp")) + list(DATA_DIR.glob("*.MSP"))

    if not msp_files:
        print(f"No .msp files found in {DATA_DIR}")
        print("Download MS-DIAL MSP files from:")
        print("  http://prime.psc.riken.jp/compms/msdial/main.html#MSP")
        print(f"Place in: {DATA_DIR}/")
        conn.close()
        return

    total_inserted = 0
    start = time.time()

    for msp_file in msp_files:
        print(f"\nParsing: {msp_file.name}")
        compounds = parse_msp(msp_file)
        print(f"  Found {len(compounds):,} entries")
        inserted, skipped = insert_compounds(conn, compounds)
        print(f"  Inserted: {inserted:,}   Skipped: {skipped:,}")
        total_inserted += inserted

    elapsed = time.time() - start
    total   = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]

    print(f"\nMS-DIAL import complete in {elapsed:.0f}s")
    print(f"  Total inserted: {total_inserted:,}")
    print(f"  DB total:       {total:,}")

    conn.close()


if __name__ == "__main__":
    main()