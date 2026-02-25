"""
Mass Search Engine v3
=====================

Adds:
- CAS number support
- MoNA compatibility
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Literal

DB_FILE = "database/compounds.db"

ION_ADJUSTMENTS = {
    'positive': 1.007276,
    'negative': -1.007276,
    'neutral': 0.0
}


class SearchEngine:

    def __init__(self, db_path: str = DB_FILE):

        self.db_path = db_path

        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found at: {db_path}\n"
                f"Please run: python scripts/build_database_v3.py"
            )

    # ─────────────────────────────────────────────
    # MASS SEARCH
    # ─────────────────────────────────────────────

    def search_by_mass(
        self,
        target_mass: float,
        tolerance: float = 0.5,
        ion_mode: Literal['positive', 'negative', 'neutral'] = 'neutral',
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:

        neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)

        lower_bound = neutral_mass - tolerance
        upper_bound = neutral_mass + tolerance

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = '''
            SELECT 
                source_database,
                source_id,
                name,
                formula,
                exact_mass,
                cas,
                ABS(exact_mass - ?) as mass_error,
                ABS((exact_mass - ?) / ? * 1000000) as ppm_error
            FROM compounds
            WHERE exact_mass BETWEEN ? AND ?
        '''

        params = [neutral_mass, neutral_mass, neutral_mass,
                  lower_bound, upper_bound]

        if source_filter:
            placeholders = ','.join('?' * len(source_filter))
            query += f' AND source_database IN ({placeholders})'
            params.extend(source_filter)

        query += ' ORDER BY mass_error ASC'

        if max_results is not None:
            query += f' LIMIT {max_results}'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'source': row['source_database'],
                'source_id': row['source_id'],
                'name': row['name'],
                'formula': row['formula'] if row['formula'] else 'N/A',
                'cas': row['cas'] if row['cas'] else '',
                'neutral_mass': round(row['exact_mass'], 4),
                'observed_mass': round(target_mass, 4),
                'mass_error': round(row['mass_error'], 4),
                'ppm_error': round(row['ppm_error'], 2),
                'ion_mode': ion_mode
            })

        conn.close()
        return results

    # ─────────────────────────────────────────────
    # BATCH MASS SEARCH
    # ─────────────────────────────────────────────

    def search_batch_masses(
        self,
        mass_adduct_pairs: List[tuple],
        tolerance: float = 0.5,
        source_filter: Optional[List[str]] = None,
        max_results_per_query: int = 20
    ) -> List[Dict]:

        all_results = []
        query_id = 0

        for observed_mass, adduct_delta, adduct_label in mass_adduct_pairs:

            results = self.search_by_mass(
                observed_mass,
                tolerance,
                ion_mode='neutral',
                source_filter=source_filter,
                max_results=max_results_per_query
            )

            neutral_mass = observed_mass - adduct_delta

            for r in results:
                r['query_id'] = query_id
                r['query_mass'] = observed_mass
                r['query_adduct'] = adduct_label
                r['adduct'] = adduct_label
                r['observed_mass'] = observed_mass
                r['neutral_mass'] = neutral_mass

            all_results.extend(results)
            query_id += 1

        return all_results

    # ─────────────────────────────────────────────
    # FORMULA SEARCH
    # ─────────────────────────────────────────────

    def search_by_formula(
        self,
        formula: str,
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:

        formula_normalized = formula.strip().upper().replace(' ', '')

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = '''
            SELECT 
                source_database,
                source_id,
                name,
                formula,
                exact_mass,
                cas
            FROM compounds
            WHERE UPPER(REPLACE(formula, ' ', '')) = ?
        '''

        params = [formula_normalized]

        if source_filter:
            placeholders = ','.join('?' * len(source_filter))
            query += f' AND source_database IN ({placeholders})'
            params.extend(source_filter)

        query += ' ORDER BY exact_mass ASC'

        if max_results is not None:
            query += f' LIMIT {max_results}'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'source': row['source_database'],
                'source_id': row['source_id'],
                'name': row['name'],
                'formula': row['formula'] if row['formula'] else 'N/A',
                'cas': row['cas'] if row['cas'] else '',
                'exact_mass': round(row['exact_mass'], 4)
            })

        conn.close()
        return results

    # ─────────────────────────────────────────────
    # DATABASE STATS
    # ─────────────────────────────────────────────

    def get_stats(self) -> Dict:

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM compounds')
        total = cursor.fetchone()[0]

        cursor.execute(
            'SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database')
        by_source = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute('SELECT MIN(exact_mass), MAX(exact_mass) FROM compounds')
        min_mass, max_mass = cursor.fetchone()

        conn.close()

        return {
            'total_compounds': total,
            'by_source': by_source,
            'min_mass': round(min_mass, 4) if min_mass else None,
            'max_mass': round(max_mass, 4) if max_mass else None
        }