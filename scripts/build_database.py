"""
Multi-Source Database Builder v3
==================================

Builds unified SQLite database from:
- HMDB (~217k metabolites)
- ChEBI (~200k biochemical compounds)
- LipidMaps (~50k lipids)

Usage:
    python scripts/build_database_v3.py

Expected files:
    data/raw/hmdb_metabolites.xml
    data/raw/chebi.sdf
    data/raw/structures.sdf   (LipidMaps)
"""

import sqlite3
import xml.etree.ElementTree as ET
import os
from pathlib import Path

# File paths
HMDB_XML_FILE    = "data/raw/hmdb_metabolites.xml"
CHEBI_SDF_FILE   = "data/raw/chebi.sdf"
LIPIDMAPS_SDF_FILE = "data/raw/structures.sdf"
DB_FILE          = "database/compounds.db"

# HMDB XML namespace
HMDB_NS = {'hmdb': 'http://www.hmdb.ca'}


# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────

def create_database():
    """Create the SQLite database with multi-source schema."""

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    if os.path.exists(DB_FILE):
        print(f"Removing existing database: {DB_FILE}")
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE compounds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            source_database  TEXT    NOT NULL,
            source_id        TEXT,
            name             TEXT,
            formula          TEXT,
            exact_mass       REAL,
            UNIQUE(source_database, source_id)
        )
    ''')

    cursor.execute('CREATE INDEX idx_mass    ON compounds(exact_mass)')
    cursor.execute('CREATE INDEX idx_formula ON compounds(formula)')
    cursor.execute('CREATE INDEX idx_source  ON compounds(source_database)')

    conn.commit()
    print("✓ Database schema created")
    return conn


# ─────────────────────────────────────────────
#  SHARED SDF PARSER
# ─────────────────────────────────────────────

def parse_sdf(filepath):
    """
    Generic SDF file parser.

    Yields one dict per compound containing all > <FIELD> / value pairs
    found in that entry. Handles files of any size via line-by-line reading.
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        entry = {}
        current_field = None

        for line in f:
            line = line.rstrip('\n')

            if line.startswith('> <'):
                # Field header line:  > <FIELD_NAME>
                current_field = line.strip().lstrip('> <').rstrip('>')
                # Strip any trailing whitespace artefacts
                current_field = current_field.strip()
                entry[current_field] = ''

            elif line == '$$$$':
                # End of entry — yield and reset
                yield entry
                entry = {}
                current_field = None

            else:
                # Data line — append to current field value
                if current_field is not None and line.strip():
                    if entry[current_field]:
                        entry[current_field] += ' ' + line.strip()
                    else:
                        entry[current_field] = line.strip()


def insert_compounds(conn, records, source_name):
    """Bulk-insert a list of (source_id, name, formula, mass) tuples."""
    cursor = conn.cursor()
    inserted = 0
    skipped  = 0

    for source_id, name, formula, mass in records:
        try:
            cursor.execute('''
                INSERT INTO compounds
                    (source_database, source_id, name, formula, exact_mass)
                VALUES (?, ?, ?, ?, ?)
            ''', (source_name, source_id, name, formula, mass))
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1  # Duplicate

    conn.commit()
    return inserted, skipped


# ─────────────────────────────────────────────
#  HMDB PARSER
# ─────────────────────────────────────────────

def parse_hmdb(conn):
    """Parse HMDB XML and insert into database."""

    if not os.path.exists(HMDB_XML_FILE):
        print(f"\n⚠  HMDB file not found: {HMDB_XML_FILE} — skipping")
        return 0

    print(f"\n📖 Parsing HMDB: {HMDB_XML_FILE}")
    print("   (This may take 5-10 minutes...)")

    cursor   = conn.cursor()
    total    = inserted = skipped = 0

    context      = ET.iterparse(HMDB_XML_FILE, events=('start', 'end'))
    context      = iter(context)
    event, root  = next(context)

    for event, elem in context:
        if event == 'end' and elem.tag == '{http://www.hmdb.ca}metabolite':
            total += 1

            hmdb_id = formula = name = mass = None

            e = elem.find('hmdb:accession', HMDB_NS)
            if e is not None: hmdb_id = e.text

            e = elem.find('hmdb:name', HMDB_NS)
            if e is not None: name = e.text

            e = elem.find('hmdb:chemical_formula', HMDB_NS)
            if e is not None: formula = e.text

            # HMDB has typo: 'monisotopic' (missing 'o')
            e = elem.find('hmdb:monisotopic_molecular_weight', HMDB_NS)
            if e is not None and e.text:
                try:    mass = float(e.text)
                except: pass

            if hmdb_id and name and mass is not None:
                try:
                    cursor.execute('''
                        INSERT INTO compounds
                            (source_database, source_id, name, formula, exact_mass)
                        VALUES (?, ?, ?, ?, ?)
                    ''', ('HMDB', hmdb_id, name, formula, mass))
                    inserted += 1
                except sqlite3.IntegrityError:
                    skipped += 1
            else:
                skipped += 1

            if total % 10000 == 0:
                print(f"   {total:,} processed | {inserted:,} inserted | {skipped:,} skipped")

            elem.clear()
            root.clear()

    conn.commit()
    print(f"✓  HMDB done — {inserted:,} compounds inserted")
    return inserted


# ─────────────────────────────────────────────
#  CHEBI PARSER
# ─────────────────────────────────────────────

def parse_chebi(conn):
    """Parse ChEBI SDF file and insert into database."""

    if not os.path.exists(CHEBI_SDF_FILE):
        print(f"\n⚠  ChEBI file not found: {CHEBI_SDF_FILE} — skipping")
        return 0

    print(f"\n📖 Parsing ChEBI: {CHEBI_SDF_FILE}")

    records  = []
    total    = skipped = 0

    for entry in parse_sdf(CHEBI_SDF_FILE):
        total += 1

        chebi_id = entry.get('ChEBI ID', '').strip()
        name     = entry.get('ChEBI NAME', '').strip()
        formula  = entry.get('FORMULA', '').strip() or None
        mass_str = entry.get('MONOISOTOPIC MASS', '') or entry.get('MONOISOTOPIC_MASS', '')
        mass_str = mass_str.strip()

        # Skip polymers / entries with no usable mass
        if not chebi_id or not name or not mass_str:
            skipped += 1
            continue

        # Skip polymer formulas (contain 'n')
        if formula and 'n' in formula.lower() and '(' in formula:
            skipped += 1
            continue

        try:
            mass = float(mass_str)
        except ValueError:
            skipped += 1
            continue

        records.append((chebi_id, name, formula, mass))

        if total % 20000 == 0:
            print(f"   {total:,} processed...")

    inserted, dupes = insert_compounds(conn, records, 'ChEBI')
    print(f"✓  ChEBI done — {inserted:,} inserted | {skipped + dupes:,} skipped/dupes")
    return inserted


# ─────────────────────────────────────────────
#  LIPIDMAPS PARSER
# ─────────────────────────────────────────────

def parse_lipidmaps(conn):
    """Parse LipidMaps SDF file and insert into database."""

    if not os.path.exists(LIPIDMAPS_SDF_FILE):
        print(f"\n⚠  LipidMaps file not found: {LIPIDMAPS_SDF_FILE} — skipping")
        return 0

    print(f"\n📖 Parsing LipidMaps: {LIPIDMAPS_SDF_FILE}")

    records = []
    total   = skipped = 0

    for entry in parse_sdf(LIPIDMAPS_SDF_FILE):
        total += 1

        lm_id    = entry.get('LM_ID', '').strip()
        # Prefer SYSTEMATIC_NAME, fall back to NAME
        name     = (entry.get('SYSTEMATIC_NAME') or entry.get('NAME', '')).strip()
        formula  = entry.get('FORMULA', '').strip() or None
        mass_str = entry.get('EXACT_MASS', '').strip()

        if not lm_id or not name or not mass_str:
            skipped += 1
            continue

        try:
            mass = float(mass_str)
        except ValueError:
            skipped += 1
            continue

        records.append((lm_id, name, formula, mass))

        if total % 10000 == 0:
            print(f"   {total:,} processed...")

    inserted, dupes = insert_compounds(conn, records, 'LipidMaps')
    print(f"✓  LipidMaps done — {inserted:,} inserted | {skipped + dupes:,} skipped/dupes")
    return inserted


# ─────────────────────────────────────────────
#  VERIFICATION
# ─────────────────────────────────────────────

def verify_database(conn):
    """Print database summary and run a quick test search."""

    print("\n🧪 Verifying database...")
    cursor = conn.cursor()

    # Totals by source
    cursor.execute('SELECT COUNT(*) FROM compounds')
    total = cursor.fetchone()[0]
    print(f"\nTotal compounds: {total:,}")

    cursor.execute('''
        SELECT source_database, COUNT(*)
        FROM compounds
        GROUP BY source_database
        ORDER BY COUNT(*) DESC
    ''')
    for source, count in cursor.fetchall():
        pct = count / total * 100
        print(f"  {source:<12} {count:>8,}  ({pct:.1f}%)")

    # Sample from each source
    print("\nSample entries per source:")
    print("-" * 95)
    print(f"{'Source':<12} {'ID':<18} {'Name':<35} {'Formula':<14} {'Mass'}")
    print("-" * 95)

    cursor.execute('''
        SELECT source_database, source_id, name, formula, exact_mass
        FROM compounds
        GROUP BY source_database
        HAVING MIN(id)
        LIMIT 10
    ''')
    for row in cursor.fetchall():
        src, sid, name, formula, mass = row
        print(f"{src:<12} {sid:<18} {(name or '')[:33]:<35} {(formula or 'N/A'):<14} {mass:.4f}")
    print("-" * 95)

    # Test search
    test_mass = 180.063
    tolerance = 0.5
    print(f"\n🔍 Test search: {test_mass} ± {tolerance} Da")
    cursor.execute('''
        SELECT source_database, name, formula, exact_mass,
               ABS(exact_mass - ?) as err
        FROM compounds
        WHERE exact_mass BETWEEN ? AND ?
        ORDER BY err ASC
        LIMIT 8
    ''', (test_mass, test_mass - tolerance, test_mass + tolerance))

    rows = cursor.fetchall()
    print(f"Found {len(rows)} matches (top 8):\n")
    print(f"{'Source':<12} {'Name':<38} {'Formula':<14} {'Mass':<12} {'Error'}")
    print("-" * 95)
    for src, name, formula, mass, err in rows:
        print(f"{src:<12} {(name or '')[:36]:<38} {(formula or 'N/A'):<14} {mass:<12.4f} {err:.4f}")

    print("\n✅ Verification complete!")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 95)
    print("Multi-Source Database Builder v3")
    print("Sources: HMDB + ChEBI + LipidMaps")
    print("=" * 95)

    conn = create_database()

    hmdb_count      = parse_hmdb(conn)
    chebi_count     = parse_chebi(conn)
    lipidmaps_count = parse_lipidmaps(conn)

    verify_database(conn)
    conn.close()

    total = hmdb_count + chebi_count + lipidmaps_count
    print(f"\n✅ SUCCESS — database ready at: {DB_FILE}")
    print(f"   HMDB:      {hmdb_count:>8,}")
    print(f"   ChEBI:     {chebi_count:>8,}")
    print(f"   LipidMaps: {lipidmaps_count:>8,}")
    print(f"   TOTAL:     {total:>8,}")
    print("\nNext step: python main.py")


if __name__ == "__main__":
    main()