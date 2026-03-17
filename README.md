# LUCID: LC-MS Unified Compound Identification Database

A full-stack metabolomics tool for LC-MS compound identification. Search 500k+ compounds by exact mass or molecular formula across HMDB, ChEBI, LipidMaps, NPAtlas, FooDB, and PubChem with multi-adduct support, batch search, and CSV export.

**Web app:** [lucid-lcms.org](https://lucid-lcms.org): no install required, works in any browser  
**API:** [api.lucid-lcms.org/docs](https://api.lucid-lcms.org/docs): REST API, publicly accessible  
**Lab deployment:** Windows `.exe` backed by an always-on FastAPI server on the lab network

> Citation pending: manuscript in preparation

---

## Example

Search mass `181.071` with `[M+H]+` across all sources → returns glucose, galactose, and related metabolites with clickable source links, InChIKey identifiers, and direct PubChem cross-references.

---

## Features

- **Batch mass search** : paste multiple masses at once, get top N hits per mass
- **Multi-adduct search** : search one mass across `[M+H]+`, `[M+Na]+`, `[M+K]+`, and more simultaneously
- **Formula search** : exact molecular formula lookup across all sources
- **Clickable source URLs** : opens HMDB, ChEBI, LipidMaps, NPAtlas, or PubChem directly in browser
- **InChIKey column** : shown for every compound that has one
- **Ctrl+F filter** : filter results by name, formula, source, or InChIKey in real time
- **Source filtering** : toggle individual databases independently
- **Color-coded results** by source database
- **CSV export** with full search parameters, source URLs, InChIKeys, and PubChem links
- **Fast indexed queries** : mass search ~9ms, formula search ~1ms (500k+ compounds)

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

*MoNA import pending*

---

## Deployment Options

LUCID supports three deployment modes:

```
1. Web app (public)
   lucid-lcms.org  →  React frontend (Vercel)
                         │  HTTPS
                         ▼
   api.lucid-lcms.org  →  FastAPI + SQLite (AWS EC2, Oregon)

2. Lab deployment (Windows network)
   LUCID.exe on any lab PC  →  FastAPI on lab server (always-on, SYSTEM)
                                  └── compounds.db (5.5M compounds)

3. Local development
   python ui/main_window.py  →  local compounds.db
```

---

## Quick Start: Web App

No installation needed. Go to [lucid-lcms.org](https://lucid-lcms.org) in any browser. The web version uses the core 4 databases (HMDB, ChEBI, LipidMaps, NPAtlas: 494,852 compounds).

---

## Quick Start: Local Development

```bash
git clone https://github.com/elaneshan/mass-lookup-app
cd mass-lookup-app
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install PyQt5

# Build core database (5-10 min, requires raw data files)
python scripts/build_database.py

# Run desktop GUI
python ui/main_window.py

# Or run API server
uvicorn api.main:app --reload --port 8000
```

**Raw data files required** (not included in repo: download separately):
- `data/raw/hmdb_metabolites.xml`: from [hmdb.ca/downloads](https://hmdb.ca/downloads)
- `data/raw/chebi.sdf`: from [ebi.ac.uk/chebi](https://www.ebi.ac.uk/chebi/)
- `data/raw/structures.sdf`: from [lipidmaps.org](https://www.lipidmaps.org)
- `data/raw/NPAtlas_download_2024_09.sdf`: from [npatlas.org](https://www.npatlas.org)

---

## Quick Start: React Frontend (Development)

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
# Proxies API calls to http://localhost:8000
```

**Prerequisites:** Node.js 18+, FastAPI running locally on port 8000.

---

## API Server

The public API is live at `https://api.lucid-lcms.org`. For local use, start with:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

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
GET https://api.lucid-lcms.org/search/mass?mass=181.071&adduct=[M+H]+&tolerance=0.02&sources=HMDB,ChEBI
```

---

## AWS Cloud Deployment

The public web version runs on AWS (us-west-2):

```
React frontend  →  Vercel (auto-deploys on git push to main)
FastAPI backend →  AWS EC2 t3.micro (Ubuntu 24.04, PM2 process manager)
SQLite database →  On EC2 instance (494,852 compounds, core 4 sources)
DNS             →  AWS Route 53 (lucid-lcms.org)
SSL             →  Let's Encrypt via Certbot (auto-renewing)
```

**Deploying backend changes to EC2:**
```bash
ssh -i ~/.ssh/lucid-key.pem ubuntu@44.252.20.43
cd mass-lookup-app
git pull origin main
pm2 restart lucid-api
```

**Checking API status:**
```bash
pm2 status
curl https://api.lucid-lcms.org/health
```

---

## Windows Lab Deployment

The lab version uses a Windows exe talking to an always-on lab server.

**Server setup (run once):**
```powershell
venv\Scripts\activate
python scripts/build_database.py

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

**Building the exe:**
```powershell
venv\Scripts\activate
pip install pyinstaller
pyinstaller mass_lookup.spec
copy config.ini dist\LUCID\config.ini
copy lucid.ico dist\LUCID\lucid.ico
Compress-Archive -Path dist\LUCID -DestinationPath LUCID.zip -Force
```

**`config.ini` for lab distribution:**
```ini
[server]
url = http://<lab-server-ip>:8000

[app]
mode = api
```

**Distributing to lab users:**
1. Share `LUCID.zip` via Google Drive or network share
2. Users unzip anywhere and double-click `LUCID.exe`
3. Must be on the lab network: no Python or other installs needed

---

## Configuration

`config.ini` controls which backend the app connects to:

```ini
[server]
url = http://localhost:8000   # or lab server IP, or https://api.lucid-lcms.org

[app]
mode = api      # 'local' -> direct SQLite | 'api' -> FastAPI server
```

---

## Scripts

| Script | Purpose |
|---|---|
| `build_database.py` | Build core DB from HMDB, ChEBI, LipidMaps, NPAtlas |
| `migrate_add_smiles.py` | One-time migration: adds SMILES column to existing DB |
| `optimize_db.py` | Add performance indexes after large imports (run after PubChem) |
| `scrape_pubchem.py` | PubChem flat-file import (50–2000 Da range, ~5M compounds) |
| `scrape_foodb.py` | FooDB import (~28k food metabolites + flavonoids) |
| `scrape_lotus.py` | LOTUS natural products import |
| `scrape_msdial.py` | MS-DIAL spectral library import (.msp files) |
| `export_progenesis.py` | Export to Progenesis QI CSV format |

**Common commands:**
```bash
# Build core database
python scripts/build_database.py

# Run migrations before large imports
python scripts/migrate_add_smiles.py

# Import PubChem (run overnight: downloads ~4GB)
python scripts/scrape_pubchem.py

# Optimize after large imports
python scripts/optimize_db.py

# Import FooDB
python scripts/scrape_foodb.py

# Export for Progenesis
python scripts/export_progenesis.py --sources HMDB LipidMaps
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web frontend | React + Vite + Tailwind CSS |
| Desktop GUI | PyQt5 |
| Backend API | FastAPI + Uvicorn |
| Database | SQLite (WAL mode, partial indexes) |
| Cloud hosting | AWS EC2 t3.micro (backend), Vercel (frontend) |
| DNS + SSL | AWS Route 53 |
| Process manager | PM2 (cloud) / Windows Task Scheduler (lab) |
| Packaging | PyInstaller (.exe) |
| Validation | Pydantic |

---

## Repository Structure

```
mass-lookup-app/
├── api/                  # FastAPI backend
│   ├── main.py
│   ├── models.py
│   └── dependencies.py
├── frontend/             # React web app
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   └── package.json
├── ui/                   # PyQt5 desktop app
│   └── main_window.py
├── scripts/              # Database build + import scripts
├── search/               # SQLite search engine
├── database/             # compiled .db file (gitignored)
├── data/                 # raw source files (gitignored)
├── config.ini
├── mass_lookup.spec      # PyInstaller spec
├── lucid.ico             # App icon
└── requirements.txt
```
