#!/usr/bin/env python3
"""
Simple test for new data structure fixes
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models.material import Material, PriceListItem
from src.services.similarity_service import SimilarityService

def test_new_structure():
    """Test the new data structure"""
    print("[TEST] Testing new data structure...")
    
    # Create test material in new format
    material = Material(
        id="MAT001",
        name="Кабель ВВГНГ 3x2.5",
        type_mark="ВВГНГ",
        equipment_code="K-VVGNG-3x2.5",
        manufacturer="Севкабель",
        unit="м",
        quantity=100.0
    )
    
    # Create test price list item in new format
    price_item = PriceListItem(
        id="P001",
        name="Кабель ВВГНГ 3х2,5 мм2",
        brand="Севкабель-Холдинг",
        article="K-VVGNG-3x2.5",
        brand_code="SEVK",
        class_code="CAB01",
        price=125.50
    )
    
    print(f"[OK] Material created: {material.name}")
    print(f"[OK] Price list item created: {price_item.name}")
    
    # Test new similarity algorithm
    similarity_service = SimilarityService()
    similarity_percentage, details = similarity_service.calculate_new_material_similarity(
        material, price_item
    )
    
    print(f"\n[RESULTS] Comparison results:")
    print(f"   Overall relevance: {similarity_percentage:.1f}%")
    print(f"   Names: {details['name_similarity']:.1f}%")
    print(f"   Article/Code: {details['article_similarity']:.1f}%")
    print(f"   Brand/Manufacturer: {details['brand_similarity']:.1f}%")
    
    success = similarity_percentage >= 70.0
    print(f"\n[FINAL] Test result: {'PASS' if success else 'FAIL'} ({similarity_percentage:.1f}%)")
    
    return success

if __name__ == "__main__":
    try:
        success = test_new_structure()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)