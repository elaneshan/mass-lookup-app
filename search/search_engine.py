"""
Mass Search Engine v4
=====================

OVERVIEW:
This file contains the core backend search logic for a mass spectrometry
compound identification system.

The engine supports:
1. Searching compounds by exact mass
2. Searching compounds by molecular formula
3. Searching compounds by compound name
4. Batch searching multiple masses at once
5. MS2 fragmentation analysis for flavonoid identification

The data is stored in a SQLite database containing compound metadata
from multiple chemical databases (HMDB, ChEBI, LipidMaps, etc).

Performance Optimizations:
- Persistent SQLite connection (avoids reconnecting every query)
- WAL mode enabled for better concurrent reads
- Formula normalization for indexed lookups
- In-memory temp storage for faster operations
"""

# this is where the code talks to the db:
# handles the connecttion, the searchingl the actual chem calculations; all performance
# optimizations and formating


import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Literal

# Path to the local SQLite database containing compound data
DB_FILE = "database/compounds.db"

# Mass adjustments for different ionization modes in mass spectrometry.
# These values are used to convert observed ion masses back into neutral masses.
#
# Positive mode usually adds a proton (+H)
# Negative mode usually removes a proton (-H)
# Neutral mode means no adjustment
ION_ADJUSTMENTS = {
    'positive':  1.007276,
    'negative': -1.007276,
    'neutral':   0.0,
}

#the api handked the aducts which was user facing
# the search engine handles the backend calc facing corrections

def normalize_formula(formula: str) -> str:
    """
    Normalize molecular formulas for consistent database searching.

    WHY THIS EXISTS:
    Chemical formulas can be written inconsistently:
        "C6H12O6"
        " c6 h12 o6 "
        "c6h12o6"

    This function standardizes them into a consistent format so
    indexed lookups work correctly.

    STEPS:
    1. Remove leading/trailing whitespace
    2. Convert to uppercase
    3. Remove spaces

    Example:
        " c6 h12 o6 " → "C6H12O6"
    """
    if not formula:
        return ''
    return formula.strip().upper().replace(' ', '')


class SearchEngine:
    """
    Main search engine class responsible for all compound lookup operations.

    This class:
    - Maintains a persistent database connection
    - Executes optimized SQL queries
    - Handles mass calculations
    - Performs MS2 fragmentation analysis
    - Formats results into frontend-friendly dictionaries

    everythign is abstacted from the API in terms of SQL details
    """

    def __init__(self, db_path: str = DB_FILE):
        """
        Initialize the search engine and database connection.

        One important optimization here is that the database connection
        is created ONCE and reused for all queries instead of reconnecting
        every request. This significantly improves performance.
        """

        # Validate that the database file actually exists
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found at: {db_path}\n"
                f"Please run: python scripts/build_database_v5.py"
            )

        # Create persistent SQLite connection; making sure to allow for concurrent threads
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

        # Return rows as dictionary-like objects instead of tuples
        # This allows accessing columns by name (row['name'])
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for better read concurrency
        # WAL = Write Ahead Logging
        self.conn.execute("PRAGMA journal_mode=WAL")

        # NORMAL synchronous mode improves speed while still being reliable
        self.conn.execute("PRAGMA synchronous=NORMAL")

        # Increase cache size for better query performance
        self.conn.execute("PRAGMA cache_size=-64000")

        # Store temporary tables in memory instead of disk
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
        """
        Search compounds by observed mass.

        THIS IS ONE OF THE CORE FEATURES OF THE SYSTEM.

        WORKFLOW:
        1. Convert observed ion mass → neutral mass
        2. Create a search window using tolerance
        3. Query database for compounds in that mass range
        4. Calculate mass error + ppm error
        5. Return formatted results

        PARAMETERS:
        - target_mass:
            Observed mass from mass spectrometry

        - tolerance:
            Allowed mass deviation window

        - ion_mode:
            Determines how to convert ion mass back to neutral mass

        - source_filter:
            Optional filtering by database source

        - max_results:
            Limit number of returned compounds

        - adduct_delta:
            Custom ion adjustment override
        """

        # If a custom adduct adjustment is provided, use it
        # Otherwise fall back to the predefined ion mode adjustments
        if adduct_delta is not None:
            neutral_mass = target_mass - adduct_delta
        else:
            neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)

        # Create search boundaries using tolerance
        lower = neutral_mass - tolerance
        upper = neutral_mass + tolerance

        # SQL query:
        #
        # ABS(exact_mass - ?) calculates absolute mass error
        #
        # ppm_error calculates:
        # (mass difference / true mass) * 1e6
        #
        # PPM is commonly used in mass spectrometry because
        # it scales error proportionally across mass ranges.
        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey,
                   ABS(exact_mass - ?)             AS mass_error,
                   ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
            FROM compounds
            WHERE exact_mass BETWEEN ? AND ?
        '''

        # Query parameters passed safely into SQL
        # Prevents SQL injection
        params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

        # Optional source filtering
        # Example:
        # WHERE source_database IN ('HMDB', 'ChEBI')
        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        # Sort best matches first
        query += ' ORDER BY mass_error ASC'

        # Apply result limit if provided
        if max_results:
            query += f' LIMIT {int(max_results)}'

        # Execute query and fetch all matching rows
        rows = self.conn.execute(query, params).fetchall()

        # Debug logging for first few rows
        # Helpful during development/testing
        for r in rows[:3]:
            print("DEBUG SQL:", dict(r))

        # Convert database rows into clean API response format
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
            'ppm_error':     row['ppm_error'],
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
        """
        Run multiple mass searches in one operation.

        WHY THIS EXISTS:
        Instead of sending many separate requests,
        users can submit multiple masses at once.

        This is useful for:
        - High throughput analysis
        - Bulk compound screening
        - MS workflows processing many peaks
        """

        # Stores combined results from all queries
        all_results = []

        # enumerate() gives:
        # query_id = index
        # observed_mass/adduct info = tuple contents
        for query_id, (observed_mass, adduct_delta, adduct_label) in enumerate(mass_adduct_pairs):

            # Convert observed ion mass → neutral mass
            neutral_mass = observed_mass - adduct_delta

            # Create search range
            lower        = neutral_mass - tolerance
            upper        = neutral_mass + tolerance

            # SQL query identical to single search
            query = '''
                SELECT source_database, source_id, name, formula,
                       exact_mass, cas, inchikey,
                       ABS(exact_mass - ?)             AS mass_error,
                       ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
                FROM compounds
                WHERE exact_mass BETWEEN ? AND ?
            '''

            params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

            # Optional source filtering
            if source_filter:
                query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
                params.extend(source_filter)

            # Limit results per query
            query += f' ORDER BY mass_error ASC LIMIT {int(max_results_per_query)}'

            rows = self.conn.execute(query, params).fetchall()

            # Format each result and attach metadata
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
                    'ppm_error':     row['ppm_error'],

                    # Determine ion mode automatically
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
        """
        Search compounds by molecular formula.

        EXAMPLE:
            Input:
                C6H12O6

            Returns:
                Glucose
                Fructose
                Other isomers

        IMPORTANT:
        Formula is normalized first so indexing works correctly.
        """

        # Standardize formula formatting
        formula_norm = normalize_formula(formula)

        # Search pre-normalized indexed column
        # This makes lookup much faster than normalizing at query time
        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE formula_normalized = ?
        '''

        params = [formula_norm]

        # Optional source filtering
        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        # Sort by exact mass
        query += ' ORDER BY exact_mass ASC'

        # Optional limit
        if max_results:
            query += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(query, params).fetchall()

        # Convert rows into API-friendly format
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
    # NAME SEARCH
    # ─────────────────────────────────────────────

    def search_by_name(
        self,
        query: str,
        source_filter: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Search compounds by name using SQL LIKE matching.

        EXAMPLE:
            Query:
                "glucose"

            SQL pattern:
                %glucose%

        This allows partial matching:
            glucose
            D-glucose
            alpha-glucose
        """

        # Wildcards for partial SQL matching
        query_str = f'%{query.strip()}%'

        sql = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE name LIKE ? COLLATE NOCASE
        '''

        params = [query_str]

        # Optional source filtering
        if source_filter:
            sql += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        # Shorter names first
        # Often produces cleaner/more relevant results
        sql += ' ORDER BY LENGTH(name) ASC'

        # Limit results
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
    # MS2 PATTERN ANALYSIS
    # ─────────────────────────────────────────────

    """
    THIS SECTION IS THE MOST SCIENTIFICALLY COMPLEX PART OF THE SYSTEM.

    PURPOSE:
    Analyze fragmentation patterns from tandem mass spectrometry (MS2)
    to predict likely flavonoid structures.

    The algorithm:
    1. Detects neutral losses
    2. Identifies sugar chains
    3. Matches aglycone fragments
    4. Predicts compound composition
    5. Searches database for supporting evidence

    This essentially mimics expert interpretation of MS2 spectra.
    """

    # ── Neutral loss library (from PI's flavonoid reference table) ────────────
    #
    # Neutral losses represent molecular fragments commonly lost during
    # fragmentation in mass spectrometry.
    #
    # Example:
    # A glucose group often produces a loss around 162 Da.
    #
    # Format:
    # loss_mass: (specific_name, category)
    NEUTRAL_LOSSES = {
        # Sugars
        162.0528: ("hexose",                  "Hexose"),
        146.0579: ("rhamnoside",              "Deoxyhexose"),
        132.0422: ("pentose",                 "Pentose"),
        324.1056: ("sophoroside",             "Hexose Disaccharide"),
        308.1107: ("rutinoside",              "Hexose Deoxyhexose"),

        # Acylated sugars
        204.0634: ("acetyl glucoside",        "Acyl Hexose"),
        188.0684: ("acetyl rhamnoside",       "Acyl Deoxyhexose"),
        308.0896: ("coumaroyl glucoside",     "Acyl Hexose"),
        292.0947: ("coumaroyl rhamnoside",    "Acyl Deoxyhexose"),
        246.0739: ("diacetyl glucoside",      "Acyl Hexose"),
        324.0845: ("caffeoyl hexose",         "Acyl Hexose"),
        248.0532: ("malonyl glucoside",       "Acyl Hexose"),  # NEW
        176.0320: ("glucuronide",             "Uronic Acid"),

        # Acyl groups
        42.0105:  ("acetyl",                  "Acyl Moiety"),
        102.0105: ("benzoyl",                 "Acyl Moiety"),
        162.0317: ("caffeoyl",                "Acyl Moiety"),
        130.0418: ("cinnamyl",                "Acyl Moiety"),
        146.0368: ("coumaroyl",               "Acyl Moiety"),
        176.0473: ("feruloyl",                "Acyl Moiety"),
        152.0109: ("galloyl",                 "Acyl Moiety"),
        86.0368:  ("hydroxyisobutyryl",       "Acyl Moiety"),
        86.0003:  ("malonyl",                 "Acyl Moiety"),
        166.0993: ("menthiafoloyl",           "Acyl Moiety"),
        160.0524: ("methoxycinnamyl",         "Acyl Moiety"),
        84.0575:  ("methylbutyryl/pentanoyl", "Acyl Moiety"),
        166.0266: ("methylgalloyl",           "Acyl Moiety"),
        128.0473: ("methylglutaryl",          "Acyl Moiety"),
        71.9847:  ("oxalyl",                  "Acyl Moiety"),
        206.0579: ("sinapoyl",                "Acyl Moiety"),
        150.0317: ("vanilloyl",               "Acyl Moiety"),
    }

    # Allowed error tolerance for neutral loss matching
    NEUTRAL_LOSS_TOLERANCE = 0.02  # Da

    # ── Flavonoid aglycone reference table ────────────────────────────────────
    #
    # Aglycones are the core flavonoid structures remaining after sugars
    # are removed.
    #
    # These serve as reference fingerprints for identification.
    FLAVONOID_AGLYCONES = [
        {"name": "pelargonidin", "class": "anthocyanin", "positive_mz": 271.0601, "negative_mz": 269.0455},
        {"name": "cyanidin",     "class": "anthocyanin", "positive_mz": 287.0550, "negative_mz": 285.0405},
        {"name": "delphinidin",  "class": "anthocyanin", "positive_mz": 303.0499, "negative_mz": 301.0354},
        {"name": "peonidin",     "class": "anthocyanin", "positive_mz": 301.0707, "negative_mz": 299.0561},
        {"name": "petunidin",    "class": "anthocyanin", "positive_mz": 317.0656, "negative_mz": 315.0510},
        {"name": "malvidin",     "class": "anthocyanin", "positive_mz": 331.0812, "negative_mz": 329.0667},

        {"name": "kaempferol",   "class": "flavonol", "positive_mz": 287.0550, "negative_mz": 285.0405},
        {"name": "quercetin",    "class": "flavonol", "positive_mz": 303.0499, "negative_mz": 301.0354},
        {"name": "myricetin",    "class": "flavonol", "positive_mz": 319.0448, "negative_mz": 317.0303},
        {"name": "isorhamnetin", "class": "flavonol", "positive_mz": 317.0656, "negative_mz": 315.0510},
    ]

    # Allowed error tolerance for aglycone matching
    AGLYCONE_TOLERANCE = 0.02

    # Database priority ranking
    # Lower number = higher confidence/preference
    SOURCE_PRIORITY = {
        "HMDB": 0,
        "ChEBI": 1,
        "LipidMaps": 2,
        "NPAtlas": 3
    }

    def _match_aglycone(self, observed_mz: float, adduct: str) -> list:
        """
        Match an observed fragment mass against known flavonoid aglycones.

        This helps identify the flavonoid backbone structure.

        INTERVIEW TALKING POINT:
        This method applies domain-specific chemistry rules.
        Different ionization modes are only compatible with certain
        flavonoid classes.
        """

        print(" ENTERING _match_aglycone", observed_mz, adduct)

        # Determine whether spectrum is positive or negative ion mode
        is_negative = adduct in (
            "[M-H]-",
            "[M+Cl]-",
            "[M+FA-H]-",
            "[M-2H]-",
            "[M-2H]2-"
        )

        mz_key = "negative_mz" if is_negative else "positive_mz"

        # Helper function:
        # Validates whether a flavonoid class is compatible
        # with the given adduct/ionization type
        def is_valid_class(ag_class: str) -> bool:

            # Anthocyanins mainly observed as [M]+
            if adduct in ("[M]+",):
                return ag_class == "anthocyanin"

            # Flavonols typically observed in positive mode
            if adduct in ("[M+H]+", "[M+Na]+", "[M+K]+", "[M+NH4]+"):
                return ag_class == "flavonol"

            # Flavonols commonly observed in negative mode too
            if adduct in ("[M-H]-", "[M+Cl]-", "[M+FA-H]-"):
                return ag_class == "flavonol"

            # Anthocyanins can appear in doubly deprotonated states
            if adduct in ("[M-2H]-", "[M-2H]2-"):
                return ag_class == "anthocyanin"

            return True

        matches = []

        # Iterate through all known aglycones
        for ag in self.FLAVONOID_AGLYCONES:

            # Skip chemically incompatible classes
            if not is_valid_class(ag["class"]):
                continue

            ref_mz = ag[mz_key]

            if ref_mz is None:
                continue

            # Calculate absolute error
            err = abs(observed_mz - ref_mz)

            # Accept match if within tolerance
            if err <= self.AGLYCONE_TOLERANCE:

                # Convert error into ppm
                ppm = err / ref_mz * 1e6

                print("DEBUG AG:", {
                    "observed": observed_mz,
                    "ref": ref_mz,
                    "err": err,
                    "ppm": ppm
                })

                matches.append({
                    **ag,
                    "ppm_error": ppm,
                    "observed_mz": observed_mz
                })

        # Best ppm match first
        matches.sort(key=lambda x: x["ppm_error"])

        return matches

    def search_ms2(
        self,
        fragment_masses: list,
        adduct_delta: float = 1.007276,
        tolerance: float = 0.02,
        source_filter=None,
        max_candidates: int = 20,
        top_n_per_fragment: int = 50,
        adduct: str = "[M+H]+",
    ) -> dict:
        """
        MAIN MS2 ANALYSIS PIPELINE

        HIGH LEVEL FLOW:
        1. Clean and sort fragments
        2. Detect neutral losses
        3. Detect sequential fragmentation ladders
        4. Infer sugar composition
        5. Match aglycone
        6. Predict compound structure
        7. Search database for supporting candidates

        This method combines:
        - chemistry knowledge
        - pattern matching
        - database searching
        - scoring/ranking
        """

        # Clean input:
        # - convert to floats
        # - remove duplicates
        # - round for consistency
        # - sort ascending
        fragments = sorted(set(round(float(m), 6) for m in fragment_masses if float(m) > 0))

        # Handle empty input safely
        if not fragments:
            return {
                "candidates": [],
                "neutral_losses": [],
                "fragment_results": [],
                "n_fragments": 0,
                "ladder_annotation": None,
            }

        n_fragments = len(fragments)

        # ── Step 1: detect pairwise neutral losses ─────────────────────────────

        detected_losses = []

        # Compare every fragment against every larger fragment
        for i, f1 in enumerate(fragments):
            for f2 in fragments[i + 1:]:

                # Difference between fragments
                diff = abs(f2 - f1)

                # Compare against known neutral loss library
                for loss_mass, (loss_name, loss_class) in self.NEUTRAL_LOSSES.items():

                    # Match if within tolerance
                    if abs(diff - loss_mass) <= self.NEUTRAL_LOSS_TOLERANCE:

                        detected_losses.append({
                            "from_mass":  round(max(f1, f2), 6),
                            "to_mass":    round(min(f1, f2), 6),
                            "loss_da":    round(diff, 4),
                            "loss_name":  loss_name,
                            "loss_class": loss_class,

                            # ppm accuracy metric
                            "ppm_error":  round(abs(diff - loss_mass) / loss_mass * 1e6, 2),
                        })

        # Remove duplicate loss detections
        seen = set()
        unique_losses = []

        for l in detected_losses:
            k = (l["from_mass"], l["to_mass"], l["loss_name"])

            if k not in seen:
                seen.add(k)
                unique_losses.append(l)

        # ── Step 2: sequential fragmentation ladder detection ─────────────────

        frag_list = sorted(fragments)
        sequential_losses = []

        # Analyze adjacent fragments only
        for i in range(len(frag_list) - 1):

            lo, hi = frag_list[i], frag_list[i + 1]
            diff = hi - lo

            best_match = None
            best_err = float("inf")

            # Find best matching neutral loss
            for loss_mass, (loss_name, loss_class) in self.NEUTRAL_LOSSES.items():

                err = abs(diff - loss_mass)

                # Keep best matching loss
                if err <= self.NEUTRAL_LOSS_TOLERANCE and err < best_err:

                    best_err = err

                    best_match = (
                        loss_mass,
                        loss_name,
                        loss_class,
                        round(diff, 4),
                        round(err / loss_mass * 1e6, 2)
                    )

            if best_match:
                sequential_losses.append({
                    "from_mass":  round(hi, 6),
                    "to_mass":    round(lo, 6),
                    "loss_mass":  best_match[0],
                    "loss_name":  best_match[1],
                    "loss_class": best_match[2],
                    "loss_da":    best_match[3],
                    "ppm_error":  best_match[4],
                })

        # ── Step 3: infer sugar composition ───────────────────────────────────

        """
        Example output:
            "2× hexose + 1× caffeoyl"

        This reconstructs likely glycoside composition.
        """

        loss_class_counts = {}
        loss_name_counts  = {}

        # Count occurrences of each loss
        for sl in sequential_losses:

            cls  = sl["loss_class"]
            name = sl["loss_name"]

            loss_class_counts[cls]  = loss_class_counts.get(cls, 0) + 1
            loss_name_counts[name]  = loss_name_counts.get(name, 0) + 1

        # Build readable composition string
        composition_parts = []

        for name, count in sorted(loss_name_counts.items(), key=lambda x: -x[1]):
            composition_parts.append(f"{count}× {name}")

        composition_str = " + ".join(composition_parts) if composition_parts else "unknown sugars"

        dominant_class = max(loss_class_counts, key=loss_class_counts.get) if loss_class_counts else None
        total_losses   = len(sequential_losses)

        # ── Step 4: aglycone matching ─────────────────────────────────────────

        # Smallest fragment is typically the aglycone core
        aglycone_frag    = frag_list[0]

        # Match against reference library
        aglycone_matches = self._match_aglycone(aglycone_frag, adduct)

        # Best ppm match
        best_ppm = aglycone_matches[0]["ppm_error"] if aglycone_matches else None

        # Determine ambiguous/isobaric matches
        isobar_threshold  = 0.5

        isobars = [
            m for m in aglycone_matches
            if best_ppm is not None and abs(m["ppm_error"] - best_ppm) <= isobar_threshold
        ]

        non_isobars = [
            m for m in aglycone_matches
            if m not in isobars
        ]

        best_aglycone = isobars[0] if isobars else None

        # Whether multiple compounds match equally well
        aglycone_ambiguous = len(isobars) > 1

        isobar_classes = list({m["class"] for m in isobars})
        isobar_names   = [m["name"] for m in isobars]

        has_anthocyanin = any(m["class"] == "anthocyanin" for m in isobars)
        has_flavonol    = any(m["class"] == "flavonol" for m in isobars)

        # Fallback:
        # If no aglycone match exists, search DB directly by mass
        if not best_aglycone:

            db_hits = self.search_by_mass(
                target_mass=aglycone_frag,
                tolerance=tolerance,
                adduct_delta=adduct_delta,
                source_filter=source_filter,
                max_results=100,
            )

            # Choose best database hit
            best_db = min(
                db_hits,
                key=lambda h: (
                    self.SOURCE_PRIORITY.get(h["source"], 99),
                    h["ppm_error"]
                )
            ) if db_hits else None

        else:
            best_db = None

        # Predict original neutral parent mass
        predicted_parent_neutral = round(frag_list[-1] - adduct_delta, 4)

        # ── Build prediction summary ──────────────────────────────────────────

        if best_aglycone and composition_parts:

            aglycone_label = "/".join(isobar_names) if aglycone_ambiguous else best_aglycone["name"]

            prediction = f"{aglycone_label} + {composition_str}"

            confidence = "high" if total_losses >= 3 and not aglycone_ambiguous else "moderate"

        elif best_aglycone:

            aglycone_label = "/".join(isobar_names) if aglycone_ambiguous else best_aglycone["name"]

            prediction = f"{aglycone_label} glycoside (sugar composition unclear)"

            confidence = "low"

        elif best_db and composition_parts:

            prediction = f"{best_db['name']} + {composition_str}"

            confidence = "low"

        else:

            prediction = "Unknown — aglycone not matched to flavonoid library"

            confidence = "none"

        # Final structured annotation object
        ladder_annotation = {
            "predicted_structure": prediction,
            "confidence": confidence,

            "aglycone_mass": round(aglycone_frag, 4),
            "aglycone_matches": isobars,
            "aglycone_name": "/".join(isobar_names) if isobars else (best_db["name"] if best_db else None),
            "aglycone_formula": None,
            "aglycone_ppm": best_ppm,
            "aglycone_ambiguous": aglycone_ambiguous,
            "aglycone_isobar_names": isobar_names,
            "aglycone_classes": isobar_classes,
            "has_anthocyanin": has_anthocyanin,
            "has_flavonol": has_flavonol,

            "aglycone_source": None,
            "aglycone_source_id": None,

            "composition_str": composition_str,
            "composition_parts": composition_parts,
            "loss_class_counts": loss_class_counts,
            "loss_name_counts": loss_name_counts,
            "sequential_losses": sequential_losses,
            "total_sequential_losses": total_losses,
            "dominant_loss_class": dominant_class,

            "predicted_parent_neutral": predicted_parent_neutral,
            "ladder_length": len(frag_list),
        }

        # ── Step 5: database candidate search ─────────────────────────────────

        """
        After predicting structure patterns,
        the engine searches database compounds that support the fragments.
        """

        candidate_map: dict[tuple, dict] = {}
        fragment_results = []

        for frag in fragments:

            # Search DB for each fragment
            hits = self.search_by_mass(
                target_mass=frag,
                tolerance=tolerance,
                adduct_delta=adduct_delta,
                source_filter=source_filter,
                max_results=top_n_per_fragment,
            )

            fragment_results.append({
                "mass": frag,
                "hits": len(hits)
            })

            # Deduplicate candidates
            for h in hits:

                key = (
                    h["source"],
                    h["source_id"],
                    h["name"],
                    h.get("formula", "")
                )

                if key not in candidate_map:

                    candidate_map[key] = {
                        "source":        h["source"],
                        "source_id":     h["source_id"],
                        "name":          h["name"],
                        "formula":       h.get("formula", ""),
                        "db_mass":       h["neutral_mass"],
                        "seed_fragment": frag,
                        "seed_ppm":      h["ppm_error"],
                        "seed_mass_err": h["mass_error"],
                    }

        scored = []

        # Score/rank candidates by fragment coverage
        for key, cand in candidate_map.items():

            db_mass      = cand["db_mass"]
            expected_ion = db_mass + adduct_delta

            direct_matches = set()

            # Count how many fragments match this candidate
            for frag in fragments:
                if abs(frag - expected_ion) <= tolerance:
                    direct_matches.add(frag)

            n_explained  = len(direct_matches)

            # Coverage percentage
            coverage_pct = round(n_explained / n_fragments * 100, 1)

            scored.append({
                "source":              cand["source"],
                "source_id":           cand["source_id"],
                "name":                cand["name"],
                "formula":             cand["formula"],
                "fragments_explained": n_explained,
                "coverage_pct":        coverage_pct,
                "avg_ppm":             cand["seed_ppm"],

                "fragment_matches": [
                    {
                        "fragment_mass": f,
                        "ppm_error":     cand["seed_ppm"],
                        "mass_error":    cand["seed_mass_err"],
                        "matched_mass":  db_mass,
                        "match_type":    "direct",
                    }
                    for f in sorted(direct_matches, reverse=True)
                ],

                "unmatched_fragments": sorted(
                    [f for f in fragments if f not in direct_matches],
                    reverse=True
                ),
            })

        # Rank best candidates first
        scored.sort(key=lambda x: (-x["fragments_explained"], x["avg_ppm"]))

        # Final API response
        return {
            "n_fragments":       n_fragments,
            "fragment_results":  fragment_results,
            "candidates":        scored[:max_candidates],
            "neutral_losses":    unique_losses,
            "ladder_annotation": ladder_annotation,
        }

    # ─────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """
        Return summary statistics about the database.

        Useful for:
        - admin dashboards
        - health checks
        - analytics
        """

        # Total number of compounds
        total = self.conn.execute(
            'SELECT COUNT(*) FROM compounds'
        ).fetchone()[0]

        # Count compounds grouped by source database
        by_source = dict(self.conn.execute(
            'SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database'
        ).fetchall())

        # Get overall mass range
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
        """
        Cleanup method.

        Ensures database connection closes properly
        when object is destroyed.
        """

        try:
            self.conn.close()
        except Exception:
            pass