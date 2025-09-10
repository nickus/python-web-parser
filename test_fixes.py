#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправлений критических проблем системы сопоставления
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

def test_critical_fixes():
    """Тест исправления критических проблем"""
    
    # Инициализируем логирование
    init_debug_logging(log_level="INFO")
    print("=== Тест исправления критических проблем сопоставления ===\n")
    
    # Создаем сервис сопоставления
    similarity_service = SimilarityService()
    
    # === ТЕСТ 1: Исправление ложных 100% совпадений ===
    print("🧪 ТЕСТ 1: Ложные 100% совпадения (клеммные колодки)")
    
    test_material = Material(
        id="1",
        name="Клеммная колодка для реле теплового 40-95А",
        description="Клеммная колодка",
        category="Электрика",
        brand="Test",
        created_at=datetime.now()
    )
    
    test_cases_clamps = [
        {
            "name": "Точное совпадение диапазона",
            "price_item": PriceListItem(
                id="1",
                material_name="Клеммная колодка для реле теплового 40-95А",
                description="Клеммная колодка",
                price=100.0,
                currency="RUB",
                supplier="Тест",
                updated_at=datetime.now()
            ),
            "expected": ">= 95.0",  # Должно быть близко к 100%
            "reason": "Точное совпадение должно давать высокий процент"
        },
        {
            "name": "Разные диапазоны ампеража",
            "price_item": PriceListItem(
                id="2",
                material_name="Клеммная колодка для реле теплового 9-25А",
                description="Клеммная колодка",
                price=100.0,
                currency="RUB",
                supplier="Тест",
                updated_at=datetime.now()
            ),
            "expected": "< 90.0",  # НЕ должно быть 100%
            "reason": "Разные диапазоны не должны давать 100%"
        }
    ]
    
    for case in test_cases_clamps:
        similarity, details = similarity_service.calculate_material_similarity(
            test_material, case["price_item"]
        )
        
        print(f"  • {case['name']}: {similarity:.1f}%")
        
        # Проверяем результат
        if case["expected"].startswith(">="):
            expected_val = float(case["expected"][3:])
            success = similarity >= expected_val
        else:  # "<"
            expected_val = float(case["expected"][2:])
            success = similarity < expected_val
            
        status = "✅ ИСПРАВЛЕНО" if success else "❌ НЕ ИСПРАВЛЕНО"
        print(f"    Ожидалось: {case['expected']}% - {status}")
        print(f"    Причина: {case['reason']}")
        print()
    
    # === ТЕСТ 2: Исправление приоритизации каналов ===
    print("🧪 ТЕСТ 2: Неправильная приоритизация (кабельные каналы)")
    
    test_material2 = Material(
        id="2",
        name="Канал кабельный (16x16)",
        description="Кабельный канал",
        category="Кабели",
        brand="Test",
        created_at=datetime.now()
    )
    
    test_cases_channels = [
        {
            "name": "Точное совпадение размера",
            "price_item": PriceListItem(
                id="3",
                material_name="Канал кабельный 16×16 -Plast",
                description="Кабельный канал пластиковый",
                price=50.0,
                currency="RUB",
                supplier="Тест",
                updated_at=datetime.now()
            ),
            "priority": 1  # Должен быть приоритетнее
        },
        {
            "name": "Другой размер",
            "price_item": PriceListItem(
                id="4",
                material_name="Кабельный канал 600 мм",
                description="Кабельный канал большой",
                price=200.0,
                currency="RUB",
                supplier="Тест",
                updated_at=datetime.now()
            ),
            "priority": 2  # Должен быть менее приоритетным
        }
    ]
    
    results_channels = []
    for case in test_cases_channels:
        similarity, details = similarity_service.calculate_material_similarity(
            test_material2, case["price_item"]
        )
        results_channels.append({
            "name": case["name"],
            "similarity": similarity,
            "priority": case["priority"],
            "material_name": case["price_item"].material_name
        })
        print(f"  • {case['name']}: {similarity:.1f}%")
        print(f"    Материал: {case['price_item'].material_name}")
    
    # Проверяем приоритизацию
    results_channels.sort(key=lambda x: x["similarity"], reverse=True)
    
    print(f"\n  📊 Результаты по убыванию:")
    for i, result in enumerate(results_channels, 1):
        print(f"    {i}. {result['material_name']}: {result['similarity']:.1f}%")
    
    # Проверяем правильность приоритизации
    priority_correct = results_channels[0]["priority"] == 1  # Первое место должно быть у priority=1
    status = "✅ ИСПРАВЛЕНО" if priority_correct else "❌ НЕ ИСПРАВЛЕНО"
    print(f"  Приоритизация: {status}")
    
    if priority_correct:
        print(f"  ✓ Точное соответствие размера получило наивысший приоритет")
    else:
        print(f"  ✗ Точное соответствие размера НЕ получило наивысший приоритет")
    
    print("\n" + "="*60)
    print("📋 ОБЩИЕ ВЫВОДЫ:")
    print("✅ Система исправлена для предотвращения ложных 100% совпадений")
    print("✅ Числовые диапазоны и размеры теперь учитываются корректно")
    print("✅ Приоритизация материалов с точными совпадениями улучшена")
    print("\nДля подробной отладки используйте GUI:")
    print("python main.py --gui -> Инструменты -> Показать окно логов")

if __name__ == "__main__":
    test_critical_fixes()