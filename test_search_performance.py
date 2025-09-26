#!/usr/bin/env python3
"""
Тест производительности поиска и выявление узких мест
"""

import sys
import os
import time
import cProfile
import pstats
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models.material import Material, PriceListItem
from src.services.elasticsearch_service import ElasticsearchService
from src.services.similarity_service import SimilarityService
from src.services.matching_service import MaterialMatchingService

print("=" * 80)
print("ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ПОИСКА")
print("=" * 80)

# Инициализация сервисов
es_service = ElasticsearchService()
similarity_service = SimilarityService()
matching_service = MaterialMatchingService(es_service, similarity_service)

# Проверка подключения
if not es_service.check_connection():
    print("❌ Elasticsearch не доступен!")
    sys.exit(1)

print("✓ Elasticsearch подключен")

# Тест 1: Простой поиск в Elasticsearch
print("\n" + "=" * 80)
print("ТЕСТ 1: Прямой поиск в Elasticsearch")
print("=" * 80)

query = "Светильник потолочный LED 36Вт"
print(f"Запрос: {query}")

start_time = time.time()
results = es_service.search_price_list(query, size=50)
es_time = time.time() - start_time

print(f"Время поиска в Elasticsearch: {es_time:.3f} сек")
print(f"Найдено результатов: {len(results)}")

# Тест 2: Поиск с расчетом similarity (без оптимизации)
print("\n" + "=" * 80)
print("ТЕСТ 2: Поиск с расчетом similarity")
print("=" * 80)

# Создаем тестовый материал
test_material = Material(
    id="test1",
    name="Светильник потолочный LED 36Вт",
    manufacturer="Световые Технологии",
    equipment_code="LED-36W"
)

print(f"Материал: {test_material.name}")
print("Расчет similarity для первых 10 результатов...")

# Профилируем расчет similarity
profiler = cProfile.Profile()
profiler.enable()

start_time = time.time()
similarity_results = []

for i, es_result in enumerate(results[:10]):
    price_item_data = es_result['_source']
    price_item = PriceListItem.from_dict(price_item_data)

    # Расчет similarity
    sim_start = time.time()
    similarity, details = similarity_service.calculate_new_material_similarity(
        test_material, price_item
    )
    sim_time = time.time() - sim_start

    similarity_results.append((price_item.name, similarity, sim_time))
    print(f"  {i+1}. {price_item.name[:50]:50} - {similarity:.1f}% ({sim_time:.3f} сек)")

total_sim_time = time.time() - start_time

profiler.disable()

print(f"\nОбщее время расчета similarity: {total_sim_time:.3f} сек")
print(f"Среднее время на один элемент: {total_sim_time/10:.3f} сек")

# Анализ профилирования
print("\n" + "=" * 80)
print("АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ")
print("=" * 80)

s = StringIO()
ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
ps.print_stats(15)  # Топ 15 самых медленных функций

print("Топ самых медленных функций:")
print(s.getvalue())

# Тест 3: Полный поиск через matching_service
print("\n" + "=" * 80)
print("ТЕСТ 3: Полный поиск через matching_service")
print("=" * 80)

start_time = time.time()
full_results = matching_service.match_material_with_price_list(
    test_material,
    similarity_threshold=10.0,
    max_results=5
)
full_time = time.time() - start_time

print(f"Время полного поиска: {full_time:.3f} сек")
print(f"Найдено результатов: {len(full_results)}")

if full_results:
    print("\nТоп результаты:")
    for i, result in enumerate(full_results[:5], 1):
        print(f"  {i}. {result.price_item.name[:50]:50} - {result.similarity_percentage:.1f}%")

# Выводы
print("\n" + "=" * 80)
print("ВЫВОДЫ")
print("=" * 80)

print(f"1. Поиск в Elasticsearch: {es_time:.3f} сек")
print(f"2. Расчет similarity (10 элементов): {total_sim_time:.3f} сек")
print(f"3. Полный процесс поиска: {full_time:.3f} сек")

if total_sim_time > 1.0:
    print("\n⚠️  ПРОБЛЕМА: Расчет similarity слишком медленный!")
    print("   Рекомендации:")
    print("   - Кешировать результаты нормализации текста")
    print("   - Упростить регулярные выражения")
    print("   - Использовать более быстрые алгоритмы сравнения")
    print("   - Предварительно рассчитывать similarity при индексации")

if full_time > 5.0:
    print("\n⚠️  КРИТИЧЕСКАЯ ПРОБЛЕМА: Полный поиск занимает больше 5 секунд!")
    print("   Необходима серьезная оптимизация!")