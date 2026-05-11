#!/usr/bin/env python
"""Main entry point for running the complete pipeline: preprocess → OCR → parser."""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.preprocess import preprocess_one_image
from src.ocr import extract_text
from src.parser import parse_ocr_results


def run_full_pipeline(image_name: str = "price_01.jpg"):
    """
    Run complete pipeline: preprocess → OCR → parse results.
    
    Args:
        image_name: Image filename (e.g., 'price_01.jpg')
        
    Returns:
        Dict with parsed results
    """
    print("=" * 60)
    print(f"🚀 Running full pipeline for: {image_name}")
    print("=" * 60)
    
    # Step 1: Preprocess image
    print("\n📸 STEP 1: Preprocessing image...")
    print("-" * 60)
    try:
        preprocess_one_image(image_name)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return None
    
    # Step 2: Run OCR on preprocessed image
    print("\n🔍 STEP 2: Running OCR on preprocessed image...")
    print("-" * 60)
    try:
        ocr_results = extract_text(image_name, use_processed=True)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return None
    
    # Step 3: Parse OCR results
    print("\n📊 STEP 3: Parsing OCR results...")
    print("-" * 60)
    
    parsed = parse_ocr_results(ocr_results)
    
    # Display parsed results
    print("\n✅ PARSED RESULTS:")
    print("=" * 60)
    
    if parsed["price"] is not None:
        print(f"💰 Price: {parsed['price']:.2f} руб")
    else:
        print("❌ Price: Not found")
    
    if parsed["date"] is not None:
        print(f"📅 Date: {parsed['date']}")
    else:
        print("❌ Date: Not found")
    
    if parsed["code"] is not None:
        print(f"🏷️  Product Code: {parsed['code']}")
    else:
        print("❌ Code: Not found")
    
    print("=" * 60)
    
    return parsed


if __name__ == "__main__":
    # Can run as: python run.py [image_name]
    image_name = sys.argv[1] if len(sys.argv) > 1 else "price_02.jpg"
    result = run_full_pipeline(image_name)
