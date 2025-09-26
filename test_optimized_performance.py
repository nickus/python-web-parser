#!/usr/bin/env python3
"""
Тест производительности оптимизированной системы поиска
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models.material import Material, PriceListItem
from src.services.elasticsearch_service import ElasticsearchService
from src.services.elasticsearch_service_optimized import OptimizedElasticsearchService
from src.services.similarity_service import SimilarityService
from src.services.fast_similarity_service import FastSimilarityService
from src.services.matching_service import MaterialMatchingService
from src.services.optimized_matching_service import OptimizedMatchingService
from src.utils.data_loader_fixed import MaterialLoader, PriceListLoader

print("=" * 80)
print("СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ: СТАРАЯ vs ОПТИМИЗИРОВАННАЯ СИСТЕМА")
print("=" * 80)

# Загружаем тестовые данные
print("\nЗагрузка тестовых данных...")
materials = MaterialLoader.load_from_csv("data/sample/materials.csv")
price_items = PriceListLoader.load_from_csv("data/sample/price_list.csv")
print(f"Загружено: {len(materials)} материалов, {len(price_items)} позиций прайс-листа")

# Инициализация старой системы
print("\n" + "=" * 80)
print("ИНИЦИАЛИЗАЦИЯ СТАРОЙ СИСТЕМЫ")
print("=" * 80)

old_es = ElasticsearchService()
old_similarity = SimilarityService()
old_matching = MaterialMatchingService(old_es, old_similarity)

# Инициализация оптимизированной системы
print("\n" + "=" * 80)
print("ИНИЦИАЛИЗАЦИЯ ОПТИМИЗИРОВАННОЙ СИСТЕМЫ")
print("=" * 80)

new_es = OptimizedElasticsearchService()
fast_similarity = FastSimilarityService()
optimized_matching = OptimizedMatchingService(new_es, fast_similarity)

# Проверка подключения
if not old_es.check_connection():
    print("❌ Elasticsearch не доступен!")
    sys.exit(1)

print("✓ Elasticsearch подключен")

# Тестовый материал
test_query = "Светильник потолочный LED 36Вт"
test_material = Material(
    id="test1",
    name=test_query,
    manufacturer="Световые Технологии",
    equipment_code="LED-36W"
)

# ТЕСТ 1: Сравнение поиска в Elasticsearch
print("\n" + "=" * 80)
print("ТЕСТ 1: ПОИСК В ELASTICSEARCH")
print("=" * 80)

# Старая система
start = time.time()
old_es_results = old_es.search_price_list(test_query, size=20)
old_es_time = time.time() - start
print(f"Старая система: {old_es_time:.3f} сек, найдено {len(old_es_results)} результатов")

# Новая система (сначала создаем индекс)
print("\nСоздание оптимизированного индекса...")
new_es.create_optimized_price_list_index()
new_es.index_price_list_optimized(price_items)

start = time.time()
new_es_results = new_es.search_price_list_optimized(test_query, size=20)
new_es_time = time.time() - start
print(f"Новая система: {new_es_time:.3f} сек, найдено {len(new_es_results)} результатов")

speedup = old_es_time / new_es_time if new_es_time > 0 else 0
print(f"⚡ Ускорение: {speedup:.1f}x")

# ТЕСТ 2: Расчет similarity
print("\n" + "=" * 80)
print("ТЕСТ 2: РАСЧЕТ SIMILARITY (10 элементов)")
print("=" * 80)

test_items = price_items[:10]

# Старая система
start = time.time()
for item in test_items:
    old_similarity.calculate_new_material_similarity(test_material, item)
old_sim_time = time.time() - start
print(f"Старая система: {old_sim_time:.3f} сек ({old_sim_time/10:.4f} сек/элемент)")

# Новая система
start = time.time()
for item in test_items:
    fast_similarity.calculate_fast_similarity(test_material, item)
new_sim_time = time.time() - start
print(f"Новая система: {new_sim_time:.3f} сек ({new_sim_time/10:.4f} сек/элемент)")

speedup = old_sim_time / new_sim_time if new_sim_time > 0 else 0
print(f"⚡ Ускорение: {speedup:.1f}x")

# ТЕСТ 3: Полный процесс поиска
print("\n" + "=" * 80)
print("ТЕСТ 3: ПОЛНЫЙ ПРОЦЕСС ПОИСКА")
print("=" * 80)

# Старая система БЕЗ bypass mode
print("\nСтарая система (Elasticsearch mode):")
start = time.time()
old_results = old_matching.match_material_with_price_list(
    test_material,
    similarity_threshold=10.0,
    max_results=5
)
old_total_time = time.time() - start
print(f"Время: {old_total_time:.3f} сек, найдено {len(old_results)} результатов")

# Новая оптимизированная система
print("\nНовая система (оптимизированная):")
start = time.time()
new_results = optimized_matching.match_material_with_price_list(
    test_material,
    similarity_threshold=10.0,
    max_results=5,
    es_top_n=20
)
new_total_time = time.time() - start
print(f"Время: {new_total_time:.3f} сек, найдено {len(new_results)} результатов")

speedup = old_total_time / new_total_time if new_total_time > 0 else 0
print(f"⚡ Ускорение: {speedup:.1f}x")

# Вывод топ результатов
if new_results:
    print("\nТоп-3 результата (новая система):")
    for i, result in enumerate(new_results[:3], 1):
        print(f"  {i}. {result.price_item.name[:50]:50} - {result.similarity_percentage:.1f}%")

# ТЕСТ 4: Пакетная обработка
print("\n" + "=" * 80)
print("ТЕСТ 4: ПАКЕТНАЯ ОБРАБОТКА (5 материалов)")
print("=" * 80)

batch_materials = materials[:5]

# Старая система
print("\nСтарая система:")
start = time.time()
old_batch = old_matching.match_materials_batch(
    batch_materials,
    similarity_threshold=20.0,
    max_results_per_material=3,
    max_workers=2
)
old_batch_time = time.time() - start
print(f"Время: {old_batch_time:.3f} сек ({old_batch_time/5:.3f} сек/материал)")

# Новая система
print("\nНовая система:")
start = time.time()
new_batch = optimized_matching.match_materials_batch(
    batch_materials,
    similarity_threshold=20.0,
    max_results_per_material=3,
    max_workers=2
)
new_batch_time = time.time() - start
print(f"Время: {new_batch_time:.3f} сек ({new_batch_time/5:.3f} сек/материал)")

speedup = old_batch_time / new_batch_time if new_batch_time > 0 else 0
print(f"⚡ Ускорение: {speedup:.1f}x")

# ИТОГОВАЯ СТАТИСТИКА
print("\n" + "=" * 80)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 80)

print("\nВремя выполнения операций:")
print(f"├─ Поиск в Elasticsearch: {old_es_time:.3f}s → {new_es_time:.3f}s")
print(f"├─ Расчет similarity (10): {old_sim_time:.3f}s → {new_sim_time:.3f}s")
print(f"├─ Полный поиск: {old_total_time:.3f}s → {new_total_time:.3f}s")
print(f"└─ Пакетная обработка (5): {old_batch_time:.3f}s → {new_batch_time:.3f}s")

avg_speedup = (
    (old_es_time / new_es_time if new_es_time > 0 else 0) +
    (old_sim_time / new_sim_time if new_sim_time > 0 else 0) +
    (old_total_time / new_total_time if new_total_time > 0 else 0) +
    (old_batch_time / new_batch_time if new_batch_time > 0 else 0)
) / 4

print(f"\n🚀 СРЕДНЕЕ УСКОРЕНИЕ: {avg_speedup:.1f}x")

# Статистика кеша
print("\nСтатистика кеша (новая система):")
cache_stats = optimized_matching.get_cache_stats()
for key, value in cache_stats.items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("ВЫВОДЫ")
print("=" * 80)

if avg_speedup > 10:
    print("✅ ОТЛИЧНО! Оптимизация дала существенное ускорение!")
elif avg_speedup > 5:
    print("✅ ХОРОШО! Система работает значительно быстрее.")
elif avg_speedup > 2:
    print("✅ НЕПЛОХО! Есть заметное улучшение производительности.")
else:
    print("⚠️  Улучшение производительности незначительное.")

if new_total_time < 1.0:
    print("✅ Поиск выполняется менее чем за 1 секунду - отличный результат!")
elif new_total_time < 3.0:
    print("✅ Поиск выполняется за приемлемое время.")
else:
    print("⚠️  Поиск все еще медленный, требуется дополнительная оптимизация.")