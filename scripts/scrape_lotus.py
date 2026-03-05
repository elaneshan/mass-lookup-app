"""
LOTUS Natural Products Scraper
================================
Downloads the LOTUS natural products database (~750MB CSV).
LOTUS includes flavonoids, terpenoids, alkaloids, and other natural products
with full InChIKey, SMILES, and compound class annotations.

Source: https://lotus.naturalproducts.net
File:   https://zenodo.org/records/12665171/files/lotus_db.csv.gz

Run on server:
    python scripts/scrape_lotus.py
    python scripts/scrape_lotus.py --limit 5000   # test run
    python scripts/scrape_lotus.py --flavonoids-only  # only flavonoid class

Adds ~200k+ compounds to DB with source_database = 'LOTUS'
"""

import sqlite3
import requests
import gzip
import csv
import io
import time
import argparse
from pathlib import Path

DB_FILE   = "database/compounds.db"
DATA_DIR  = Path("data/raw/lotus")
LOTUS_URL = "https://zenodo.org/records/5794106/files/230106_frozen_metadata.csv.gz"
LOTUS_FILE= DATA_DIR / "230106_frozen_metadata.csv.gz"
CHUNK     = 5_000

# Flavonoid class keywords — LOTUS uses 'np_superclass' and 'np_class' columns
FLAVONOID_KEYWORDS = [
    'flavonoid', 'flavone', 'flavanol', 'flavanone', 'isoflavone',
    'anthocyanin', 'chalcone', 'aurone', 'flavanonol', 'catechin',
]


def download_file(url, dest):
    if dest.exists():
        print(f"  Already downloaded: {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")
        return
    print(f"  Downloading LOTUS database...")
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


def is_flavonoid(row):
    """Check if compound is classified as a flavonoid."""
    fields = [
        row.get('np_superclass', ''),
        row.get('np_class', ''),
        row.get('np_pathway', ''),
    ]
    text = ' '.join(fields).lower()
    return any(kw in text for kw in FLAVONOID_KEYWORDS)


def parse_and_insert(conn, flavonoids_only=False, limit=None):
    cursor   = conn.cursor()
    inserted = 0
    skipped  = 0
    filtered = 0
    batch    = []

    print("Parsing LOTUS CSV...")

    with gzip.open(LOTUS_FILE, 'rt', encoding='utf-8', errors='replace') as gz:
        reader = csv.DictReader(gz)

        # Print headers on first run so we can verify column names
        headers = reader.fieldnames
        print(f"  Columns found: {headers[:8] if headers else 'NONE — check file'}")

        for row in reader:
            inchikey = row.get('structure_inchikey', '').strip()
            smiles   = row.get('structure_smiles', '').strip() or \
                       row.get('structure_smiles_2D', '').strip()
            formula  = row.get('structure_molecular_formula', '').strip()
            # Try multiple possible name columns
            name = (row.get('structure_nameTraditional') or
                    row.get('structure_name') or
                    row.get('structure_nameIUPAC') or
                    '').strip() or None

            try:
                mass = float(row.get('structure_exact_mass', '').strip())
            except (ValueError, AttributeError):
                skipped += 1
                continue

            # Skip out of metabolomics range
            if mass < 50 or mass > 2000:
                filtered += 1
                continue

            # Flavonoid filter
            if flavonoids_only and not is_flavonoid(row):
                filtered += 1
                continue

            source_id     = inchikey or row.get('structure_wikidata', '').strip()
            formula_norm  = formula.strip().upper().replace(' ', '') if formula else None
            np_class      = row.get('np_class', '').strip() or None

            batch.append((
                'LOTUS', source_id, name,
                formula, mass, None, inchikey, formula_norm, smiles
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

    print(f"\n  Done — inserted: {inserted:,}  "
          f"skipped (bad data): {skipped:,}  filtered: {filtered:,}")
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
    parser.add_argument('--flavonoids-only', action='store_true',
                        help='Only insert flavonoid-class compounds')
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
        print("Step 1/2 — Downloading LOTUS")
        download_file(LOTUS_URL, LOTUS_FILE)
    else:
        print("Step 1/2 — Skipping download")

    print(f"\nStep 2/2 — Parsing and inserting "
          f"({'flavonoids only' if args.flavonoids_only else 'all compounds'})")
    start    = time.time()
    inserted = parse_and_insert(conn, args.flavonoids_only, args.limit)
    elapsed  = time.time() - start

    total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    print(f"\nLOTUS import complete in {elapsed:.0f}s")
    print(f"  Inserted: {inserted:,}")
    print(f"  DB total: {total:,}")

    conn.close()


if __name__ == "__main__":
    main()