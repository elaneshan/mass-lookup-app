"""
Environment Check Script
========================

Run this BEFORE attempting to build the database.
It verifies that all required libraries are installed.
"""


def check_imports():
    """Check if all required libraries can be imported."""

    print("Checking Python environment...\n")

    required = {
        'sqlite3': 'SQLite (built-in)',
        'xml.etree.ElementTree': 'XML Parser (built-in)',
        'pandas': 'Pandas',
        'sqlalchemy': 'SQLAlchemy',
        'PyQt5': 'PyQt5'
    }

    missing = []

    for module, name in required.items():
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError:
            print(f"❌ {name} - NOT FOUND")
            missing.append(module)

    print()

    if missing:
        print("Missing libraries. Install with:")
        if 'PyQt5' in missing:
            print("  pip install pandas sqlalchemy pyqt5")
        else:
            print(f"  pip install {' '.join(missing)}")
        return False
    else:
        print("✅ All required libraries are installed!")
        return True


def check_folders():
    """Check if folder structure exists."""
    import os

    print("\nChecking folder structure...\n")

    folders = ['database', 'data/raw', 'scripts', 'search', 'ui']

    for folder in folders:
        if os.path.exists(folder):
            print(f"✓ {folder}/")
        else:
            print(f"❌ {folder}/ - MISSING")
            print(f"   Creating: {folder}/")
            os.makedirs(folder, exist_ok=True)

    print("\n✅ Folder structure ready!")


def main():
    print("=" * 60)
    print("Mass Lookup App - Environment Check")
    print("=" * 60)
    print()

    imports_ok = check_imports()
    check_folders()

    print("\n" + "=" * 60)

    if imports_ok:
        print("✅ Environment is ready!")
        print("\nNext steps:")
        print("1. Download HMDB XML from: https://hmdb.ca/downloads")
        print("2. Place it at: data/raw/hmdb_metabolites.xml")
        print("3. Run: python scripts/build_database.py")
    else:
        print("❌ Please install missing libraries first")

    print("=" * 60)


if __name__ == "__main__":
    main()