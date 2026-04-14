"""
Script to test layout detection on real BDT files to determine if Layout B exists.
"""
__test__ = False

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bdt.parser import parse_bdt_file


def inspect_layout_on_file(file_path):
    """Parse a file and check which layout was detected."""
    try:
        result = parse_bdt_file(str(file_path), skip_photos=True)
        # Determine layout by checking which layout dict was used
        # We can infer this from the rectifier_brand position
        # Layout A: rectifier at (13, 12), Layout B: rectifier at (13, 9)
        # But we don't have direct access to which layout was selected
        # Instead, we'll check if the parsing succeeded with valid data
        
        layout_detected = "Unknown"
        if result.site_code and result.test_date:
            # If both parsed successfully, likely Layout A (most common)
            layout_detected = "Likely Layout A"
        elif result.errors:
            layout_detected = f"Error: {result.errors[0]}"
        else:
            layout_detected = "Parsed but missing key fields"
        
        return {
            "file": file_path.name,
            "site_code": result.site_code,
            "test_date": result.test_date,
            "rectifier_brand": result.rectifier_brand,
            "layout": layout_detected,
            "errors": result.errors,
        }
    except Exception as e:
        return {
            "file": file_path.name,
            "error": str(e),
        }


def main():
    """Test layout detection on sample BDT files."""
    data_dir = Path("/Users/mikawi/Developer/orange/data")
    
    # Find BDT files from test_pms
    test_pms_dir = data_dir / "test_pms"
    bdt_files = list(test_pms_dir.glob("*.xlsx"))
    
    # Also check 2024_pm_tests
    w1_dir = data_dir / "2024_pm_tests" / "W1" / "W1_2024_BDT" / "W1_2024_BDT"
    if w1_dir.exists():
        bdt_files.extend(list(w1_dir.glob("*.xlsx")))
    
    print(f"Found {len(bdt_files)} BDT files to test")
    print("=" * 80)
    
    layout_b_candidates = []
    
    for i, file_path in enumerate(bdt_files[:20]):  # Test first 20 files
        print(f"\n[{i+1}] Testing: {file_path.name}")
        result = inspect_layout_on_file(file_path)
        print(f"  Site code: {result.get('site_code', 'N/A')}")
        print(f"  Test date: {result.get('test_date', 'N/A')}")
        print(f"  Rectifier brand: {result.get('rectifier_brand', 'N/A')}")
        print(f"  Layout: {result.get('layout', 'N/A')}")
        
        if result.get('errors'):
            print(f"  Errors: {result['errors']}")
        
        # Check if this might be Layout B
        # Layout B would have site_code at (4, 9) instead of (4, 12)
        # If parsing failed or site_code is empty, might be Layout B
        if not result.get('site_code') or result.get('errors'):
            layout_b_candidates.append(file_path.name)
    
    print("\n" + "=" * 80)
    print(f"\nLayout B candidates (files with parsing issues): {len(layout_b_candidates)}")
    for name in layout_b_candidates:
        print(f"  - {name}")
    
    if layout_b_candidates:
        print("\nConclusion: Some files may use Layout B - need manual inspection")
    else:
        print("\nConclusion: All tested files appear to use Layout A")
        print("Recommendation: Demote _LAYOUT_B to a comment and simplify _detect_layout")


if __name__ == "__main__":
    main()
