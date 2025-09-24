#!/usr/bin/env python3
"""
Simple Performance Test for Elasticsearch optimizations
Testing the key performance improvements without unicode issues
"""

import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import services
from src.services.elasticsearch_service import ElasticsearchService
from src.models.material import Material, PriceListItem


def test_basic_functionality():
    """Test basic Elasticsearch functionality and performance"""
    print("=" * 50)
    print("ELASTICSEARCH PERFORMANCE TEST")
    print("=" * 50)
    
    # Initialize optimized service
    es_service = ElasticsearchService(
        host='localhost',
        port=9200,
        bulk_size=1000,
        max_workers=6
    )
    
    results = {}
    
    # Test 1: Connection
    print("\n1. Testing connection...")
    start = time.time()
    connected = es_service.check_connection()
    connection_time = time.time() - start
    
    results['connection'] = {
        'success': connected,
        'time_ms': round(connection_time * 1000, 2)
    }
    
    if connected:
        print(f"   Connection: OK ({connection_time:.3f}s)")
    else:
        print(f"   Connection: FAILED")
        return results
    
    # Test 2: Index Creation
    print("\n2. Creating optimized indices...")
    start = time.time()
    
    materials_ok = es_service.create_materials_index()
    price_ok = es_service.create_price_list_index()
    
    index_time = time.time() - start
    
    results['index_creation'] = {
        'materials': materials_ok,
        'price_list': price_ok,
        'time_ms': round(index_time * 1000, 2)
    }
    
    print(f"   Materials index: {'OK' if materials_ok else 'FAILED'}")
    print(f"   Price list index: {'OK' if price_ok else 'FAILED'}")
    print(f"   Creation time: {index_time:.3f}s")
    
    if not (materials_ok and price_ok):
        print("   Index creation failed!")
        return results
    
    # Test 3: Generate test data
    print("\n3. Generating test data...")
    
    # Create test materials
    test_materials = []
    for i in range(50):
        material = Material(
            id=f"test_mat_{i}",
            name=f"Кабель тестовый {i+1}",
            description=f"Тестовый кабель номер {i+1}",
            category="Кабели",
            brand="TestBrand",
            specifications={"test": f"value_{i}"}
        )
        test_materials.append(material)
    
    # Create test price items
    test_price_items = []
    for i in range(30):
        price_item = PriceListItem(
            id=f"test_price_{i}",
            material_name=f"Материал тестовый {i+1}",
            price=100.0 + i * 10,
            currency="RUB",
            supplier="TestSupplier",
            description=f"Тестовый материал {i+1}"
        )
        test_price_items.append(price_item)
    
    print(f"   Generated {len(test_materials)} materials and {len(test_price_items)} price items")
    
    # Test 4: Bulk indexing performance
    print("\n4. Testing bulk indexing performance...")
    
    start = time.time()
    materials_indexed = es_service.index_materials(test_materials)
    materials_time = time.time() - start
    
    start = time.time()
    prices_indexed = es_service.index_price_list(test_price_items)
    prices_time = time.time() - start
    
    materials_rate = len(test_materials) / materials_time if materials_time > 0 else 0
    prices_rate = len(test_price_items) / prices_time if prices_time > 0 else 0
    
    results['bulk_indexing'] = {
        'materials': {
            'success': materials_indexed,
            'count': len(test_materials),
            'time_s': round(materials_time, 3),
            'docs_per_sec': round(materials_rate, 1)
        },
        'prices': {
            'success': prices_indexed,
            'count': len(test_price_items),
            'time_s': round(prices_time, 3),
            'docs_per_sec': round(prices_rate, 1)
        }
    }
    
    print(f"   Materials indexing: {'OK' if materials_indexed else 'FAILED'}")
    print(f"     {len(test_materials)} docs in {materials_time:.3f}s ({materials_rate:.1f} docs/sec)")
    print(f"   Price list indexing: {'OK' if prices_indexed else 'FAILED'}")
    print(f"     {len(test_price_items)} docs in {prices_time:.3f}s ({prices_rate:.1f} docs/sec)")
    
    # Wait a moment for indexing to complete
    time.sleep(2)
    
    # Test 5: Search performance
    print("\n5. Testing search performance...")
    
    test_queries = ["кабель", "тестовый", "материал"]
    search_results = []
    
    for query in test_queries:
        # Regular search
        start = time.time()
        materials = es_service.search_materials(query, 10)
        search_time = time.time() - start
        
        # Cached search (if available)
        cached_time = 0
        try:
            start = time.time()
            cached_materials = es_service.search_materials_cached(query, 10)
            cached_time = time.time() - start
        except:
            cached_materials = []
        
        search_results.append({
            'query': query,
            'materials_found': len(materials),
            'search_time_ms': round(search_time * 1000, 2),
            'cached_time_ms': round(cached_time * 1000, 2) if cached_time > 0 else 0
        })
        
        print(f"   Query '{query}': {len(materials)} results in {search_time*1000:.2f}ms")
        if cached_time > 0:
            print(f"     Cached: {cached_time*1000:.2f}ms")
    
    results['search_performance'] = search_results
    
    # Test 6: Performance statistics
    print("\n6. Getting performance statistics...")
    
    try:
        perf_stats = es_service.get_performance_stats()
        print(f"   Total indexed docs: {perf_stats.get('total_indexed_documents', 0)}")
        print(f"   Average docs/sec: {perf_stats.get('average_documents_per_second', 0)}")
        print(f"   Bulk operations: {perf_stats.get('bulk_operations_count', 0)}")
        
        results['performance_stats'] = perf_stats
    except Exception as e:
        print(f"   Performance stats error: {e}")
        results['performance_stats'] = {}
    
    # Test 7: Index optimization
    print("\n7. Testing index optimization...")
    
    try:
        start = time.time()
        optimization_ok = es_service.optimize_indices_for_search()
        optimization_time = time.time() - start
        
        print(f"   Index optimization: {'OK' if optimization_ok else 'FAILED'}")
        print(f"   Optimization time: {optimization_time:.3f}s")
        
        results['optimization'] = {
            'success': optimization_ok,
            'time_s': round(optimization_time, 3)
        }
    except Exception as e:
        print(f"   Optimization error: {e}")
        results['optimization'] = {'success': False, 'error': str(e)}
    
    # Final summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    total_tests = 0
    passed_tests = 0
    
    if results['connection']['success']:
        passed_tests += 1
    total_tests += 1
    
    if results['index_creation']['materials'] and results['index_creation']['price_list']:
        passed_tests += 1
    total_tests += 1
    
    if results['bulk_indexing']['materials']['success'] and results['bulk_indexing']['prices']['success']:
        passed_tests += 1
    total_tests += 1
    
    if any(r['materials_found'] > 0 for r in results['search_performance']):
        passed_tests += 1
    total_tests += 1
    
    if results.get('optimization', {}).get('success', False):
        passed_tests += 1
    total_tests += 1
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"Tests passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
    
    if passed_tests == total_tests:
        print("All tests PASSED! Optimizations are working correctly.")
    else:
        print("Some tests FAILED. Check the details above.")
    
    # Save results
    results['summary'] = {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'success_rate': success_rate,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save to file
    report_file = f"performance_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed report saved to: {report_file}")
    
    return results


if __name__ == "__main__":
    try:
        results = test_basic_functionality()
        
        # Return appropriate exit code
        if results.get('summary', {}).get('success_rate', 0) >= 80:
            print("\nSUCCESS: Performance optimizations working well!")
            sys.exit(0)
        else:
            print("\nFAILED: Some optimizations need attention.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        sys.exit(2)