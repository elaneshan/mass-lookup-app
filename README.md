# LC-MS Mass Lookup Tool

A desktop + API tool for LC-MS compound identification. Search 494,852+ compounds by exact mass or molecular formula across HMDB, ChEBI, LipidMaps, and NPAtlas — with multi-adduct support, batch search, and CSV export.

Deployable as a Windows `.exe` backed by a FastAPI server, or run fully offline with a local database.

---

## Features

- **Batch mass search** — paste multiple masses at once, get top N hits per mass
- **Multi-adduct search** — search one mass across [M+H]+, [M+Na]+, [M+K]+ and more simultaneously
- **Formula search** — exact molecular formula lookup across all sources
- **Source filtering** — toggle HMDB, ChEBI, LipidMaps, NPAtlas independently
- **Color-coded results** by source database
- **Source IDs + URLs** — clickable links to HMDB, ChEBI, LipidMaps, NPAtlas records
- **CSV export** with full search parameters and source metadata
- **Progenesis QI export** — export database in Progenesis-compatible format
- **Two deployment modes** — local SQLite (dev) or FastAPI server (lab)
- **Fast indexed queries** — mass search ~9ms, formula search ~1ms (494k compounds)

### Adduct Modes
`[M+H]+` `[M+Na]+` `[M+K]+` `[M+NH4]+` `[M-H]-` `[M+Cl]-` `[M+FA-H]-` `neutral`

---

## Database Coverage

| Source    | Compounds | Focus                     |
|-----------|-----------|---------------------------|
| HMDB      | 217,879   | Human metabolites         |
| ChEBI     | 190,800   | Biochemical compounds     |
| LipidMaps | 49,719    | Lipids                    |
| NPAtlas   | 36,454    | Natural products          |
| **Total** | **494,852** |                         |

*MoNA and KEGG pending server import (~+1M compounds)*

---

## Architecture

```
Lab deployment:
  [MassLookup.exe on any lab PC]
        │  HTTP
        ▼
  [Server: Docker → FastAPI :8000] → [compounds.db]

Local development:
  [python main.py] → [local compounds.db]
```

---

## Quick Start — Local Development

```bash
git clone <repo>
cd mass_lookup_app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install PyQt5

# Build database (5-10 min)
python scripts/build_database_v5.py

# Run GUI
python main.py
```

---

## Quick Start — API Server (Docker)

```bash
# Build and start
docker-compose up --build

# API available at:
http://localhost:8000/docs
```

**Endpoints:**

| Method | Endpoint          | Description                        |
|--------|-------------------|------------------------------------|
| GET    | `/health`         | Liveness check                     |
| GET    | `/stats`          | Compound counts by source          |
| GET    | `/search/mass`    | Mass search with adduct correction |
| GET    | `/search/formula` | Exact formula search               |
| POST   | `/search/batch`   | Multi-mass × multi-adduct search   |
| GET    | `/adducts`        | List supported adduct modes        |

Example:
```
GET /search/mass?mass=181.071&adduct=[M+H]+&tolerance=0.02&sources=HMDB,ChEBI
```

---

## Configuration

`config.ini` (sits next to the `.exe` or `main.py`):

```ini
[server]
url = http://localhost:8000   # change to server IP for lab deployment

[app]
mode = local    # 'local' → SQLite direct | 'api' → FastAPI server
```

---

## Scripts

| Script                        | Purpose                                     |
|-------------------------------|---------------------------------------------|
| `build_database_v5.py`        | Build DB from HMDB, ChEBI, LipidMaps, NPAtlas |
| `migrate_formula_index.py`    | One-time migration for existing databases   |
| `export_progenesis.py`        | Export to Progenesis QI CSV format          |
| `scrape_kegg.py`              | KEGG API scraper (run on server)            |

```bash
# Build database
python scripts/build_database_v5.py

# Add MoNA (run on server overnight — 17GB file)
python scripts/build_database_v5.py --mona-only

# Add KEGG (run on server)
python scripts/scrape_kegg.py

# Export for Progenesis
python scripts/export_progenesis.py --sources HMDB LipidMaps

# Performance diagnostic
python tests/diagnose_performance.py
```

---

## Windows Deployment

See `WINDOWS_DEPLOYMENT.md` for full instructions.

```bash
# On a Windows machine:
pip install pyinstaller
pyinstaller mass_lookup.spec
# Copy database/ into dist/MassLookup/
# Edit config.ini: mode = api, url = http://[server-ip]:8000
# Zip and distribute dist/MassLookup/
```

---

## Tech Stack

- **Python 3.11**
- **PyQt5** — desktop GUI
- **SQLite** — indexed compound database
- **FastAPI + Uvicorn** — REST API server
- **Docker + Docker Compose** — containerized deployment
- **Pydantic** — request/response validation