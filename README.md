# Offline LC-MS Mass Lookup Tool

Standalone offline metabolomics mass search application with multi-mode search capabilities.

Features:
- Mass search with tolerance-based matching
- Formula search for exact molecular formula lookup
- Ion mode support (Positive [M+H]+, Negative [M-H]-, Neutral)
- Multi-source database architecture (currently HMDB with 217k compounds)
- CSV export functionality
- Fast SQLite-based search with indexed queries
- Clean PyQt5 desktop interface

Database:
- HMDB: 217,879 metabolites with monoisotopic masses
- Extensible schema ready for additional sources (KEGG, PubChem, MassBank)

Tech Stack:
- Python 3.11+
- SQLite with indexed mass/formula searches
- PyQt5 for cross-platform GUI
- Fully offline, no internet required