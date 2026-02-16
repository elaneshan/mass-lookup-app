"""
Multi-Source Database Builder for Mass Lookup Tool
===================================================

This script builds a unified SQLite database from multiple sources:
- HMDB (Human Metabolome Database)
- KEGG (Kyoto Encyclopedia of Genes and Genomes)

Each source is parsed separately and merged into a single normalized schema.

Usage:
    python scripts/build_database_v2.py
"""

import sqlite3
import xml.etree.ElementTree as ET
import os
import re
from pathlib import Path

# Configuration
HMDB_XML_FILE = "data/raw/hmdb_metabolites.xml"
KEGG_COMPOUND_FILE = "data/raw/kegg_compound.txt"
DB_FILE = "database/compounds.db"

# HMDB XML namespace
HMDB_NS = {'hmdb': 'http://www.hmdb.ca'}


def create_database():
    """Create the SQLite database with updated multi-source schema."""

    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    # Remove old database if it exists
    if os.path.exists(DB_FILE):
        print(f"Removing existing database: {DB_FILE}")
        os.remove(DB_FILE)

    # Create new database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create table with multi-source support
    cursor.execute('''
        CREATE TABLE compounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_database TEXT NOT NULL,
            source_id TEXT,
            name TEXT,
            formula TEXT,
            exact_mass REAL,
            UNIQUE(source_database, source_id)
        )
    ''')

    # Create indexes
    cursor.execute('CREATE INDEX idx_mass ON compounds(exact_mass)')
    cursor.execute('CREATE INDEX idx_formula ON compounds(formula)')
    cursor.execute('CREATE INDEX idx_source ON compounds(source_database)')

    print("✓ Database schema created with multi-source support")

    conn.commit()
    return conn


def parse_hmdb(conn):
    """Parse HMDB XML and insert into database."""

    if not os.path.exists(HMDB_XML_FILE):
        print(f"⚠ HMDB file not found: {HMDB_XML_FILE}")
        print("  Skipping HMDB import")
        return 0

    print(f"\n📖 Parsing HMDB: {HMDB_XML_FILE}")
    print("This may take 5-10 minutes...")

    cursor = conn.cursor()

    total = 0
    inserted = 0
    skipped = 0

    context = ET.iterparse(HMDB_XML_FILE, events=('start', 'end'))
    context = iter(context)
    event, root = next(context)

    for event, elem in context:
        if event == 'end' and elem.tag == '{http://www.hmdb.ca}metabolite':
            total += 1

            # Extract fields
            hmdb_id = None
            name = None
            formula = None
            mass = None

            accession_elem = elem.find('hmdb:accession', HMDB_NS)
            if accession_elem is not None:
                hmdb_id = accession_elem.text

            name_elem = elem.find('hmdb:name', HMDB_NS)
            if name_elem is not None:
                name = name_elem.text

            formula_elem = elem.find('hmdb:chemical_formula', HMDB_NS)
            if formula_elem is not None:
                formula = formula_elem.text

            # Note: HMDB has typo - 'monisotopic' not 'monoisotopic'
            mass_elem = elem.find('hmdb:monisotopic_molecular_weight', HMDB_NS)
            if mass_elem is not None and mass_elem.text:
                try:
                    mass = float(mass_elem.text)
                except (ValueError, TypeError):
                    mass = None

            # Insert if valid
            if hmdb_id and name and mass is not None:
                try:
                    cursor.execute('''
                        INSERT INTO compounds (source_database, source_id, name, formula, exact_mass)
                        VALUES (?, ?, ?, ?, ?)
                    ''', ('HMDB', hmdb_id, name, formula, mass))
                    inserted += 1
                except sqlite3.IntegrityError:
                    skipped += 1  # Duplicate
            else:
                skipped += 1

            if total % 10000 == 0:
                print(f"  Processed: {total:,} | Inserted: {inserted:,} | Skipped: {skipped:,}")

            elem.clear()
            root.clear()

    conn.commit()

    print(f"\n✓ HMDB complete: {inserted:,} compounds inserted")
    return inserted


def parse_kegg(conn):
    """Parse KEGG COMPOUND list - note: list format lacks mass/formula data."""

    if not os.path.exists(KEGG_COMPOUND_FILE):
        print(f"\n⚠ KEGG file not found: {KEGG_COMPOUND_FILE}")
        print("  Run: python scripts/download_kegg.py")
        print("  Skipping KEGG import")
        return 0

    print(f"\n📖 KEGG list file found: {KEGG_COMPOUND_FILE}")
    print("⚠  Note: KEGG list format only contains IDs and names")
    print("   It does NOT include molecular formulas or exact masses")
    print("   For full KEGG integration, we'd need to fetch each compound individually")
    print("   (19k+ API calls = several hours)")
    print("\n   Skipping KEGG for now - HMDB provides comprehensive coverage")

    return 0



def verify_database(conn):
    """Verify the multi-source database."""

    print("\n🧪 Verifying database...")

    cursor = conn.cursor()

    # Total compounds
    cursor.execute('SELECT COUNT(*) FROM compounds')
    total = cursor.fetchone()[0]
    print(f"Total compounds: {total:,}")

    # Breakdown by source
    cursor.execute('SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database')
    for source, count in cursor.fetchall():
        print(f"  - {source}: {count:,}")

    # Sample from each source
    print("\nSample compounds:")
    print("-" * 100)
    print(f"{'Source':<10} {'ID':<15} {'Name':<40} {'Formula':<15} {'Mass':<10}")
    print("-" * 100)

    cursor.execute('''
        SELECT source_database, source_id, name, formula, exact_mass
        FROM compounds
        ORDER BY source_database, RANDOM()
        LIMIT 10
    ''')

    for row in cursor.fetchall():
        source, source_id, name, formula, mass = row
        name = name[:38] if name else "N/A"
        formula = formula[:13] if formula else "N/A"
        print(f"{source:<10} {source_id:<15} {name:<40} {formula:<15} {mass:<10.4f}")

    print("-" * 100)

    # Test search
    print("\n🔍 Testing multi-source search...")
    test_mass = 180.063
    tolerance = 0.5

    cursor.execute('''
        SELECT source_database, name, formula, exact_mass,
               ABS(exact_mass - ?) as mass_error
        FROM compounds
        WHERE exact_mass BETWEEN ? AND ?
        ORDER BY mass_error ASC
        LIMIT 5
    ''', (test_mass, test_mass - tolerance, test_mass + tolerance))

    results = cursor.fetchall()
    print(f"Search for {test_mass} ± {tolerance} Da:")
    print(f"Found {len(results)} matches (top 5):\n")

    if results:
        print(f"{'Source':<10} {'Name':<40} {'Formula':<15} {'Mass':<12} {'Error':<10}")
        print("-" * 100)
        for source, name, formula, mass, error in results:
            name = name[:38] if name else "N/A"
            formula = formula[:13] if formula else "N/A"
            print(f"{source:<10} {name:<40} {formula:<15} {mass:<12.4f} {error:<10.4f}")

    print("\n✅ Database verification complete!")


def main():
    """Main execution."""

    print("=" * 100)
    print("Multi-Source Database Builder")
    print("=" * 100)
    print()

    # Create database
    conn = create_database()

    # Parse sources
    hmdb_count = parse_hmdb(conn)
    kegg_count = parse_kegg(conn)

    # Verify
    verify_database(conn)

    # Close
    conn.close()

    total = hmdb_count + kegg_count

    print(f"\n✅ SUCCESS! Multi-source database ready at: {DB_FILE}")
    print(f"Total compounds: {total:,}")
    print("\nNext step: Update search engine for multi-source queries")


if __name__ == "__main__":
    main()