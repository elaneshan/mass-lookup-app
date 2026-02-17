# Offline LC-MS Mass Lookup Tool

Standalone offline metabolomics mass search application for LC-MS compound identification.  
Fully offline. No internet connection required at runtime.

---

## Overview

This application enables rapid compound identification from LC-MS data using exact mass or molecular formula searches. It integrates multiple biochemical databases into a unified local SQLite database optimized for fast indexed queries.

Designed for laboratory environments where internet access is restricted.

---

## Features

- Exact mass search with configurable tolerance (default ±0.5 Da)
- Molecular formula search
- Seven supported ion/adduct modes:
  - [M+H]+
  - [M+Na]+
  - [M+K]+
  - [M+NH4]+
  - [M-H]-
  - [M+Cl]-
  - [M+FA-H]-
- Multi-source database (457,527 compounds across 3 databases)
- Database source filter checkboxes
- Color-coded results by source database
- Copyable source URLs (HMDB, ChEBI, LipidMaps)
- Copy selected row to clipboard (Excel/lab notebook compatible)
- CSV export including:
  - Search parameters
  - Adduct information
  - Source URLs
- Indexed SQLite queries (sub-second search performance)
- Clean PyQt5 desktop interface
- Fully offline operation

---

## Database Coverage

| Source     | Compounds | Focus Area            |
|------------|-----------|-----------------------|
| HMDB       | 217,879   | Human metabolites     |
| ChEBI      | 189,932   | Biochemical compounds |
| LipidMaps  | 49,716    | Lipids (lipidomics)   |
| **Total**  | **457,527** |                     |

---

## Technology Stack

- Python 3.11+
- SQLite (indexed mass and formula searches)
- PyQt5 desktop GUI
- Fully offline architecture

---

## Usage
Mass Search
Select Mass mode
Enter observed m/z value
Select appropriate adduct (e.g. [M+H]+ for positive ESI)
Adjust tolerance if needed (default ±0.5 Da)
Optionally filter by database source
Click Search

Results are ranked by mass error (closest match first).

## Formula Search

Select Formula mode
Enter molecular formula (e.g. C6H12O6)
Click Search

Returns all compounds matching the exact formula across selected databases.

## Exporting Results

Copy Selected Row
Copies tab-separated result data directly to clipboard.

## Export to CSV
Saves all results including:
Search parameters

