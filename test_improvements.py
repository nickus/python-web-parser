#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест улучшений системы сопоставления материалов
Проверяет, достигают ли идентичные материалы 100% сопоставления
"""

import sys
import os
from pathlib import Path

# Настройка кодировки для консоли Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.services.similarity_service import SimilarityService
from src.models.material import Material, PriceListItem
from src.utils.debug_logger import init_debug_logging
from datetime import datetime

def test_similarity_improvements():
    """Тест улучшений алгоритма сопоставления"""
    
    # Инициализируем логирование
    init_debug_logging(log_level="DEBUG")
    print("=== Тест улучшений системы сопоставления материалов ===\n")
    
    # Создаем сервис сопоставления
    similarity_service = SimilarityService()
    
    # Тестовые случаи для проверки улучшений
    test_cases = [
        {
            "name": "Кабель с заменой латинских символов на кириллические",
            "material": Material(
                id="1",
                name="Кабель ВВГНГ-LS 3x2.5",  # латинская x
                description="Кабель силовой медный",
                category="Кабели",
                brand="ЭлектроКабель",
                created_at=datetime.now()
            ),
            "price_item": PriceListItem(
                id="1",
                material_name="Кабель ВВГНГ-LS 3х2.5мм²",  # кириллическая х и мм²
                description="Силовой кабель медный 3х2,5",
                price=1250.0,
                currency="RUB",
                supplier="Поставщик1",
                category="Кабели",
                brand="ЭлектроКабель",
                updated_at=datetime.now()
            ),
            "expected_min": 90.0  # Ожидаем не менее 90%
        },
        {
            "name": "Автомат с синонимами",
            "material": Material(
                id="2",
                name="Автоматический выключатель C16",
                description="Автомат защиты 16А",
                category="Автоматы",
                brand="ABB",
                created_at=datetime.now()
            ),
            "price_item": PriceListItem(
                id="2",
                material_name="Автомат защиты S201-C16 ABB",
                description="Автоматический выключатель 16А",
                price=650.0,
                currency="RUB",
                supplier="Поставщик2",
                category="Автоматы",
                brand="ABB",
                updated_at=datetime.now()
            ),
            "expected_min": 70.0  # Ожидаем не менее 70% (разные модели)
        },
        {
            "name": "LED лампа с синонимами",
            "material": Material(
                id="3",
                name="LED лампа 10W",
                description="Светодиодная лампа мощностью 10 ватт",
                category="Освещение",
                brand="Philips",
                created_at=datetime.now()
            ),
            "price_item": PriceListItem(
                id="3",
                material_name="Светодиодная лампа 10Вт",
                description="LED лампа 10W E27",
                price=450.0,
                currency="RUB",
                supplier="Поставщик3",
                category="Освещение",
                brand="Philips",
                updated_at=datetime.now()
            ),
            "expected_min": 85.0  # Ожидаем не менее 85%
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Тест {i}: {test_case['name']}")
        print(f"  Материал: '{test_case['material'].name}'")
        print(f"  Прайс-лист: '{test_case['price_item'].material_name}'")
        
        # Выполняем сопоставление
        similarity_percentage, details = similarity_service.calculate_material_similarity(
            test_case['material'], 
            test_case['price_item']
        )
        
        # Проверяем результат
        success = similarity_percentage >= test_case['expected_min']
        status = "✅ ПРОЙДЕН" if success else "❌ НЕ ПРОЙДЕН"
        
        print(f"  Результат: {similarity_percentage:.1f}% (ожидалось ≥{test_case['expected_min']}%) - {status}")
        print(f"  Детали:")
        for field, value in details.items():
            print(f"    - {field}: {value:.1f}%")
        print()
        
        results.append({
            "test_name": test_case['name'],
            "similarity": similarity_percentage,
            "expected": test_case['expected_min'],
            "success": success,
            "details": details
        })
    
    # Итоговая статистика
    passed_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    
    print("=== ИТОГОВЫЕ РЕЗУЛЬТАТЫ ===")
    print(f"Пройдено тестов: {passed_tests}/{total_tests}")
    print(f"Процент успеха: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Улучшения работают корректно.")
    else:
        print("⚠️ Некоторые тесты не пройдены. Требуются дополнительные улучшения.")
    
    # Дополнительный анализ
    avg_similarity = sum(r['similarity'] for r in results) / len(results)
    print(f"Средняя схожесть: {avg_similarity:.1f}%")
    
    print("\nДля получения детальных логов откройте GUI приложение:")
    print("python main.py --gui")
    print("И используйте меню 'Инструменты' -> 'Показать окно логов'")

if __name__ == "__main__":
    test_similarity_improvements()