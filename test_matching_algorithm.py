#!/usr/bin/env python3
"""
Тестирование алгоритма сопоставления для выявления проблем
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models.material import Material, PriceListItem
from src.services.similarity_service import SimilarityService

# Создаем сервис похожести
similarity_service = SimilarityService()

# Тестовые данные для выявления проблем
test_cases = [
    {
        "description": "Кабель с разными размерами - должны быть разные результаты",
        "materials": [
            Material(
                id="1",
                name="Кабель ВВГнг(A)-LS 3х1,5",
                equipment_code="КАБ-001",
                manufacturer="Камкабель"
            ),
            Material(
                id="2",
                name="Кабель ВВГнг(A)-LS 3х2,5",
                equipment_code="КАБ-002",
                manufacturer="Камкабель"
            ),
        ],
        "price_items": [
            PriceListItem(
                id="p1",
                name="Кабель ВВГнг(A)-LS 3x1,5",
                article="КАБ-001",
                brand="Камкабель"
            ),
            PriceListItem(
                id="p2",
                name="Кабель ВВГнг(A)-LS 3x2,5",
                article="КАБ-002",
                brand="Камкабель"
            ),
            PriceListItem(
                id="p3",
                name="Кабель ВВГнг(A)-LS 3x4",
                article="КАБ-003",
                brand="Камкабель"
            ),
        ]
    },
    {
        "description": "Автоматы с разными токами - должны правильно сопоставляться",
        "materials": [
            Material(
                id="3",
                name="Автоматический выключатель С16",
                equipment_code="АВТ-С16",
                manufacturer="Schneider"
            ),
            Material(
                id="4",
                name="Автоматический выключатель С25",
                equipment_code="АВТ-С25",
                manufacturer="Schneider"
            ),
        ],
        "price_items": [
            PriceListItem(
                id="p4",
                name="Выключатель автомат. 1п С16",
                article="АВТ-С16",
                brand="Schneider Electric"
            ),
            PriceListItem(
                id="p5",
                name="Выключатель автомат. 1п С25",
                article="АВТ-С25",
                brand="Schneider Electric"
            ),
            PriceListItem(
                id="p6",
                name="Выключатель автомат. 1п С32",
                article="АВТ-С32",
                brand="Schneider Electric"
            ),
        ]
    },
    {
        "description": "Лампы с разной мощностью",
        "materials": [
            Material(
                id="5",
                name="Лампа светодиодная 10Вт E27",
                equipment_code="ЛМП-10",
                manufacturer="Osram"
            ),
            Material(
                id="6",
                name="Лампа светодиодная 15Вт E27",
                equipment_code="ЛМП-15",
                manufacturer="Osram"
            ),
        ],
        "price_items": [
            PriceListItem(
                id="p7",
                name="LED лампа 10W E27",
                article="LED-10",
                brand="Osram"
            ),
            PriceListItem(
                id="p8",
                name="LED лампа 15W E27",
                article="LED-15",
                brand="Osram"
            ),
            PriceListItem(
                id="p9",
                name="LED лампа 20W E27",
                article="LED-20",
                brand="Osram"
            ),
        ]
    }
]

print("=" * 80)
print("ТЕСТИРОВАНИЕ АЛГОРИТМА СОПОСТАВЛЕНИЯ")
print("=" * 80)

# Анализ каждого тестового случая
for test_case in test_cases:
    print(f"\n{'='*80}")
    print(f"ТЕСТ: {test_case['description']}")
    print('='*80)

    for material in test_case['materials']:
        print(f"\nМатериал: '{material.name}'")
        print(f"  Код оборудования: {material.equipment_code}")
        print(f"  Производитель: {material.manufacturer}")
        print("-" * 50)

        results = []
        for price_item in test_case['price_items']:
            # Тестируем новый алгоритм
            similarity, details = similarity_service.calculate_new_material_similarity(material, price_item)
            results.append((price_item, similarity, details))

        # Сортируем по похожести
        results.sort(key=lambda x: x[1], reverse=True)

        # Выводим результаты
        print("  Результаты сопоставления:")
        for price_item, similarity, details in results:
            print(f"    [{similarity:6.2f}%] '{price_item.name}'")
            print(f"             Артикул: {price_item.article}, Бренд: {price_item.brand}")
            print(f"             Детали: имя={details['name_similarity']:.1f}%, "
                  f"артикул={details['article_similarity']:.1f}%, "
                  f"бренд={details['brand_similarity']:.1f}%")

            # Проверка на проблемы
            if similarity > 90:
                # Извлекаем числовые значения для проверки
                mat_nums = similarity_service._extract_numeric_values(material.name)
                price_nums = similarity_service._extract_numeric_values(price_item.name)

                if mat_nums != price_nums:
                    print(f"    ⚠️  ПРОБЛЕМА: Высокая похожесть при разных числовых значениях!")
                    print(f"        Числа материала: {mat_nums}")
                    print(f"        Числа прайса: {price_nums}")

print("\n" + "=" * 80)
print("АНАЛИЗ НОРМАЛИЗАЦИИ ТЕКСТА")
print("=" * 80)

# Тестируем нормализацию
test_texts = [
    "Кабель ВВГнг(A)-LS 3х1,5",
    "Кабель ВВГнг(A)-LS 3x1.5",
    "Кабель ВВГнг(A)-LS 3х2,5",
    "Автоматический выключатель С16",
    "Выключатель автомат. 1п С16",
    "Лампа светодиодная 10Вт",
    "LED лампа 10W",
]

print("\nТестирование нормализации:")
for text in test_texts:
    normalized = similarity_service._normalize_text(text)
    print(f"  '{text}' -> '{normalized}'")

print("\n" + "=" * 80)
print("ТЕСТИРОВАНИЕ ИЗВЛЕЧЕНИЯ ЧИСЛОВЫХ ЗНАЧЕНИЙ")
print("=" * 80)

for text in test_texts:
    values = similarity_service._extract_numeric_values(text)
    print(f"  '{text}' -> {values}")

print("\n" + "=" * 80)
print("ПРОВЕРКА СОВМЕСТИМОСТИ ЧИСЛОВЫХ ЗНАЧЕНИЙ")
print("=" * 80)

compatibility_tests = [
    ("Кабель ВВГнг 3х1,5", "Кабель ВВГнг 3x1.5"),
    ("Кабель ВВГнг 3х1,5", "Кабель ВВГнг 3x2.5"),
    ("Автомат С16", "Автомат C16"),
    ("Автомат С16", "Автомат C25"),
    ("Лампа 10Вт", "Лампа 10W"),
    ("Лампа 10Вт", "Лампа 15W"),
]

for text1, text2 in compatibility_tests:
    compatible = similarity_service._check_numeric_compatibility(text1, text2)
    print(f"  '{text1}' vs '{text2}' -> {'✓ Совместимы' if compatible else '✗ Несовместимы'}")

print("\n" + "=" * 80)
print("КОНЕЦ ТЕСТИРОВАНИЯ")
print("=" * 80)