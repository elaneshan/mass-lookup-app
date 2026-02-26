"""
Multi-Source Database Builder v5
==================================

Sources: HMDB + ChEBI + LipidMaps + NPAtlas + (MoNA via --mona-only)

Usage:
    python build_database_v5.py              # HMDB + ChEBI + LipidMaps + NPAtlas
    python build_database_v5.py --mona-only  # Add MoNA to existing DB (resumable)
"""

import sqlite3
import xml.etree.ElementTree as ET
import os
import re
import csv
import argparse

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────

HMDB_XML_FILE      = "data/raw/hmdb_metabolites.xml"
CHEBI_SDF_FILE     = "data/raw/chebi.sdf"
LIPIDMAPS_SDF_FILE = "data/raw/structures.sdf"
NPATLAS_SDF_FILE   = "data/raw/NPAtlas_download_2024_09.sdf"
MONA_SDF_FILE      = "data/raw/moNA-export-All_Spectra.sdf"

DB_FILE            = "database/compounds.db"

HMDB_NS   = {'hmdb': 'http://www.hmdb.ca'}
CAS_REGEX = re.compile(r"^\d{2,7}-\d{2}-\d$")

MONA_CHUNK_SIZE = 5_000


# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def create_database(mona_only=False):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    if mona_only:
        if not os.path.exists(DB_FILE):
            print("⚠  No existing database — creating fresh one.")
        else:
            print(f"📂 Opening existing DB for MoNA import: {DB_FILE}")
            conn = sqlite3.connect(DB_FILE)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            return conn

    if os.path.exists(DB_FILE):
        print(f"Removing existing database: {DB_FILE}")
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE compounds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            source_database  TEXT    NOT NULL,
            source_id        TEXT,
            name             TEXT,
            formula          TEXT,
            exact_mass       REAL,
            cas              TEXT,
            inchikey             TEXT,
            formula_normalized   TEXT,
            UNIQUE(source_database, source_id)
        )
    ''')

    cursor.execute('CREATE INDEX idx_mass               ON compounds(exact_mass)')
    cursor.execute('CREATE INDEX idx_formula            ON compounds(formula)')
    cursor.execute('CREATE INDEX idx_formula_normalized ON compounds(formula_normalized)')
    cursor.execute('CREATE INDEX idx_source   ON compounds(source_database)')
    cursor.execute('CREATE INDEX idx_cas      ON compounds(cas)')
    cursor.execute('CREATE INDEX idx_inchikey ON compounds(inchikey)')

    conn.commit()
    print("✓ Database schema created")
    return conn


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def normalize_cas(value):
    if not value:
        return None
    value = value.strip().split()[0].strip()
    return value if CAS_REGEX.match(value) else None


def insert_record(cursor, source, source_id, name, formula, mass, cas, inchikey=None):
    try:
        cursor.execute('''
            INSERT INTO compounds
                (source_database, source_id, name, formula, exact_mass, cas, inchikey, formula_normalized)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (source, source_id, name, formula, mass, cas, inchikey, formula.strip().upper().replace(' ','') if formula else None))
        return True
    except sqlite3.IntegrityError:
        return False


def parse_sdf(filepath):
    """Universal SDF parser — handles both '> <FIELD>' and '>  <FIELD>' formats."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        entry = {}
        current_field = None
        for line in f:
            stripped = line.strip()
            if stripped.startswith('>') and '<' in stripped:
                m = re.match(r'^>+\s*<(.+?)>', stripped)
                if m:
                    current_field = m.group(1).strip()
                    entry[current_field] = ''
            elif stripped == '$$$$':
                yield entry
                entry = {}
                current_field = None
            else:
                if current_field is not None and stripped:
                    entry[current_field] = (entry[current_field] + ' ' + stripped).strip()


# ─────────────────────────────────────────────
# HMDB
# ─────────────────────────────────────────────

def parse_hmdb(conn):
    if not os.path.exists(HMDB_XML_FILE):
        print("⚠  HMDB not found — skipping")
        return 0

    print("\n📖 Parsing HMDB...")
    cursor = conn.cursor()
    total = inserted = 0

    context = iter(ET.iterparse(HMDB_XML_FILE, events=('start', 'end')))
    event, root = next(context)

    for event, elem in context:
        if event == 'end' and elem.tag == '{http://www.hmdb.ca}metabolite':
            total += 1
            hmdb_id  = elem.findtext('hmdb:accession',                    namespaces=HMDB_NS)
            name     = elem.findtext('hmdb:name',                         namespaces=HMDB_NS)
            formula  = elem.findtext('hmdb:chemical_formula',             namespaces=HMDB_NS)
            mass     = elem.findtext('hmdb:monisotopic_molecular_weight', namespaces=HMDB_NS)
            cas      = elem.findtext('hmdb:cas_registry_number',          namespaces=HMDB_NS)
            inchikey = elem.findtext('hmdb:inchikey',                     namespaces=HMDB_NS)

            try:
                mass = float(mass) if mass else None
            except Exception:
                mass = None

            if hmdb_id and name and mass:
                if insert_record(cursor, "HMDB", hmdb_id, name, formula,
                                 mass, normalize_cas(cas), inchikey):
                    inserted += 1

            if total % 10_000 == 0:
                conn.commit()
                print(f"   {total:,} processed, {inserted:,} inserted")

            elem.clear()
            root.clear()

    conn.commit()
    print(f"✓ HMDB — inserted: {inserted:,} / {total:,}")
    return inserted


# ─────────────────────────────────────────────
# ChEBI
# ─────────────────────────────────────────────

def parse_chebi(conn):
    if not os.path.exists(CHEBI_SDF_FILE):
        print("⚠  ChEBI not found — skipping")
        return 0

    print("\n📖 Parsing ChEBI...")
    cursor = conn.cursor()
    inserted = total = 0

    for entry in parse_sdf(CHEBI_SDF_FILE):
        total += 1
        chebi_id = entry.get('ChEBI ID', '').strip()
        name     = entry.get('ChEBI NAME', '').strip()
        formula  = entry.get('FORMULA', '').strip() or None
        mass_str = entry.get('MONOISOTOPIC_MASS', '').strip()
        cas      = normalize_cas(entry.get('CAS Registry Numbers', ''))
        inchikey = entry.get('INCHIKEY', '').strip() or None

        try:
            mass = float(mass_str)
        except (ValueError, TypeError):
            continue

        if not chebi_id:
            continue

        if insert_record(cursor, "ChEBI", chebi_id, name, formula, mass, cas, inchikey):
            inserted += 1

        if total % 20_000 == 0:
            conn.commit()
            print(f"   {total:,} processed, {inserted:,} inserted")

    conn.commit()
    print(f"✓ ChEBI — inserted: {inserted:,} / {total:,}")
    return inserted


# ─────────────────────────────────────────────
# LipidMaps
# ─────────────────────────────────────────────

def parse_lipidmaps(conn):
    if not os.path.exists(LIPIDMAPS_SDF_FILE):
        print("⚠  LipidMaps not found — skipping")
        return 0

    print("\n📖 Parsing LipidMaps...")
    cursor = conn.cursor()
    inserted = total = 0

    for entry in parse_sdf(LIPIDMAPS_SDF_FILE):
        total += 1
        lm_id    = entry.get('LM_ID', '').strip()
        name     = (entry.get('SYSTEMATIC_NAME') or entry.get('NAME', '')).strip()
        formula  = entry.get('FORMULA', '').strip() or None
        mass_str = entry.get('EXACT_MASS', '').strip()
        inchikey = entry.get('INCHI_KEY', '').strip() or None

        try:
            mass = float(mass_str)
        except (ValueError, TypeError):
            continue

        if insert_record(cursor, "LipidMaps", lm_id, name, formula, mass, None, inchikey):
            inserted += 1

        if total % 10_000 == 0:
            conn.commit()
            print(f"   {total:,} processed, {inserted:,} inserted")

    conn.commit()
    print(f"✓ LipidMaps — inserted: {inserted:,} / {total:,}")
    return inserted


# ─────────────────────────────────────────────
# NPAtlas
# ─────────────────────────────────────────────

def parse_npatlas(conn):
    if not os.path.exists(NPATLAS_SDF_FILE):
        print("⚠  NPAtlas not found — skipping")
        return 0

    print("\n📖 Parsing NPAtlas...")
    cursor = conn.cursor()
    inserted = total = 0

    for entry in parse_sdf(NPATLAS_SDF_FILE):
        total += 1
        npa_id   = entry.get('npaid', '').strip()
        name     = entry.get('compound_name', '').strip()
        formula  = entry.get('compound_molecular_formula', '').strip() or None
        mass_str = entry.get('compound_accurate_mass', '').strip()
        inchikey = entry.get('compound_inchikey', '').strip() or None

        try:
            mass = float(mass_str)
        except (ValueError, TypeError):
            continue

        if not npa_id:
            npa_id = f"npatlas_{total}"

        if insert_record(cursor, "NPAtlas", npa_id, name, formula, mass, None, inchikey):
            inserted += 1

        if total % 10_000 == 0:
            conn.commit()
            print(f"   {total:,} processed, {inserted:,} inserted")

    conn.commit()
    print(f"✓ NPAtlas — inserted: {inserted:,} / {total:,}")
    return inserted


# ─────────────────────────────────────────────
# MoNA  (run separately via --mona-only)
# ─────────────────────────────────────────────

def parse_mona(conn):
    if not os.path.exists(MONA_SDF_FILE):
        print("⚠  MoNA not found — skipping")
        return 0

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM compounds WHERE source_database='MoNA'")
    already = cursor.fetchone()[0]
    if already > 0:
        print(f"\n📖 Resuming MoNA ({already:,} already in DB)...")
    else:
        print("\n📖 Parsing MoNA (17 GB — run overnight)...")
        print("   Safe to Ctrl+C and resume — duplicates skipped automatically.")

    inserted = total = skipped = 0
    batch = []

    def flush(batch):
        nonlocal inserted
        cur = conn.cursor()
        for row in batch:
            if insert_record(cur, *row):
                inserted += 1
        conn.commit()

    with open(MONA_SDF_FILE, 'r', encoding='utf-8', errors='replace') as f:
        entry = {}
        current_field = None
        for line in f:
            stripped = line.strip()
            if stripped.startswith('>') and '<' in stripped:
                m = re.match(r'^>+\s*<(.+?)>', stripped)
                if m:
                    current_field = m.group(1).strip()
                    entry[current_field] = ''
            elif stripped == '$$$$':
                total += 1
                mona_id  = entry.get('ID', '').strip() or f"mona_{total}"
                name     = entry.get('NAME', '').strip()
                formula  = entry.get('FORMULA', '').strip() or None
                mass_str = entry.get('EXACT MASS', '').strip()
                inchikey = entry.get('INCHIKEY', '').strip() or None

                try:
                    mass = float(mass_str)
                except (ValueError, TypeError):
                    skipped += 1
                    entry = {}
                    current_field = None
                    continue

                batch.append(("MoNA", mona_id, name, formula, mass, None, inchikey))

                if len(batch) >= MONA_CHUNK_SIZE:
                    flush(batch)
                    batch = []
                    print(f"   {total:,} processed | {inserted:,} inserted | {skipped:,} skipped")

                entry = {}
                current_field = None
            else:
                if current_field is not None and stripped:
                    entry[current_field] = (entry.get(current_field, '') + ' ' + stripped).strip()

    if batch:
        flush(batch)

    conn.commit()
    print(f"✓ MoNA — inserted: {inserted:,} / {total:,}")
    return inserted


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build LC-MS compound database")
    parser.add_argument('--mona-only', action='store_true',
                        help='Only add MoNA to existing DB (resumable, run overnight)')
    args = parser.parse_args()

    print("=" * 70)
    print("Multi-Source Database Builder v5")
    print("Sources: HMDB + ChEBI + LipidMaps + NPAtlas  [+ MoNA via --mona-only]")
    print("=" * 70)

    conn = create_database(mona_only=args.mona_only)

    hmdb = chebi = lipid = npatlas = mona = 0

    if not args.mona_only:
        hmdb    = parse_hmdb(conn)
        chebi   = parse_chebi(conn)
        lipid   = parse_lipidmaps(conn)
        npatlas = parse_npatlas(conn)

    if args.mona_only:
        mona = parse_mona(conn)

    conn.close()

    total = hmdb + chebi + lipid + npatlas + mona
    print("\n" + "=" * 70)
    print("✅ Database build complete")
    print(f"   HMDB:      {hmdb:,}")
    print(f"   ChEBI:     {chebi:,}")
    print(f"   LipidMaps: {lipid:,}")
    print(f"   NPAtlas:   {npatlas:,}")
    print(f"   MoNA:      {mona:,}")
    print(f"   TOTAL:     {total:,}")
    print("\nNext step: python main.py")


if __name__ == "__main__":
    main()