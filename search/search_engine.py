"""
Mass Search Engine v2
=====================

Enhanced search functionality:
- Mass search with ion mode adjustment
- Formula search
- Multi-source database support

Usage:
    from search.search_engine_v2 import SearchEngine

    engine = SearchEngine()
    results = engine.search_by_mass(180.063, tolerance=0.5, ion_mode='positive')
    results = engine.search_by_formula('C6H12O6')
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Literal

# Database path
DB_FILE = "database/compounds.db"

# Ion mode mass adjustments (for common LC-MS adducts)
ION_ADJUSTMENTS = {
    'positive': 1.007276,  # [M+H]+
    'negative': -1.007276,  # [M-H]-
    'neutral': 0.0
}


class SearchEngine:
    """Enhanced mass search engine with formula search and ion modes."""

    def __init__(self, db_path: str = DB_FILE):
        """
        Initialize search engine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Verify database exists
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found at: {db_path}\n"
                f"Please run: python scripts/build_database_v2.py"
            )

    def search_by_mass(
        self,
        target_mass: float,
        tolerance: float = 0.5,
        ion_mode: Literal['positive', 'negative', 'neutral'] = 'neutral',
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for compounds by exact mass with ion mode adjustment.

        Args:
            target_mass: Observed mass from LC-MS (e.g., 181.071 for glucose [M+H]+)
            tolerance: Mass tolerance in Da (default: 0.5)
            ion_mode: 'positive' ([M+H]+), 'negative' ([M-H]-), or 'neutral'
            source_filter: List of database sources to search (e.g., ['HMDB', 'KEGG'])
            max_results: Maximum number of results to return

        Returns:
            List of matching compounds with mass error and ppm error
        """

        # Adjust for ion mode to get neutral mass
        neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)

        # Calculate mass range
        lower_bound = neutral_mass - tolerance
        upper_bound = neutral_mass + tolerance

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = '''
            SELECT 
                source_database,
                source_id,
                name,
                formula,
                exact_mass,
                ABS(exact_mass - ?) as mass_error,
                ABS((exact_mass - ?) / ? * 1000000) as ppm_error
            FROM compounds
            WHERE exact_mass BETWEEN ? AND ?
        '''

        params = [neutral_mass, neutral_mass, neutral_mass, lower_bound, upper_bound]

        # Add source filter if specified
        if source_filter:
            placeholders = ','.join('?' * len(source_filter))
            query += f' AND source_database IN ({placeholders})'
            params.extend(source_filter)

        query += ' ORDER BY mass_error ASC'

        # Add limit if specified
        if max_results is not None:
            query += f' LIMIT {max_results}'

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts
        results = []
        for row in rows:
            results.append({
                'source': row['source_database'],
                'source_id': row['source_id'],
                'name': row['name'],
                'formula': row['formula'] if row['formula'] else 'N/A',
                'neutral_mass': round(row['exact_mass'], 4),
                'observed_mass': round(target_mass, 4),
                'mass_error': round(row['mass_error'], 4),
                'ppm_error': round(row['ppm_error'], 2),
                'ion_mode': ion_mode
            })

        conn.close()
        return results

    def search_by_formula(
        self,
        formula: str,
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for compounds by exact molecular formula.

        Args:
            formula: Molecular formula (e.g., 'C6H12O6')
            source_filter: List of database sources to search
            max_results: Maximum number of results to return

        Returns:
            List of matching compounds
        """

        # Normalize formula (uppercase, no spaces)
        formula_normalized = formula.strip().upper().replace(' ', '')

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = '''
            SELECT 
                source_database,
                source_id,
                name,
                formula,
                exact_mass
            FROM compounds
            WHERE UPPER(REPLACE(formula, ' ', '')) = ?
        '''

        params = [formula_normalized]

        # Add source filter if specified
        if source_filter:
            placeholders = ','.join('?' * len(source_filter))
            query += f' AND source_database IN ({placeholders})'
            params.extend(source_filter)

        query += ' ORDER BY exact_mass ASC'

        # Add limit if specified
        if max_results is not None:
            query += f' LIMIT {max_results}'

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts
        results = []
        for row in rows:
            results.append({
                'source': row['source_database'],
                'source_id': row['source_id'],
                'name': row['name'],
                'formula': row['formula'] if row['formula'] else 'N/A',
                'exact_mass': round(row['exact_mass'], 4)
            })

        conn.close()
        return results

    def get_stats(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dict with database stats including breakdown by source
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total compounds
        cursor.execute('SELECT COUNT(*) FROM compounds')
        total = cursor.fetchone()[0]

        # Breakdown by source
        cursor.execute('SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database')
        by_source = {row[0]: row[1] for row in cursor.fetchall()}

        # Mass range
        cursor.execute('SELECT MIN(exact_mass), MAX(exact_mass) FROM compounds')
        min_mass, max_mass = cursor.fetchone()

        conn.close()

        return {
            'total_compounds': total,
            'by_source': by_source,
            'min_mass': round(min_mass, 4) if min_mass else None,
            'max_mass': round(max_mass, 4) if max_mass else None
        }


# Convenience functions
def search_by_mass(target_mass: float, tolerance: float = 0.5, ion_mode: str = 'neutral') -> List[Dict]:
    """Quick mass search function."""
    engine = SearchEngine()
    return engine.search_by_mass(target_mass, tolerance, ion_mode)


def search_by_formula(formula: str) -> List[Dict]:
    """Quick formula search function."""
    engine = SearchEngine()
    return engine.search_by_formula(formula)


# Test script
if __name__ == "__main__":
    print("=" * 100)
    print("Mass Search Engine v2 - Test Mode")
    print("=" * 100)
    print()

    # Initialize
    engine = SearchEngine()

    # Stats
    stats = engine.get_stats()
    print(f"Database Statistics:")
    print(f"  Total compounds: {stats['total_compounds']:,}")
    for source, count in stats['by_source'].items():
        print(f"    - {source}: {count:,}")
    print(f"  Mass range: {stats['min_mass']} - {stats['max_mass']} Da")
    print()

    # Test 1: Mass search with ion modes
    print("=" * 100)
    print("TEST 1: Mass Search with Ion Modes")
    print("=" * 100)

    # Glucose [M+H]+ = 181.071
    test_mass = 181.071
    print(f"\nSearching for observed mass {test_mass} in positive mode")
    print("(Should find glucose and isomers - neutral mass ~180.063)")

    results = engine.search_by_mass(test_mass, tolerance=0.5, ion_mode='positive', max_results=5)

    if results:
        print(f"\nFound {len(results)} matches:\n")
        print(f"{'Name':<35} {'Formula':<15} {'Neutral Mass':<15} {'Error (Da)':<12} {'Error (ppm)'}")
        print("-" * 100)
        for r in results:
            print(f"{r['name'][:33]:<35} {r['formula']:<15} {r['neutral_mass']:<15} {r['mass_error']:<12} {r['ppm_error']}")

    # Test 2: Formula search
    print("\n" + "=" * 100)
    print("TEST 2: Formula Search")
    print("=" * 100)

    formula = "C6H12O6"
    print(f"\nSearching for formula: {formula}")
    print("(Should find glucose, fructose, galactose, etc.)")

    results = engine.search_by_formula(formula, max_results=10)

    if results:
        print(f"\nFound {len(results)} matches:\n")
        print(f"{'Name':<40} {'Formula':<15} {'Exact Mass':<15} {'Source'}")
        print("-" * 100)
        for r in results:
            print(f"{r['name'][:38]:<40} {r['formula']:<15} {r['exact_mass']:<15} {r['source']}")

    # Test 3: Negative mode
    print("\n" + "=" * 100)
    print("TEST 3: Negative Ion Mode")
    print("=" * 100)

    # Glucose [M-H]- = 179.056
    test_mass_neg = 179.056
    print(f"\nSearching for observed mass {test_mass_neg} in negative mode")

    results = engine.search_by_mass(test_mass_neg, tolerance=0.5, ion_mode='negative', max_results=5)

    if results:
        print(f"\nFound {len(results)} matches:\n")
        print(f"{'Name':<35} {'Neutral Mass':<15} {'Error (Da)':<12}")
        print("-" * 100)
        for r in results:
            print(f"{r['name'][:33]:<35} {r['neutral_mass']:<15} {r['mass_error']:<12}")

    print("\n" + "=" * 100)
    print("✅ Search engine v2 test complete!")
    print("=" * 100)