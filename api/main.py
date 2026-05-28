"""
LC-MS Mass Lookup API
=====================
Frontend ↔ API Layer ↔ Search Engine ↔ Database
Endpoints:
    GET  /health
    GET  /stats
    GET  /search/mass
    GET  /search/formula
    GET  /search/name
    POST /search/batch

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

# how it works: frontend sends HTTP request; FastAPI route gets the request and validates it
# route will call search engine -> search engine will query from compund database
# API formats the response back and the front end recives back the json

# in this file we define the end points, validate inputs, covert the raw engine output into API schemas
# is this the traffic controller
# so if App.jsx is the front end controller then this one acts as the server-side control layer
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

# fastAPI -> bc it provides automatic request vlaidation and pre-built architecture
# these are the pydantic models that will define the request and response contracts between the backend and then frontend
from api.models import (
    MassResult, CompoundResult, BatchQueryResult,
    StatsResponse, BatchSearchRequest
)
from api.dependencies import get_search_engine
from api.models import MS2SearchRequest, MS2SearchResponse

# ─────────────────────────────────────────────
# ADDUCT TABLE
# ─────────────────────────────────────────────

# Adducts are ions that form when a molecule picks up or loses a small charged
# particle during ionization. In mass spec, what we actually *measure* is the
# mass of that ion — not the bare molecule — so we need to subtract the adduct's
# known mass offset to recover the true neutral mass of the compound.
ADDUCTS = {
    "[M+H]+":    1.007276,   # proton added (most common in positive mode)
    "[M+Na]+":   22.989218,  # sodium adduct — common in ESI-positive
    "[M+K]+":    38.963158,  # potassium adduct
    "[M+NH4]+":  18.034374,  # ammonium adduct — common for lipids
    "[M]+":      0.0,        # radical cation, no offset
    "[M-H]-":   -1.007276,   # deprotonated — most common in negative mode
    "[M+Cl]-":   34.969402,  # chloride adduct — negative mode
    "[M-2H]-":  -2.014552,   # doubly deprotonated
    "[M-2H]2-": -2.014552,   # same delta, different charge notation
    "neutral":   0.0,        # no adduct correction applied
}

# the lookup table ensures that the chem logic is consistent across every endpoint


def resolve_adduct(adduct_str: str) -> float:
    """
    Looks up the mass delta (in Daltons) for a given adduct string.
    Raises a 400 error immediately if the adduct isn't in our table —
    this is a fast-fail so bad input never reaches the search engine.
    """
    delta = ADDUCTS.get(adduct_str)
    if delta is None: # invalid inputs are treated as client input erros rather than server failures
        raise HTTPException(
            status_code=400,
            detail=f"Unknown adduct '{adduct_str}'. "
                   f"Valid options: {list(ADDUCTS.keys())}"
        )
    return delta


def map_mass_result(r: dict, observed_mass: float, adduct: str) -> MassResult:
    """
    Transforms a raw database result dict into a typed MassResult object.
    We attach the original observed m/z and adduct label here so the caller
    always gets full context alongside the database match — useful when
    processing batch results with mixed adducts.
    """
    return MassResult(
        source        = r.get("source", ""),
        source_id     = r.get("source_id"),
        name          = r.get("name"),
        formula       = r.get("formula") if r.get("formula") != "N/A" else None,
        cas           = r.get("cas") or None,
        inchikey      = r.get("inchikey") or None,
        exact_mass    = r.get("neutral_mass") or r.get("exact_mass"),  # fallback for different DB schemas
        observed_mass = observed_mass,
        mass_error    = round(r.get("mass_error", 0), 6),  # absolute Da error
        ppm_error     = round(r.get("ppm_error", 0), 3),   # relative error — more meaningful at different mass ranges
        adduct        = adduct,
        ion_mode      = r.get("ion_mode", "neutral"),
    )
# this func nornalizes db schemeas into stable response contracts so the frontend can just handle them all the same
def map_formula_result(r: dict) -> CompoundResult:
    """
    Simpler mapper for formula/name searches — no mass error fields needed
    since we're not doing m/z matching here, just identity lookup.
    """
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

# FastAPI auto-generates interactive docs at /docs (Swagger) and /redoc.
# The title/description here show up there — useful for collaborators and API consumers.
app = FastAPI(
    title       = "LUCID API",
    description = "Search 494k+ compounds by mass, formula, or name across HMDB, ChEBI, LipidMaps, NPAtlas and more.",
    version     = "1.1.0",
)

# Allow any frontend (or tool like Postman) to call this API cross-origin.
# In production you'd lock allow_origins down to specific domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

@app.on_event("startup")
def startup():
    """
    Runs once when the server boots. We eagerly load the search engine (which
    reads the compound database into memory) and print a per-source breakdown.
    If the database file is missing we don't crash — the API starts in a
    "degraded" state and every search endpoint returns 503 until it's fixed.
    """
    try:
        se    = get_search_engine()
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
def health(): # for AWS
    """
    Lightweight liveness check — suitable for load balancer health probes.
    Returns 'ok' with compound count if the DB is reachable, 'degraded' otherwise.
    Intentionally never raises an exception so monitoring tools always get a 200.
    """
    try:
        se    = get_search_engine()
        stats = se.get_stats()
        return {"status": "ok", "compounds": stats["total_compounds"]}
    except Exception:
        return {"status": "degraded", "compounds": 0}


@app.get("/stats", response_model=StatsResponse, tags=["Meta"])
def stats():
    """Returns per-source compound counts — useful for verifying database ingestion."""
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
    sources:   Optional[str] = Query(None, description="Comma-separated sources"),
    limit:     int   = Query(20, description="Max results", gt=0, le=500),
):
    """
    Core endpoint — looks up compounds by observed m/z.

    The key step: we subtract the adduct delta from the observed mass before
    querying, so the search engine always works in neutral mass space. This means
    the DB doesn't need separate entries per adduct form.

    Ion mode (positive/negative/neutral) is derived from the adduct sign — we
    pass it to the engine so it can filter to chemically sensible results.
    """
    adduct_delta  = resolve_adduct(adduct)
    source_filter = [s.strip() for s in sources.split(",")] if sources else None
    # Derive ion mode from the sign of the adduct delta
    ion_mode      = "positive" if adduct_delta > 0 else "negative" if adduct_delta < 0 else "neutral"

    try:
        se      = get_search_engine()
        results = se.search_by_mass(
            target_mass=mass, tolerance=tolerance,
            ion_mode=ion_mode, source_filter=source_filter, max_results=limit,
            adduct_delta=adduct_delta,
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
    Exact formula match across all database sources.
    Useful when you've already determined the molecular formula (e.g. from
    high-res MS1) and want to enumerate all known compounds with that composition.
    Note: many structurally distinct compounds share a formula (isomers), so
    results here are not unique identities — that's expected.
    """
    source_filter = [s.strip() for s in sources.split(",")] if sources else None

    try:
        se      = get_search_engine()
        results = se.search_by_formula(
            formula=formula, source_filter=source_filter, max_results=limit,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return [map_formula_result(r) for r in results]


@app.get("/search/name", response_model=List[CompoundResult], tags=["Search"])
def search_by_name(
    query:   str = Query(..., description="Compound name or partial name, e.g. caffeine"),
    sources: Optional[str] = Query(None, description="Comma-separated sources"),
    limit:   int = Query(50, description="Max results", gt=0, le=500),
):
    """
    Case-insensitive substring name search — handy for quick identity lookup
    when you already have a name in mind (e.g. a known standard or reference compound).
    Returns a 501 if the underlying search engine version doesn't support name search,
    so the API degrades gracefully rather than throwing an unhandled exception.
    """
    source_filter = [s.strip() for s in sources.split(",")] if sources else None

    try:
        se      = get_search_engine()
        results = se.search_by_name(
            query=query, source_filter=source_filter, max_results=limit,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AttributeError:
        # Raised if an older engine version doesn't have search_by_name implemented
        raise HTTPException(status_code=501, detail="Name search not implemented in this search engine version.")

    return [map_formula_result(r) for r in results]


@app.post("/search/batch", response_model=List[BatchQueryResult], tags=["Search"])
def search_batch(request: BatchSearchRequest):
    """
    Batch endpoint — runs the full mass search for every combination of
    (mass × adduct) in a single request. This avoids the overhead of many
    individual HTTP calls when processing a full LC-MS feature list.

    Each (mass, adduct) pair produces its own BatchQueryResult, so the caller
    can easily map results back to their original query.
    """
    try:
        se = get_search_engine()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    query_results = []

    # Cartesian product: every mass paired with every adduct
    for mass in request.masses:
        for adduct_label in request.adducts:
            adduct_delta = resolve_adduct(adduct_label)
            ion_mode     = "positive" if adduct_delta > 0 else "negative" if adduct_delta < 0 else "neutral"

            results = se.search_by_mass(
                target_mass=mass, tolerance=request.tolerance,
                ion_mode=ion_mode, source_filter=request.sources,
                max_results=request.limit,
                adduct_delta=adduct_delta,
            )

            query_results.append(BatchQueryResult(
                query_mass   = mass,
                adduct       = adduct_label,
                adduct_delta = adduct_delta,
                result_count = len(results),
                results      = [map_mass_result(r, mass, adduct_label) for r in results],
            ))

    return query_results


@app.post("/search/ms2", tags=["Search"])
def search_ms2(request: MS2SearchRequest):
    """
    MS2 (tandem mass spec) fragment matching endpoint.

    MS2 gives us a fragmentation spectrum — a fingerprint of how a molecule
    breaks apart. This endpoint:
      1. Takes all fragment masses from a single MS2 scan
      2. Searches each fragment individually against the DB
      3. Computes pairwise mass differences and matches them to known neutral losses
         (e.g. loss of water at 18 Da, loss of CO2 at 44 Da)
      4. Scores each candidate compound by how many fragments it can explain
      5. Returns candidates ranked by score, with neutral losses annotated

    This is the most chemically rich search mode — it goes beyond just matching
    the precursor mass and actually leverages structural information from fragmentation.
    """
    adduct_delta = resolve_adduct(request.adduct)

    try:
        se = get_search_engine()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Input validation — keep payloads sane before hitting the engine
    if not request.fragment_masses:
        raise HTTPException(status_code=400, detail="Provide at least one fragment mass.")
    if len(request.fragment_masses) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 fragment masses per request.")

    result = se.search_ms2(
        fragment_masses=request.fragment_masses,
        adduct_delta=adduct_delta,
        adduct=request.adduct,
        tolerance=request.tolerance,
        source_filter=request.sources or None,
        max_candidates=request.limit,
    )

    return result

@app.get("/adducts", tags=["Meta"])
def list_adducts():
    """
    Utility endpoint — returns the full adduct table with their Da offsets.
    Lets API consumers discover valid adduct strings without reading the docs.
    """
    return [{"adduct": k, "delta_da": v} for k, v in ADDUCTS.items()]