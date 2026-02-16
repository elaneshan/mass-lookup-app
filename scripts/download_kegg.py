"""
KEGG COMPOUND Data Downloader
==============================

Downloads KEGG COMPOUND database via REST API.

KEGG provides a free REST API for bulk downloads.
This is legal and encouraged by KEGG for academic use.

Usage:
    python scripts/download_kegg.py
"""

import urllib.request
import os
from pathlib import Path

KEGG_COMPOUND_URL = "https://rest.kegg.jp/list/compound"
OUTPUT_FILE = "data/raw/kegg_compound.txt"


def download_kegg():
    """Download KEGG COMPOUND database."""

    print("=" * 80)
    print("KEGG COMPOUND Downloader")
    print("=" * 80)
    print()

    # Create directory if needed
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    print(f"Downloading from: {KEGG_COMPOUND_URL}")
    print(f"Saving to: {OUTPUT_FILE}")
    print("\nThis may take a few minutes...")
    print()

    try:
        # Download with progress
        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(downloaded * 100 / total_size, 100)
                print(f"\rProgress: {percent:.1f}% ({downloaded:,} / {total_size:,} bytes)", end='')

        urllib.request.urlretrieve(
            KEGG_COMPOUND_URL,
            OUTPUT_FILE,
            reporthook=report_progress
        )

        print("\n")

        # Verify file
        file_size = os.path.getsize(OUTPUT_FILE)
        print(f"✓ Download complete!")
        print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")

        # Count entries
        with open(OUTPUT_FILE, 'r') as f:
            lines = f.readlines()
            compound_count = len(lines)

        print(f"  Compounds: ~{compound_count:,}")
        print()
        print("✅ KEGG data ready for import")
        print(f"\nNext step: python scripts/build_database_v2.py")

    except Exception as e:
        print(f"\n❌ Error downloading KEGG data: {e}")
        print("\nAlternative: Download manually from:")
        print("  https://rest.kegg.jp/list/compound")
        print(f"  and save to: {OUTPUT_FILE}")


if __name__ == "__main__":
    download_kegg()