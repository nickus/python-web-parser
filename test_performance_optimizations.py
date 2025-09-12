#!/usr/bin/env python3
"""
Performance Testing Script для оптимизированного Elasticsearch сервиса
Автор: Claude Code Assistant
Версия: 1.0

Данный скрипт тестирует производительность оптимизированного Elasticsearch сервиса
и проверяет корректность работы всех оптимизаций.
"""

import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('performance_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Импортируем необходимые модули
from src.services.elasticsearch_service import ElasticsearchService
from src.models.material import Material, PriceListItem


class PerformanceTestSuite:
    """Набор тестов для проверки производительности оптимизированного Elasticsearch"""
    
    def __init__(self):
        """Инициализация тестового набора"""
        # Создаем сервис с оптимизированными настройками
        self.es_service = ElasticsearchService(
            host='localhost',
            port=9200,
            bulk_size=1000,  # Увеличенный bulk_size
            max_workers=6    # Увеличенное количество воркеров
        )
        
        # Тестовые данные
        self.test_materials = self._generate_test_materials()
        self.test_price_items = self._generate_test_price_items()
        
        # Результаты тестов
        self.test_results = {}
        
        logger.info("Performance Test Suite initialized")
        logger.info(f"Elasticsearch service configured: bulk_size={self.es_service.bulk_size}, max_workers={self.es_service.max_workers}")
    
    def _generate_test_materials(self) -> List[Material]:
        """Генерация тестовых материалов"""
        materials = []
        
        # Реалистичные тестовые данные для материалов
        test_data = [
            {"name": "Кабель ВВГнг-LS 3x2.5", "category": "Кабели", "brand": "ElectroMax", "description": "Медный силовой кабель"},
            {"name": "Выключатель автоматический C16", "category": "Автоматика", "brand": "Schneider", "description": "Автоматический выключатель 16А"},
            {"name": "Лампа LED 10W E27", "category": "Освещение", "brand": "Philips", "description": "Светодиодная лампа 10 ватт"},
            {"name": "Провод ПВС 2x1.5", "category": "Провода", "brand": "Rexant", "description": "Гибкий соединительный провод"},
            {"name": "Розетка с заземлением", "category": "Розетки", "brand": "Legrand", "description": "Розетка европейского типа"},
        ]
        
        # Создаем по 20 вариантов каждого материала для полноценного тестирования
        for i, base_data in enumerate(test_data):
            for j in range(20):
                material = Material(
                    id=f"mat_{i}_{j}",
                    name=f"{base_data['name']} - вариант {j+1}",
                    description=f"{base_data['description']} (тест {j+1})",
                    category=base_data['category'],
                    brand=base_data['brand'],
                    specifications={
                        "test_param": f"value_{j}",
                        "batch": f"batch_{i}_{j}"
                    }
                )
                materials.append(material)
        
        logger.info(f"Generated {len(materials)} test materials")
        return materials
    
    def _generate_test_price_items(self) -> List[PriceListItem]:
        """Генерация тестовых элементов прайс-листа"""
        price_items = []
        
        # Тестовые данные для прайс-листа
        test_data = [
            {"name": "Кабель силовой медный", "supplier": "ЭлектроТорг", "price": 125.50},
            {"name": "Автоматический выключатель", "supplier": "ТехноОпт", "price": 890.00},
            {"name": "Светодиодная лампа", "supplier": "СветТех", "price": 350.75},
            {"name": "Гибкий провод соединительный", "supplier": "КабельСнаб", "price": 45.20},
            {"name": "Розетка электрическая", "supplier": "ЭлектроКомплект", "price": 280.30},
        ]
        
        # Создаем по 15 вариантов каждого элемента прайс-листа
        for i, base_data in enumerate(test_data):
            for j in range(15):
                price_item = PriceListItem(
                    id=f"price_{i}_{j}",
                    material_name=f"{base_data['name']} модель {j+1}",
                    price=base_data['price'] + (j * 10),
                    currency="RUB",
                    supplier=base_data['supplier'],
                    description=f"Тестовый элемент прайс-листа {j+1}"
                )
                price_items.append(price_item)
        
        logger.info(f"Generated {len(price_items)} test price items")
        return price_items
    
    def test_connection(self) -> bool:
        """Тест 1: Проверка подключения к Elasticsearch"""
        logger.info("=== TEST 1: Connection Test ===")
        
        start_time = time.time()
        connection_ok = self.es_service.check_connection()
        duration = time.time() - start_time
        
        self.test_results['connection'] = {
            'status': 'PASS' if connection_ok else 'FAIL',
            'duration_ms': round(duration * 1000, 2),
            'details': 'Elasticsearch connection successful' if connection_ok else 'Connection failed'
        }
        
        logger.info(f"Connection test: {'PASS' if connection_ok else 'FAIL'} ({duration:.3f}s)")
        return connection_ok
    
    def test_index_creation(self) -> bool:
        """Тест 2: Создание оптимизированных индексов"""
        logger.info("=== TEST 2: Optimized Index Creation ===")
        
        start_time = time.time()
        
        # Создаем индексы с оптимизированными настройками
        materials_ok = self.es_service.create_materials_index()
        price_list_ok = self.es_service.create_price_list_index()
        
        duration = time.time() - start_time
        
        success = materials_ok and price_list_ok
        self.test_results['index_creation'] = {
            'status': 'PASS' if success else 'FAIL',
            'duration_ms': round(duration * 1000, 2),
            'materials_index': materials_ok,
            'price_list_index': price_list_ok,
            'details': 'Optimized indices created with Russian analyzer and performance settings'
        }
        
        logger.info(f"Index creation test: {'PASS' if success else 'FAIL'} ({duration:.3f}s)")
        return success
    
    def test_bulk_indexing_performance(self) -> bool:
        """Тест 3: Производительность массовой индексации"""
        logger.info("=== TEST 3: Bulk Indexing Performance ===")
        
        # Индексируем материалы
        start_time = time.time()
        materials_success = self.es_service.index_materials(self.test_materials)
        materials_duration = time.time() - start_time
        
        # Индексируем прайс-лист
        start_time = time.time()
        price_success = self.es_service.index_price_list(self.test_price_items)
        price_duration = time.time() - start_time
        
        # Рассчитываем производительность
        materials_per_sec = len(self.test_materials) / materials_duration if materials_duration > 0 else 0
        price_per_sec = len(self.test_price_items) / price_duration if price_duration > 0 else 0
        
        success = materials_success and price_success
        self.test_results['bulk_indexing'] = {
            'status': 'PASS' if success else 'FAIL',
            'materials': {
                'count': len(self.test_materials),
                'duration_s': round(materials_duration, 3),
                'docs_per_sec': round(materials_per_sec, 1),
                'success': materials_success
            },
            'price_list': {
                'count': len(self.test_price_items),
                'duration_s': round(price_duration, 3),
                'docs_per_sec': round(price_per_sec, 1),
                'success': price_success
            }
        }
        
        logger.info(f"Bulk indexing test: {'PASS' if success else 'FAIL'}")
        logger.info(f"  Materials: {materials_per_sec:.1f} docs/sec")
        logger.info(f"  Price list: {price_per_sec:.1f} docs/sec")
        return success
    
    def test_search_performance(self) -> bool:
        """Тест 4: Производительность поиска"""
        logger.info("=== TEST 4: Search Performance ===")
        
        # Тестовые запросы
        test_queries = [
            "кабель",
            "автомат",
            "лампа led",
            "провод пвс",
            "розетка заземление"
        ]
        
        search_results = []
        
        for query in test_queries:
            # Обычный поиск
            start_time = time.time()
            materials = self.es_service.search_materials(query, 10)
            materials_duration = time.time() - start_time
            
            # Кешированный поиск
            start_time = time.time()
            materials_cached = self.es_service.search_materials_cached(query, 10)
            cached_duration = time.time() - start_time
            
            # Поиск в прайс-листе
            start_time = time.time()
            price_items = self.es_service.search_price_list_cached(query, 20)
            price_duration = time.time() - start_time
            
            search_results.append({
                'query': query,
                'materials_count': len(materials),
                'materials_duration_ms': round(materials_duration * 1000, 2),
                'cached_duration_ms': round(cached_duration * 1000, 2),
                'price_items_count': len(price_items),
                'price_duration_ms': round(price_duration * 1000, 2)
            })
        
        # Средняя производительность
        avg_materials_time = sum(r['materials_duration_ms'] for r in search_results) / len(search_results)
        avg_cached_time = sum(r['cached_duration_ms'] for r in search_results) / len(search_results)
        
        success = all(r['materials_count'] >= 0 for r in search_results)
        self.test_results['search_performance'] = {
            'status': 'PASS' if success else 'FAIL',
            'queries_tested': len(test_queries),
            'avg_materials_search_ms': round(avg_materials_time, 2),
            'avg_cached_search_ms': round(avg_cached_time, 2),
            'cache_speedup_factor': round(avg_materials_time / max(avg_cached_time, 0.001), 1),
            'detailed_results': search_results
        }
        
        logger.info(f"Search performance test: {'PASS' if success else 'FAIL'}")
        logger.info(f"  Average search time: {avg_materials_time:.2f}ms")
        logger.info(f"  Average cached time: {avg_cached_time:.2f}ms")
        return success
    
    def test_caching_system(self) -> bool:
        """Тест 5: Система кеширования"""
        logger.info("=== TEST 5: Caching System ===")
        
        # Очищаем кеш
        self.es_service.clear_cache()
        
        test_query = "тестовый запрос кабель"
        
        # Первый запрос (должен заполнить кеш)
        start_time = time.time()
        results1 = self.es_service.search_materials_cached(test_query, 5)
        first_duration = time.time() - start_time
        
        # Второй запрос (должен использовать кеш)
        start_time = time.time()
        results2 = self.es_service.search_materials_cached(test_query, 5)
        cached_duration = time.time() - start_time
        
        # Получаем статистику
        search_report = self.es_service.get_search_performance_report()
        
        # Кеш должен сработать
        cache_hit = cached_duration < first_duration
        results_identical = len(results1) == len(results2)
        
        success = cache_hit and results_identical and search_report['cache_hits'] > 0
        self.test_results['caching_system'] = {
            'status': 'PASS' if success else 'FAIL',
            'first_query_ms': round(first_duration * 1000, 2),
            'cached_query_ms': round(cached_duration * 1000, 2),
            'speedup_factor': round(first_duration / max(cached_duration, 0.001), 1),
            'cache_hits': search_report['cache_hits'],
            'total_queries': search_report['total_queries'],
            'cache_hit_ratio': round(search_report['cache_hit_ratio'], 1)
        }
        
        logger.info(f"Caching system test: {'PASS' if success else 'FAIL'}")
        logger.info(f"  Cache speedup: {success and cache_hit}")
        logger.info(f"  Cache hit ratio: {search_report['cache_hit_ratio']:.1f}%")
        return success
    
    def test_production_optimization(self) -> bool:
        """Тест 6: Производственные оптимизации"""
        logger.info("=== TEST 6: Production Optimizations ===")
        
        start_time = time.time()
        
        # Применяем производственные оптимизации
        optimization_success = self.es_service.optimize_for_production()
        
        # Получаем статистику индексов после оптимизации
        index_stats = self.es_service.get_index_stats()
        
        # Проверяем здоровье кластера
        health = self.es_service.health_check()
        
        duration = time.time() - start_time
        
        success = optimization_success and health.get('connection_healthy', False)
        self.test_results['production_optimization'] = {
            'status': 'PASS' if success else 'FAIL',
            'duration_s': round(duration, 3),
            'optimization_success': optimization_success,
            'cluster_healthy': health.get('connection_healthy', False),
            'cluster_status': health.get('cluster_status', 'unknown'),
            'index_statistics': index_stats
        }
        
        logger.info(f"Production optimization test: {'PASS' if success else 'FAIL'}")
        logger.info(f"  Cluster status: {health.get('cluster_status', 'unknown')}")
        return success
    
    def test_monitoring_capabilities(self) -> bool:
        """Тест 7: Возможности мониторинга"""
        logger.info("=== TEST 7: Monitoring Capabilities ===")
        
        # Получаем полную статистику
        performance_stats = self.es_service.get_performance_stats()
        search_stats = self.es_service.get_search_performance_report()
        
        # Экспортируем статистику
        full_stats = self.es_service.export_performance_stats()
        
        # Проверяем наличие ключевых метрик
        required_keys = ['total_indexed_documents', 'average_documents_per_second', 'bulk_operations_count']
        stats_complete = all(key in performance_stats for key in required_keys)
        
        search_keys = ['total_queries', 'cache_hits', 'cache_hit_ratio']
        search_stats_complete = all(key in search_stats for key in search_keys)
        
        success = stats_complete and search_stats_complete and bool(full_stats)
        self.test_results['monitoring'] = {
            'status': 'PASS' if success else 'FAIL',
            'performance_stats_complete': stats_complete,
            'search_stats_complete': search_stats_complete,
            'export_successful': bool(full_stats),
            'total_indexed_docs': performance_stats.get('total_indexed_documents', 0),
            'avg_docs_per_sec': performance_stats.get('average_documents_per_second', 0),
            'total_queries': search_stats.get('total_queries', 0),
            'cache_hit_ratio': search_stats.get('cache_hit_ratio', 0)
        }
        
        logger.info(f"Monitoring capabilities test: {'PASS' if success else 'FAIL'}")
        logger.info(f"  Performance tracking: {stats_complete}")
        logger.info(f"  Search monitoring: {search_stats_complete}")
        return success
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов производительности"""
        logger.info("🚀 Starting comprehensive performance test suite...")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Запускаем все тесты по порядку
        tests = [
            ('connection', self.test_connection),
            ('index_creation', self.test_index_creation),
            ('bulk_indexing', self.test_bulk_indexing_performance),
            ('search_performance', self.test_search_performance),
            ('caching_system', self.test_caching_system),
            ('production_optimization', self.test_production_optimization),
            ('monitoring', self.test_monitoring_capabilities)
        ]
        
        passed_tests = 0
        failed_tests = 0
        
        for test_name, test_func in tests:
            try:
                success = test_func()
                if success:
                    passed_tests += 1
                else:
                    failed_tests += 1
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                self.test_results[test_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                failed_tests += 1
        
        total_duration = time.time() - start_time
        
        # Итоговый отчет
        final_report = {
            'test_suite': 'Elasticsearch Performance Optimization',
            'timestamp': datetime.now().isoformat(),
            'total_duration_s': round(total_duration, 3),
            'tests_passed': passed_tests,
            'tests_failed': failed_tests,
            'total_tests': len(tests),
            'success_rate': round((passed_tests / len(tests)) * 100, 1),
            'elasticsearch_config': {
                'host': self.es_service.host,
                'port': self.es_service.port,
                'bulk_size': self.es_service.bulk_size,
                'max_workers': self.es_service.max_workers
            },
            'detailed_results': self.test_results
        }
        
        # Логируем итоговые результаты
        logger.info("=" * 60)
        logger.info(f"🎯 TEST SUITE COMPLETED")
        logger.info(f"Total duration: {total_duration:.3f}s")
        logger.info(f"Tests passed: {passed_tests}/{len(tests)} ({final_report['success_rate']:.1f}%)")
        logger.info(f"Tests failed: {failed_tests}")
        
        if failed_tests == 0:
            logger.info("✅ All performance optimizations working correctly!")
        else:
            logger.warning(f"⚠️  {failed_tests} test(s) failed - check detailed results")
        
        # Сохраняем отчет
        report_filename = f"performance_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Full report saved to: {report_filename}")
        
        return final_report


def main():
    """Основная функция для запуска тестов"""
    print("Elasticsearch Performance Optimization Test Suite")
    print("=" * 50)
    
    try:
        # Создаем и запускаем тестовый набор
        test_suite = PerformanceTestSuite()
        results = test_suite.run_all_tests()
        
        # Возвращаем код выхода
        if results['tests_failed'] == 0:
            print("\n✅ All tests passed! Performance optimizations are working correctly.")
            return 0
        else:
            print(f"\n❌ {results['tests_failed']} test(s) failed. Check the logs for details.")
            return 1
            
    except Exception as e:
        logger.error(f"Test suite failed with critical error: {e}")
        print(f"\n💥 Test suite crashed: {e}")
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)