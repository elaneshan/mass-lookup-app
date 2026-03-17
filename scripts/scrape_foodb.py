"""
FooDB Scraper
=============
Downloads and parses the FooDB CSV dataset.
FooDB covers food-related compounds including flavonoids, lipids,
amino acids, vitamins, and other food metabolites.

Source: https://foodb.ca/downloads
File:   https://foodb.ca/public/system/downloads/foodb_2020_4_7_csv.tar.gz

Run on server:
    python scripts/scrape_foodb.py
    python scripts/scrape_foodb.py --limit 5000   # test run
"""

import sqlite3
import requests
import tarfile
import csv
import io
import time
import argparse
from pathlib import Path

DB_FILE   = "database/compounds.db"
DATA_DIR  = Path("data/raw/foodb")
FOODB_URL = "https://foodb.ca/public/system/downloads/foodb_2020_4_7_csv.tar.gz"
FOODB_FILE = DATA_DIR / "foodb_2020_4_7_csv.tar.gz"
CHUNK     = 5_000


def download_file(url, dest):
    if dest.exists():
        print(f"  Already downloaded: {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")
        return
    print(f"  Downloading FooDB CSV (~952MB)...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total   = int(resp.headers.get('content-length', 0))
    written = 0
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            written += len(chunk)
            if total:
                print(f"\r  {written/1e6:.0f} / {total/1e6:.0f} MB", end='', flush=True)
    print(f"\n  Done.")


def parse_and_insert(conn, limit=None):
    cursor   = conn.cursor()
    inserted = 0
    skipped  = 0
    batch    = []

    print("Opening tar archive and locating compounds.csv...")

    # FooDB ships as a plain .tar (not gzip) created on macOS
    # Use 'r|*' to auto-detect format and skip ._metadata entries
    compounds_data = None
    with tarfile.open(FOODB_FILE, 'r|*') as tar:
        for member in tar:
            basename = member.name.split('/')[-1]
            if basename.startswith('.'):          # skip macOS ._metadata files
                continue
            if basename.lower() in ('compounds.csv', 'compound.csv'):
                f = tar.extractfile(member)
                if f:
                    compounds_data = f.read()
                    print(f"  Found: {member.name}")
                break

    if not compounds_data:
        print("ERROR: compounds.csv not found. Check archive contents manually.")
        return 0

    text   = io.TextIOWrapper(io.BytesIO(compounds_data), encoding='utf-8', errors='replace')
    reader = csv.DictReader(text)
    print(f"  Columns: {list(reader.fieldnames)[:10] if reader.fieldnames else 'NONE'}")

    for row in reader:
        name     = row.get('name', '').strip() or None
        formula  = row.get('moldb_formula', '').strip() or None
        smiles   = row.get('moldb_smiles', '').strip() or None
        inchikey = row.get('moldb_inchikey', '').strip() or None
        cas      = row.get('cas_number', '').strip() or None
        pub_id   = row.get('public_id', '').strip() or \
                   row.get('id', '').strip() or None

        mass_str = row.get('moldb_mono_mass', '').strip()
        try:
            mass = float(mass_str)
        except (ValueError, AttributeError):
            skipped += 1
            continue

        if mass < 50 or mass > 2000:
            skipped += 1
            continue

        formula_norm = formula.strip().upper().replace(' ', '') if formula else None

        batch.append((
            'FooDB', pub_id, name,
            formula, mass, cas, inchikey, formula_norm, smiles
        ))

        if len(batch) >= CHUNK:
            _flush(cursor, batch)
            conn.commit()
            inserted += len(batch)
            batch = []
            print(f"  Inserted {inserted:,}...", end='\r')

        if limit and (inserted + len(batch)) >= limit:
            break

    if batch:
        _flush(cursor, batch)
        conn.commit()
        inserted += len(batch)

    print(f"\n  Done — inserted: {inserted:,}  skipped: {skipped:,}")
    return inserted


def _flush(cursor, batch):
    cursor.executemany('''
        INSERT OR IGNORE INTO compounds
            (source_database, source_id, name, formula, exact_mass,
             cas, inchikey, formula_normalized, smiles)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', batch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None,
                        help='Max compounds to insert (for testing)')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download (file already present)')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")

    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)").fetchall()]
    if 'smiles' not in cols:
        print("ERROR: smiles column missing. Run migrate_add_smiles.py first.")
        conn.close()
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_download:
        print("Step 1/2 — Downloading FooDB")
        download_file(FOODB_URL, FOODB_FILE)
    else:
        print("Step 1/2 — Skipping download")

    print("\nStep 2/2 — Parsing and inserting")
    start    = time.time()
    inserted = parse_and_insert(conn, args.limit)
    elapsed  = time.time() - start

    total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    print(f"\nFooDB import complete in {elapsed:.0f}s")
    print(f"  Inserted: {inserted:,}")
    print(f"  DB total: {total:,}")

    conn.close()


if __name__ == "__main__":
    main()