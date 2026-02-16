"""
HMDB XML Inspector
==================

This script examines the actual structure of your HMDB XML file
to see what fields are available and what the namespace is.
"""

import xml.etree.ElementTree as ET

XML_FILE = "data/raw/hmdb_metabolites.xml"


def inspect_xml():
    """Parse first metabolite and show its structure."""

    print("=" * 80)
    print("HMDB XML Structure Inspector")
    print("=" * 80)
    print()

    print(f"Reading: {XML_FILE}\n")

    # Parse just the first metabolite
    context = ET.iterparse(XML_FILE, events=('start', 'end'))
    context = iter(context)

    event, root = next(context)

    print(f"Root element: {root.tag}\n")

    metabolite_count = 0

    for event, elem in context:
        # Look for metabolite entries
        if event == 'end' and ('metabolite' in elem.tag.lower()):
            metabolite_count += 1

            print(f"Found metabolite #{metabolite_count}")
            print(f"Tag: {elem.tag}")
            print(f"\nAll child elements found:\n")
            print("-" * 80)

            # Print all child elements and their values
            for child in elem:
                # Clean up the tag name
                tag = child.tag
                if '}' in tag:
                    namespace, tag_name = tag.split('}')
                    namespace = namespace + '}'
                else:
                    tag_name = tag
                    namespace = "No namespace"

                value = child.text
                if value:
                    value = value[:100]  # Truncate long values

                print(f"{tag_name:<40} = {value}")

            print("-" * 80)

            # Clear memory
            elem.clear()
            root.clear()

            # Only look at first metabolite
            if metabolite_count >= 1:
                break

    print("\n" + "=" * 80)
    print("Inspection complete!")
    print("\nLook for fields like:")
    print("  - accession (HMDB ID)")
    print("  - name")
    print("  - chemical_formula or formula")
    print("  - monoisotopic_molecular_weight or monoisotopic_mass")
    print("=" * 80)


if __name__ == "__main__":
    inspect_xml()