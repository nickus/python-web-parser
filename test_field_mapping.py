#!/usr/bin/env python3
"""
Тест маппинга полей между старым и новым форматом
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.data_loader_fixed import MaterialLoader, PriceListLoader
from src.services.similarity_service import SimilarityService

# Загружаем данные
print("=" * 80)
print("ЗАГРУЗКА ДАННЫХ")
print("=" * 80)

# Загружаем материалы
materials = MaterialLoader.load_from_csv("data/sample/materials.csv")
print(f"\nЗагружено материалов: {len(materials)}")

if materials:
    mat = materials[0]
    print(f"\nПример материала:")
    print(f"  name: {mat.name}")
    print(f"  brand (старое): {mat.brand}")
    print(f"  model (старое): {mat.model}")
    print(f"  manufacturer (новое): {mat.manufacturer}")
    print(f"  equipment_code (новое): {mat.equipment_code}")
    print(f"  type_mark (новое): {mat.type_mark}")

# Загружаем прайс-лист
price_items = PriceListLoader.load_from_csv("data/sample/price_list.csv")
print(f"\nЗагружено позиций прайс-листа: {len(price_items)}")

if price_items:
    item = price_items[0]
    print(f"\nПример позиции прайс-листа:")
    print(f"  name: {item.name}")
    print(f"  material_name (старое): {item.material_name}")
    print(f"  brand: {item.brand}")
    print(f"  article (новое): {item.article}")
    print(f"  class_code (новое): {item.class_code}")

print("\n" + "=" * 80)
print("ТЕСТ СОПОСТАВЛЕНИЯ")
print("=" * 80)

# Тестируем сопоставление
similarity_service = SimilarityService()

# Берем первый материал и сопоставляем с прайс-листом
if materials and price_items:
    material = materials[0]  # Кабель ВВГНГ-LS 3x2.5

    print(f"\nМатериал: {material.name}")
    print(f"  Производитель: {material.manufacturer}")
    print(f"  Код: {material.equipment_code}")
    print("-" * 50)

    # Сопоставляем со всеми позициями прайс-листа
    results = []
    for price_item in price_items[:5]:  # Первые 5 для теста
        similarity, details = similarity_service.calculate_new_material_similarity(
            material, price_item
        )
        results.append((price_item, similarity, details))

    # Сортируем по похожести
    results.sort(key=lambda x: x[1], reverse=True)

    print("\nРезультаты сопоставления:")
    for price_item, similarity, details in results:
        print(f"\n[{similarity:6.2f}%] {price_item.name}")
        print(f"  Бренд: {price_item.brand}, Артикул: {price_item.article}")
        print(f"  Детали:")
        print(f"    - name_similarity: {details['name_similarity']:.1f}%")
        print(f"    - article_similarity: {details['article_similarity']:.1f}%")
        print(f"    - brand_similarity: {details['brand_similarity']:.1f}%")

print("\n" + "=" * 80)
print("ПРОВЕРКА СПЕЦИФИЧНЫХ СЛУЧАЕВ")
print("=" * 80)

# Проверяем светильник из примера пользователя
office_light = None
for item in price_items:
    if "OFFICE LINE" in item.name:
        office_light = item
        break

if office_light:
    print(f"\nПозиция: {office_light.name}")
    print(f"  Бренд: {office_light.brand}")
    print(f"  Артикул: {office_light.article}")
    print(f"  Класс: {office_light.class_code}")

    # Ищем похожий материал
    for material in materials:
        if "светильник" in material.name.lower() or "лампа" in material.name.lower():
            similarity, details = similarity_service.calculate_new_material_similarity(
                material, office_light
            )
            print(f"\n  Сопоставление с '{material.name}':")
            print(f"    Общая похожесть: {similarity:.1f}%")
            print(f"    name: {details['name_similarity']:.1f}%")
            print(f"    article: {details['article_similarity']:.1f}%")
            print(f"    brand: {details['brand_similarity']:.1f}%")
            break