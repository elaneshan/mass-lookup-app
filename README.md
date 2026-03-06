# LUCID — LC-MS Unified Compound Identification Database

A desktop + API tool for LC-MS compound identification. Search 500k+ compounds by exact mass or molecular formula across HMDB, ChEBI, LipidMaps, NPAtlas, FooDB, and PubChem — with multi-adduct support, batch search, and CSV export.

Distributed as a Windows `.exe` backed by an always-on FastAPI server, or run fully offline with a local database.

---

## Example

Search mass `181.071` with `[M+H]+` across all sources → returns glucose, galactose, and related metabolites with clickable source links and InChIKey identifiers.

---

## Prerequisites

**General:**
- Python 3.11+
- ~10 GB storage for full database build
- Network access to lab server (for `.exe` deployment)

**Python Libraries:**
```
pip install -r requirements.txt
pip install PyQt5
```

---

## Features

- **Batch mass search** — paste multiple masses at once, get top N hits per mass
- **Multi-adduct search** — search one mass across `[M+H]+`, `[M+Na]+`, `[M+K]+`, and more simultaneously
- **Formula search** — exact molecular formula lookup across all sources
- **Clickable source URLs** — single click opens HMDB, ChEBI, LipidMaps, NPAtlas, or PubChem in browser
- **InChIKey column** — shown for every compound that has one
- **Ctrl+F filter** — filter visible results by name, formula, source, or InChIKey in real time
- **Source filtering** — toggle individual databases independently
- **Color-coded results** by source database
- **CSV export** with full search parameters, source URLs, InChIKeys, and PubChem links
- **Two deployment modes** — local SQLite (development) or FastAPI server (lab)
- **Fast indexed queries** — mass search ~9ms, formula search ~1ms (500k+ compounds)

---

## Adduct Modes

| Adduct | Mode |
|---|---|
| `[M+H]+` | Positive |
| `[M+Na]+` | Positive |
| `[M+K]+` | Positive |
| `[M+NH4]+` | Positive |
| `[M-H]-` | Negative |
| `[M+Cl]-` | Negative |
| `[M+FA-H]-` | Negative |
| Neutral | Exact mass |

---

## Database Coverage

| Source | Compounds | Focus |
|---|---|---|
| HMDB | 217,879 | Human metabolites |
| ChEBI | 190,800 | Biochemical compounds |
| LipidMaps | 49,719 | Lipids |
| NPAtlas | 36,454 | Natural products |
| FooDB | ~28,000 | Food metabolites, flavonoids |
| PubChem | ~5,000,000 | Broad metabolomics range (50–2000 Da) |
| **Total** | **~5,500,000+** | |

*MoNA import pending (overnight server job)*

---

## Architecture

**Lab deployment:**
```
Lab PCs (any Windows machine on lab network)
  └── MassLookup.exe  (unzip and run — no installs needed)
        │  HTTP
        ▼
  Server — always on, runs as SYSTEM via Task Scheduler
  └── FastAPI + Uvicorn
        └── compounds.db (SQLite)
```

**Local development:**
```
python ui/main_window.py  →  local compounds.db
```

---

## Quick Start — Local Development

```bash
git clone <repo>
cd mass-lookup-app
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install PyQt5

# Build core database (5-10 min)
python scripts/build_database_v5.py

# Run GUI
python ui/main_window.py
```

---

## API Server

The server runs via Windows Task Scheduler as SYSTEM — starts on boot, no login required.

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/stats` | Compound counts by source |
| GET | `/search/mass` | Mass search with adduct correction |
| GET | `/search/formula` | Exact formula search |
| POST | `/search/batch` | Multi-mass × multi-adduct search |
| GET | `/adducts` | List supported adduct modes |

**Example:**
```
GET /search/mass?mass=181.071&adduct=[M+H]+&tolerance=0.02&sources=HMDB,ChEBI
```

---

## Configuration

`config.ini` (sits next to the `.exe` or `main_window.py`):

```ini
[server]
url = http://<server-ip>:8000

[app]
mode = api    # 'local' -> SQLite direct | 'api' -> FastAPI server
```

---

## Scripts

| Script | Purpose |
|---|---|
| `build_database_v5.py` | Build core DB from HMDB, ChEBI, LipidMaps, NPAtlas |
| `migrate_add_smiles.py` | One-time migration — adds SMILES column to existing DB |
| `scrape_pubchem.py` | PubChem flat-file import (50–2000 Da range, ~5M compounds) |
| `scrape_foodb.py` | FooDB import (~28k food metabolites + flavonoids) |
| `scrape_lotus.py` | LOTUS natural products import |
| `export_progenesis.py` | Export to Progenesis QI CSV format |

**Common commands:**

```bash
# Build core database
python scripts/build_database_v5.py

# Add SMILES column (run once before PubChem/FooDB/LOTUS)
python scripts/migrate_add_smiles.py

# Import PubChem (run overnight — downloads ~4GB)
python scripts/scrape_pubchem.py

# Import FooDB
python scripts/scrape_foodb.py

# Export for Progenesis
python scripts/export_progenesis.py --sources HMDB LipidMaps
```

---

## Windows Lab Deployment

```powershell
# On the server — activate venv and build database first
venv\Scripts\activate
python scripts/build_database_v5.py

# Register always-on API (runs as SYSTEM, survives logout and reboot)
$action = New-ScheduledTaskAction `
  -Execute "C:\path\to\venv\Scripts\python.exe" `
  -Argument "-m uvicorn api.main:app --host 0.0.0.0 --port 8000" `
  -WorkingDirectory "C:\path\to\mass-lookup-app"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "MassLookupAPI" `
  -Action $action `
  -Trigger (New-ScheduledTaskTrigger -AtStartup) `
  -Principal $principal -Force
Start-ScheduledTask -TaskName "MassLookupAPI"
```

**Distributing to lab users:**
1. Build the exe: `pyinstaller mass_lookup.spec`
2. Copy `config.ini` into `dist\MassLookup\` with `mode = api` and correct server IP
3. Zip `dist\MassLookup\` and share via Google Drive or network share
4. Users unzip anywhere and double-click `MassLookup.exe` — no Python or installs needed

---

## Tech Stack

- **Python 3.11**
- **PyQt5** — desktop GUI
- **SQLite** — indexed compound database
- **FastAPI + Uvicorn** — REST API server
- **Windows Task Scheduler** — always-on server process (runs as SYSTEM)
- **Pydantic** — request/response validation
- **PyInstaller** — Windows `.exe` packaging