# Windows Deployment Guide
# Mass Lookup Tool — LC-MS

## Overview

The app is built on Mac but **must be packaged on Windows** to produce a Windows .exe.
You have two options:

1. **Use a lab Windows computer** to run PyInstaller (recommended)
2. **Use the server** if it runs Windows or has Wine

---

## Step 1 — Transfer project to Windows machine

Copy the entire `mass_lookup_app/` folder to the Windows machine.
Exclude the large raw data files — just need the app code + database:

```
mass_lookup_app/
  main.py
  search/
    __init__.py
    search_engine.py
  database/
    compounds.db        ← REQUIRED — copy this over
  scripts/
  mass_lookup.spec
```

**Fastest transfer options:**
- USB drive
- `scp` if Windows machine has SSH: `scp -r mass_lookup_app/ user@labpc:/path/`
- Shared network drive
- GitHub (push from Mac, pull on Windows)

---

## Step 2 — Set up Python on Windows

On the Windows machine, open Command Prompt or PowerShell:

```bat
:: Install Python 3.11 from python.org if not already installed
:: Then:

cd mass_lookup_app
python -m venv venv
venv\Scripts\activate

pip install PyQt5 pyinstaller
```

---

## Step 3 — Build the executable

```bat
cd mass_lookup_app
venv\Scripts\activate
pyinstaller mass_lookup.spec
```

This creates:
```
dist/
  MassLookup/
    MassLookup.exe      ← main executable
    [many .dll files]   ← required, keep with .exe
```

**Do not move MassLookup.exe out of the MassLookup/ folder** — it needs the DLLs next to it.

---

## Step 4 — Add the database

Copy `database/compounds.db` into the `dist/MassLookup/database/` folder:

```
dist/MassLookup/
  MassLookup.exe
  database/
    compounds.db        ← copy here
  [dll files...]
```

---

## Step 5 — Test and distribute

Double-click `MassLookup.exe` — it should open without installing anything.

To share with the lab:
1. Zip the entire `dist/MassLookup/` folder
2. Share the zip
3. Users unzip and run `MassLookup.exe` — no install needed

---

## Troubleshooting

**"DLL not found" error:**
```bat
pip install pyinstaller --upgrade
pyinstaller mass_lookup.spec --clean
```

**App opens then immediately closes:**
Temporarily enable the console to see the error:
In `mass_lookup.spec`, change `console=False` to `console=True`, rebuild.

**PyQt5 not found:**
```bat
pip install PyQt5==5.15.9
```

**Database not found error:**
Make sure `database/compounds.db` is in the same folder as `MassLookup.exe`
(inside `dist/MassLookup/database/compounds.db`)

---

## File size expectations

| Component         | Size      |
|-------------------|-----------|
| MassLookup folder | ~80 MB    |
| compounds.db      | ~300 MB   |
| Total to share    | ~380 MB   |

compounds.db without MoNA. With MoNA it will be ~3-5 GB.

---

## Database path note

`search_engine.py` uses a relative path `"database/compounds.db"`.
PyInstaller sets the working directory to the exe location, so this
path resolves correctly as long as the folder structure is maintained.

No code changes needed for Windows deployment.