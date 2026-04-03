"""
Mass Search Engine v4
=====================

Performance fixes:
- Persistent SQLite connection (no reconnect per query)
- Formula stored and queried pre-normalized → idx_formula index actually used
- WAL mode for better read concurrency
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Literal

DB_FILE = "database/compounds.db"

ION_ADJUSTMENTS = {
    'positive':  1.007276,
    'negative': -1.007276,
    'neutral':   0.0,
}


def normalize_formula(formula: str) -> str:
    if not formula:
        return ''
    return formula.strip().upper().replace(' ', '')


class SearchEngine:

    def __init__(self, db_path: str = DB_FILE):
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found at: {db_path}\n"
                f"Please run: python scripts/build_database_v5.py"
            )
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")
        self.conn.execute("PRAGMA temp_store=MEMORY")

    # ─────────────────────────────────────────────
    # MASS SEARCH
    # ─────────────────────────────────────────────

    def search_by_mass(
        self,
        target_mass: float,
        tolerance: float = 0.5,
        ion_mode: Literal['positive', 'negative', 'neutral'] = 'neutral',
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        adduct_delta: Optional[float] = None,
    ) -> List[Dict]:

        # Use exact adduct delta if provided, otherwise fall back to generic ion mode offset
        if adduct_delta is not None:
            neutral_mass = target_mass - adduct_delta
        else:
            neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)
        lower        = neutral_mass - tolerance
        upper        = neutral_mass + tolerance

        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey,
                   ABS(exact_mass - ?)             AS mass_error,
                   ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
            FROM compounds
            WHERE exact_mass BETWEEN ? AND ?
        '''
        params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        query += ' ORDER BY mass_error ASC'
        if max_results:
            query += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(query, params).fetchall()

        return [{
            'source':        row['source_database'],
            'source_id':     row['source_id'],
            'name':          row['name'],
            'formula':       row['formula'] or 'N/A',
            'cas':           row['cas'] or '',
            'inchikey':      row['inchikey'] or '',
            'neutral_mass':  round(row['exact_mass'], 6),
            'observed_mass': round(target_mass, 6),
            'mass_error':    round(row['mass_error'], 6),
            'ppm_error':     round(row['ppm_error'], 3),
            'ion_mode':      ion_mode,
        } for row in rows]

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

        for query_id, (observed_mass, adduct_delta, adduct_label) in enumerate(mass_adduct_pairs):
            # Use exact adduct delta directly
            neutral_mass = observed_mass - adduct_delta
            lower        = neutral_mass - tolerance
            upper        = neutral_mass + tolerance

            query = '''
                SELECT source_database, source_id, name, formula,
                       exact_mass, cas, inchikey,
                       ABS(exact_mass - ?)             AS mass_error,
                       ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
                FROM compounds
                WHERE exact_mass BETWEEN ? AND ?
            '''
            params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

            if source_filter:
                query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
                params.extend(source_filter)

            query += f' ORDER BY mass_error ASC LIMIT {int(max_results_per_query)}'

            rows = self.conn.execute(query, params).fetchall()

            for row in rows:
                all_results.append({
                    'query_id':      query_id,
                    'query_mass':    observed_mass,
                    'query_adduct':  adduct_label,
                    'adduct':        adduct_label,
                    'source':        row['source_database'],
                    'source_id':     row['source_id'],
                    'name':          row['name'],
                    'formula':       row['formula'] or 'N/A',
                    'cas':           row['cas'] or '',
                    'inchikey':      row['inchikey'] or '',
                    'neutral_mass':  round(neutral_mass, 6),
                    'observed_mass': round(observed_mass, 6),
                    'mass_error':    round(row['mass_error'], 6),
                    'ppm_error':     round(row['ppm_error'], 3),
                    'ion_mode':      'positive' if adduct_delta > 0 else
                                     'negative' if adduct_delta < 0 else 'neutral',
                })

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

        formula_norm = normalize_formula(formula)

        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE formula_normalized = ?
        '''
        params = [formula_norm]

        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        query += ' ORDER BY exact_mass ASC'
        if max_results:
            query += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(query, params).fetchall()

        return [{
            'source':     row['source_database'],
            'source_id':  row['source_id'],
            'name':       row['name'],
            'formula':    row['formula'] or 'N/A',
            'cas':        row['cas'] or '',
            'inchikey':   row['inchikey'] or '',
            'exact_mass': round(row['exact_mass'], 6),
        } for row in rows]

    # ─────────────────────────────────────────────
    # MS2 PATTERN ANALYSIS
    # ─────────────────────────────────────────────

    def search_ms2(
        self,
        fragment_masses: list,
        tolerance: float = 0.02,
        adduct_delta: float = 1.007276,
        source_filter=None,
        max_candidates: int = 20,
    ) -> dict:
        """
        MS2 fragment pattern analysis.

        For each fragment mass, search the DB for matching compounds.
        Then score candidates by how many fragments they explain,
        with average ppm as tiebreaker.

        Returns a dict with:
          - candidates: ranked list of compounds with fragment match details
          - neutral_losses: detected neutral losses between fragment pairs
          - fragment_results: per-fragment search results
        """

        NEUTRAL_LOSSES = {
            162.0528: "hexose loss (−C6H10O5)",
            146.0579: "deoxyhexose loss (−C6H10O4)",
            132.0423: "pentose loss (−C5H8O4)",
            308.1107: "hexose + deoxyhexose loss",
            324.1056: "dihexose loss",
            176.0477: "glucuronic acid loss",
            80.0262:  "sulfate loss (−SO3)",
            18.0106:  "water loss (−H2O)",
            28.0101:  "CO loss",
            44.0262:  "CO2 loss",
            42.0106:  "acetyl loss",
            120.0423: "hexose − H2O loss",
            272.0685: "caffeic acid hexose loss",
            206.0528: "hexose + H2O loss",
        }
        LOSS_TOL = 0.02  # Da tolerance for neutral loss matching

        # 1. Search each fragment
        fragment_results = []
        for frag in fragment_masses:
            hits = self.search_by_mass(
                target_mass=frag,
                tolerance=tolerance,
                ion_mode='positive' if adduct_delta >= 0 else 'negative',
                source_filter=source_filter,
                max_results=50,
                adduct_delta=adduct_delta,
            )
            fragment_results.append({
                'mass': frag,
                'hits': hits,
            })

        # 2. Detect neutral losses between all fragment pairs
        sorted_masses = sorted(fragment_masses, reverse=True)
        detected_losses = []
        for i in range(len(sorted_masses)):
            for j in range(i + 1, len(sorted_masses)):
                diff = round(sorted_masses[i] - sorted_masses[j], 4)
                for loss_mass, loss_name in NEUTRAL_LOSSES.items():
                    if abs(diff - loss_mass) <= LOSS_TOL:
                        detected_losses.append({
                            'from_mass': sorted_masses[i],
                            'to_mass':   sorted_masses[j],
                            'loss_da':   diff,
                            'loss_name': loss_name,
                        })

        # 3. Score candidates — key = (source, source_id)
        candidate_scores = {}

        for fi, frag_result in enumerate(fragment_results):
            for hit in frag_result['hits']:
                key = (hit['source'], hit['source_id'])
                if key not in candidate_scores:
                    candidate_scores[key] = {
                        'source':      hit['source'],
                        'source_id':   hit['source_id'],
                        'name':        hit['name'],
                        'formula':     hit['formula'],
                        'inchikey':    hit['inchikey'],
                        'exact_mass':  hit['neutral_mass'],
                        'fragment_matches': [],
                        'ppm_errors':  [],
                    }
                candidate_scores[key]['fragment_matches'].append({
                    'fragment_mass': frag_result['mass'],
                    'matched_mass':  hit['neutral_mass'],
                    'mass_error':    hit['mass_error'],
                    'ppm_error':     hit['ppm_error'],
                })
                candidate_scores[key]['ppm_errors'].append(abs(hit['ppm_error']))

        # 4. Rank: fragments explained descending, then avg ppm ascending
        n_frags = len(fragment_masses)
        candidates = list(candidate_scores.values())
        for c in candidates:
            c['fragments_explained'] = len(c['fragment_matches'])
            c['fragments_total']     = n_frags
            c['coverage_pct']        = round(len(c['fragment_matches']) / n_frags * 100, 1)
            c['avg_ppm']             = round(
                sum(c['ppm_errors']) / len(c['ppm_errors']), 3
            ) if c['ppm_errors'] else 999

        candidates.sort(key=lambda c: (-c['fragments_explained'], c['avg_ppm']))
        candidates = candidates[:max_candidates]

        return {
            'candidates':       candidates,
            'neutral_losses':   detected_losses,
            'fragment_results': fragment_results,
            'n_fragments':      n_frags,
        }

    # ─────────────────────────────────────────────
    # NAME SEARCH
    # ─────────────────────────────────────────────

    def search_by_name(
        self,
        query: str,
        source_filter: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Case-insensitive substring search on compound name.
        Returns compounds whose name contains the query string.
        """
        query_str = f'%{query.strip()}%'

        sql = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE name LIKE ? COLLATE NOCASE
        '''
        params = [query_str]

        if source_filter:
            sql += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        # Order by name length ascending so exact/short matches float to top
        sql += ' ORDER BY LENGTH(name) ASC'
        sql += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(sql, params).fetchall()

        return [{
            'source':     row['source_database'],
            'source_id':  row['source_id'],
            'name':       row['name'],
            'formula':    row['formula'] or 'N/A',
            'cas':        row['cas'] or '',
            'inchikey':   row['inchikey'] or '',
            'exact_mass': round(row['exact_mass'], 6) if row['exact_mass'] else None,
        } for row in rows]

    # ─────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────

    def get_stats(self) -> Dict:
        total     = self.conn.execute('SELECT COUNT(*) FROM compounds').fetchone()[0]
        by_source = dict(self.conn.execute(
            'SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database'
        ).fetchall())
        min_m, max_m = self.conn.execute(
            'SELECT MIN(exact_mass), MAX(exact_mass) FROM compounds'
        ).fetchone()

        return {
            'total_compounds': total,
            'by_source':       by_source,
            'min_mass':        round(min_m, 4) if min_m else None,
            'max_mass':        round(max_m, 4) if max_m else None,
        }

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass