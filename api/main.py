"""
LC-MS Mass Lookup API
=====================

Endpoints:
    GET  /health
    GET  /stats
    GET  /search/mass
    GET  /search/formula
    POST /search/batch

Run locally:
    uvicorn api.main:app --reload --port 8000

Run via Docker:
    docker-compose up
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from api.models import (
    MassResult, CompoundResult, BatchQueryResult,
    StatsResponse, BatchSearchRequest
)
from api.dependencies import get_search_engine

# ─────────────────────────────────────────────
# ADDUCT TABLE
# Maps adduct label → mass delta
# ─────────────────────────────────────────────

ADDUCTS = {
    "[M+H]+":    1.007276,
    "[M+Na]+":   22.989218,
    "[M+K]+":    38.963158,
    "[M+NH4]+":  18.034374,
    "[M-H]-":   -1.007276,
    "[M+Cl]-":   34.969402,
    "neutral":   0.0,
}


def resolve_adduct(adduct_str: str) -> float:
    """Return mass delta for an adduct label. Raises 400 if unknown."""
    delta = ADDUCTS.get(adduct_str)
    if delta is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown adduct '{adduct_str}'. "
                   f"Valid options: {list(ADDUCTS.keys())}"
        )
    return delta


def map_mass_result(r: dict, observed_mass: float, adduct: str) -> MassResult:
    """Convert SearchEngine dict → MassResult Pydantic model."""
    return MassResult(
        source        = r.get("source", ""),
        source_id     = r.get("source_id"),
        name          = r.get("name"),
        formula       = r.get("formula") if r.get("formula") != "N/A" else None,
        cas           = r.get("cas") or None,
        inchikey      = r.get("inchikey") or None,
        exact_mass    = r.get("neutral_mass") or r.get("exact_mass"),
        observed_mass = observed_mass,
        mass_error    = round(r.get("mass_error", 0), 6),
        ppm_error     = round(r.get("ppm_error", 0), 3),
        adduct        = adduct,
        ion_mode      = r.get("ion_mode", "neutral"),
    )


def map_formula_result(r: dict) -> CompoundResult:
    """Convert SearchEngine dict → CompoundResult Pydantic model."""
    return CompoundResult(
        source     = r.get("source", ""),
        source_id  = r.get("source_id"),
        name       = r.get("name"),
        formula    = r.get("formula") if r.get("formula") != "N/A" else None,
        cas        = r.get("cas") or None,
        inchikey   = r.get("inchikey") or None,
        exact_mass = r.get("exact_mass"),
    )


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

app = FastAPI(
    title       = "LC-MS Mass Lookup API",
    description = "Search 494k+ compounds by mass or formula across HMDB, ChEBI, LipidMaps, NPAtlas and more.",
    version     = "1.0.0",
)

# Allow requests from any origin — fine for a lab internal tool
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────
# STARTUP — validate DB exists
# ─────────────────────────────────────────────

@app.on_event("startup")
def startup():
    try:
        se = get_search_engine()
        stats = se.get_stats()
        print(f"✓ Database loaded — {stats['total_compounds']:,} compounds")
        for src, cnt in stats["by_source"].items():
            print(f"    {src:<12} {cnt:>10,}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("   The API will start but all search endpoints will return 503.")


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health():
    """Quick liveness check — returns 200 if API is up."""
    try:
        se    = get_search_engine()
        stats = se.get_stats()
        return {"status": "ok", "compounds": stats["total_compounds"]}
    except Exception:
        return {"status": "degraded", "compounds": 0}


@app.get("/stats", response_model=StatsResponse, tags=["Meta"])
def stats():
    """Database statistics — total compounds, counts per source, mass range."""
    try:
        se = get_search_engine()
        return se.get_stats()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/search/mass", response_model=List[MassResult], tags=["Search"])
def search_by_mass(
    mass:      float = Query(...,  description="Observed m/z value"),
    tolerance: float = Query(0.02, description="Mass tolerance in Da", gt=0, le=5.0),
    adduct:    str   = Query("neutral", description="Adduct mode, e.g. [M+H]+"),
    sources:   Optional[str] = Query(None, description="Comma-separated sources, e.g. HMDB,ChEBI"),
    limit:     int   = Query(20,   description="Max results", gt=0, le=500),
):
    """
    Search compounds by observed mass with adduct correction.

    Examples:
    - `/search/mass?mass=181.071&adduct=[M+H]+&tolerance=0.02`
    - `/search/mass?mass=181.071&adduct=[M+H]+&sources=HMDB,ChEBI&limit=10`
    """
    adduct_delta  = resolve_adduct(adduct)
    source_filter = [s.strip() for s in sources.split(",")] if sources else None

    # Determine ion mode from adduct delta sign
    if adduct_delta > 0:
        ion_mode = "positive"
    elif adduct_delta < 0:
        ion_mode = "negative"
    else:
        ion_mode = "neutral"

    try:
        se      = get_search_engine()
        results = se.search_by_mass(
            target_mass   = mass,
            tolerance     = tolerance,
            ion_mode      = ion_mode,
            source_filter = source_filter,
            max_results   = limit,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return [map_mass_result(r, mass, adduct) for r in results]


@app.get("/search/formula", response_model=List[CompoundResult], tags=["Search"])
def search_by_formula(
    formula: str = Query(..., description="Molecular formula, e.g. C6H12O6"),
    sources: Optional[str] = Query(None, description="Comma-separated sources"),
    limit:   int = Query(100, description="Max results", gt=0, le=500),
):
    """
    Search compounds by exact molecular formula.

    Example:
    - `/search/formula?formula=C6H12O6&sources=HMDB,LipidMaps`
    """
    source_filter = [s.strip() for s in sources.split(",")] if sources else None

    try:
        se      = get_search_engine()
        results = se.search_by_formula(
            formula       = formula,
            source_filter = source_filter,
            max_results   = limit,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return [map_formula_result(r) for r in results]


@app.post("/search/batch", response_model=List[BatchQueryResult], tags=["Search"])
def search_batch(request: BatchSearchRequest):
    """
    Batch mass search — multiple masses × multiple adducts in one request.

    Example body:
    ```json
    {
        "masses": [181.071, 194.079, 342.116],
        "adducts": ["[M+H]+", "[M+Na]+"],
        "tolerance": 0.02,
        "sources": ["HMDB", "ChEBI"],
        "limit": 20
    }
    ```
    """
    try:
        se = get_search_engine()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    query_results = []

    for mass in request.masses:
        for adduct_label in request.adducts:
            adduct_delta = resolve_adduct(adduct_label)

            if adduct_delta > 0:
                ion_mode = "positive"
            elif adduct_delta < 0:
                ion_mode = "negative"
            else:
                ion_mode = "neutral"

            results = se.search_by_mass(
                target_mass   = mass,
                tolerance     = request.tolerance,
                ion_mode      = ion_mode,
                source_filter = request.sources,
                max_results   = request.limit,
            )

            query_results.append(BatchQueryResult(
                query_mass   = mass,
                adduct       = adduct_label,
                adduct_delta = adduct_delta,
                result_count = len(results),
                results      = [map_mass_result(r, mass, adduct_label) for r in results],
            ))

    return query_results


@app.get("/adducts", tags=["Meta"])
def list_adducts():
    """List all supported adduct modes and their mass deltas."""
    return [{"adduct": k, "delta_da": v} for k, v in ADDUCTS.items()]