#!/usr/bin/env python3
"""
Script to extract and display image information from BDT files with site_id 3938CA.
"""

import sys
from pathlib import Path

from alarm_app.bdt.parser import parse_bdt_file


def show_images(file_path):
    """Parse a BDT file and show image information."""
    print(f"\n{'='*80}")
    print(f"File: {file_path.name}")
    print(f"{'='*80}")
    
    result = parse_bdt_file(str(file_path), skip_photos=False)
    
    print(f"Site code: {result.site_code}")
    print(f"Test date: {result.test_date}")
    print(f"Photo layout ID: {result.photo_layout_id}")
    print(f"Required photo count: {result.required_photo_count}")
    print(f"Total slots: {len(result.photo_slots)}")
    
    filled_slots = 0
    print(f"\n{'='*80}")
    print("Photo Slots:")
    print(f"{'='*80}")
    
    for i, slot in enumerate(result.photo_slots):
        status = "FILLED" if slot.image_data else "EMPTY"
        size = f"{len(slot.image_data)} bytes" if slot.image_data else "N/A"
        print(f"  Slot {i+1}: {slot.label}")
        print(f"    Category: {slot.category}")
        print(f"    Status: {status}")
        print(f"    Size: {size}")
        print(f"    Extension: {slot.image_ext}")
        if slot.image_data:
            filled_slots += 1
            # Show first few bytes as hex to verify it's an image
            hex_preview = slot.image_data[:10].hex()
            print(f"    Data preview (hex): {hex_preview}")
        print()
    
    print(f"{'='*80}")
    print(f"Summary: {filled_slots}/{len(result.photo_slots)} slots filled")
    print(f"{'='*80}")
    
    return result


def main():
    """Extract images from the specific BDT file with site_id 3938CA."""
    # The specific file the user wants
    bdt_file = Path("/Users/mikawi/Developer/orange/data/2024_pm_tests/BDTs/U_S_3938CA_BOLAKDAKROR27_3938CA_BDT.XLSX")
    
    result = show_images(bdt_file)
    
    if result.site_code == "3938CA":
        print(f"\n>>> CONFIRMED site_id 3938CA")
    else:
        print(f"\n>>> Site code is '{result.site_code}' (not 3938CA)")


if __name__ == "__main__":
    main()
