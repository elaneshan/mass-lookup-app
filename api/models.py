"""
API Models
==========
Pydantic schemas for request validation and response serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ─────────────────────────────────────────────
# RESPONSE MODELS
# ─────────────────────────────────────────────

class CompoundResult(BaseModel):
    """Single compound match returned by mass or formula search."""
    source:       str
    source_id:    Optional[str]  = None
    name:         Optional[str]  = None
    formula:      Optional[str]  = None
    cas:          Optional[str]  = None
    inchikey:     Optional[str]  = None
    exact_mass:   Optional[float] = None

class MassResult(CompoundResult):
    """Mass search result — includes error fields."""
    observed_mass: float
    mass_error:    float
    ppm_error:     float
    adduct:        str
    ion_mode:      str

class BatchQueryResult(BaseModel):
    """One query within a batch search."""
    query_mass:  float
    adduct:      str
    adduct_delta: float
    result_count: int
    results:     List[MassResult]

class StatsResponse(BaseModel):
    """Database statistics."""
    total_compounds: int
    by_source:       dict
    min_mass:        Optional[float]
    max_mass:        Optional[float]


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

class BatchSearchRequest(BaseModel):
    """POST body for /search/batch."""
    masses:    List[float] = Field(..., min_length=1, max_length=100)
    adducts:   List[str]   = Field(default=["[M+H]+"])
    tolerance: float       = Field(default=0.02, gt=0, le=5.0)
    sources:   Optional[List[str]] = None
    limit:     int         = Field(default=20, gt=0, le=500)