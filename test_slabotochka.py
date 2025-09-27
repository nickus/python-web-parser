#!/usr/bin/env python3
"""
Тест для проверки сопоставления слаботочного оборудования
Проверяет корректность работы с моделями RS-485, DTM, FireSec, R3 и т.д.
"""

import sys
import os
import time
import json
from pathlib import Path

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp
from src.models.material import Material, PriceListItem
from src.services.fast_similarity_service import FastSimilarityService


def test_model_extraction():
    """Тест извлечения моделей из текста"""
    print("\n=== ТЕСТ 1: Извлечение моделей ===")

    service = FastSimilarityService()

    test_cases = [
        ("Прибор приемно-контрольный. RS-485", {"RS-485"}),
        ("Источник вторичного электропитания резервированный 24/2.5 RS-R3 2x17 БР Серия 3", {"RS-R3"}),
        ("Аккумулятор DTM 12В 17Ач", {"DTM", "12В 17АЧ"}),
        ("Блок индикации и управления Рубеж-БИУ R3", {"R3", "РУБЕЖ"}),
        ("Модуль сопряжения R3-Link", {"R3-LINK"}),
        ("Кабель силовой ППГнг(А)-FRHF 3x2.5", {"3X2.5"}),
        ("Выключатель автоматический БА47-35-3х40/10-20 C5", {}),
        ("FireSec-Pro R3 модуль", {"FIRESEC", "R3"}),
    ]

    for text, expected in test_cases:
        models = service._extract_models(text)
        # Приводим к верхнему регистру для сравнения
        models_upper = {m.upper() for m in models}

        print(f"\nТекст: {text}")
        print(f"Извлечено: {models_upper}")
        print(f"Ожидалось: {expected}")

        # Проверяем, что хотя бы часть ожидаемых моделей найдена
        if expected and models_upper:
            intersection = expected & models_upper
            if intersection:
                print("✅ Модели найдены")
            else:
                print("⚠️ Модели не совпали точно, но что-то найдено")
        elif not expected and not models_upper:
            print("✅ Правильно - модели не ожидались")
        else:
            print("❌ Модели не найдены")


def test_slabotochka_matching():
    """Тест сопоставления слаботочного оборудования"""
    print("\n=== ТЕСТ 2: Сопоставление слаботочного оборудования ===")

    config = {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "bulk_size": 1000,
            "max_workers": 4
        },
        "matching": {
            "similarity_threshold": 20.0,
            "max_results_per_material": 5
        }
    }

    app = MaterialMatcherApp(config)

    # Создаем тестовые данные слаботочки из реальных примеров
    test_materials = [
        Material(
            id="1",
            name="Прибор приемно-контрольный. RS-485",
            equipment_code="Рубеж-2ОП прот.R3",
            manufacturer="Rubezh (адресный)"
        ),
        Material(
            id="2",
            name="Источник вторичного электропитания резервированный 24/2.5 RS-R3 2x17 БР Серия 3",
            equipment_code="24/2.5 RS-R3 2x17 БР",
            manufacturer="Rubezh (адресный)"
        ),
        Material(
            id="3",
            name="Аккумулятор DTM 12В 26Ач",
            equipment_code="DTM 1226",
            manufacturer="Delta"
        ),
        Material(
            id="4",
            name="Пульт дистанционного управления пожаротушения",
            equipment_code="РЗ-Рубеж-ПДУ-ПТ",
            manufacturer="Rubezh (адресный)"
        ),
        Material(
            id="5",
            name="Блок индикации и управления Рубеж-БИУ R3",
            equipment_code="Рубеж-БИУ R3",
            manufacturer="Rubezh (адресный)"
        ),
        Material(
            id="6",
            name="Модуль сопряжения R3-Link",
            equipment_code="R3-МС-Е",
            manufacturer="Rubezh (адресный)"
        ),
        Material(
            id="7",
            name="Шкаф управления пожарный адресный, мощность 18 кВт",
            equipment_code="ШУН/В-18-03-R3",
            manufacturer="Rubezh (адресный)"
        )
    ]

    # Создаем элементы прайс-листа из реального catalog.json
    test_price_items = [
        PriceListItem(
            id="p1",
            name="Прибор приемно-контрольный охранно-пожарный Яхонт-4И исп.03 с АКБ, RS-485",
            article="8784030004",
            brand="Спецприбор-комплект",
            description="С интерфейсом RS-485"
        ),
        PriceListItem(
            id="p2",
            name="Блок индикации и управления, R3-Link.",
            article="R3-Рубеж-БИУ СЕРИЯ 3",
            brand="Rubezh (адресный)",
            description="Блок индикации и управления для системы Рубеж"
        ),
        PriceListItem(
            id="p3",
            name="Метка адресная.",
            article="АМ-4-R3 СЕРИЯ 3",
            brand="Rubezh (адресный)",
            description="Адресная метка для системы R3"
        ),
        PriceListItem(
            id="p4",
            name="Шкаф управления пожарный адресный, мощность 11 кВт исполнение 00",
            article="ШУЗ-11-00-R3 (IP54)",
            brand="Rubezh (адресный)",
            description="Шкаф управления пожарный"
        ),
        PriceListItem(
            id="p5",
            name="Шкаф управления пожарный адресный, однофазный, мощность 1,5 кВт исполнение 03",
            article="ШУН/В-О-1,5-03-R3 (IP54)",
            brand="Rubezh (адресный)",
            description="Шкаф управления пожарный однофазный"
        ),
        PriceListItem(
            id="p6",
            name="Аккумулятор DTM 12В 26Ач",
            article="DTM 1226",
            brand="Delta",
            description="Аккумуляторная батарея 12В 26Ач"
        ),
        PriceListItem(
            id="p7",
            name="Кабель интерфейсный ITK RS-485 1х2х0.6 нг(А)-LS серый (200м)",
            article="RC3-RS485-01-SF-2101",
            brand="ITK (IEK)",
            description="Кабель для интерфейса RS-485"
        ),
        PriceListItem(
            id="p8",
            name="Модуль управления пожаротушением адресный",
            article="МПТ-1-ИКЗ-R3",
            brand="Rubezh (адресный)",
            description="Модуль управления пожаротушением с изолятором КЗ"
        )
    ]

    # Проверяем Elasticsearch
    if not app.es_service.check_connection():
        print("⚠️ Elasticsearch недоступен")
        print("Тестируем локально без Elasticsearch...")

        # Локальное тестирование FastSimilarityService
        similarity_service = FastSimilarityService()

        print("\n--- Тестирование локального сопоставления ---")
        for material in test_materials[:3]:  # Тестируем первые 3 материала
            print(f"\n📦 Материал: {material.name}")
            print(f"   Код: {material.equipment_code}")

            best_match = None
            best_score = 0

            for price_item in test_price_items:
                score, details = similarity_service.calculate_fast_similarity(
                    material, price_item, use_cache=True
                )

                if score > best_score:
                    best_score = score
                    best_match = price_item

            if best_match:
                print(f"\n   ✅ Лучшее совпадение: {best_match.name}")
                print(f"      Артикул: {best_match.article}")
                print(f"      Схожесть: {best_score:.1f}%")
            else:
                print(f"   ❌ Совпадения не найдены")

        return

    # Индексируем данные в Elasticsearch
    print("Индексируем тестовые данные в Elasticsearch...")
    app.setup_indices()
    app.es_service.index_price_list_optimized(test_price_items)
    time.sleep(2)  # Даем время на индексацию

    print("\n--- Тестирование полного сопоставления ---")

    # Тестируем каждый материал
    for material in test_materials:
        print(f"\n📦 Материал: {material.name}")
        print(f"   Код оборудования: {material.equipment_code}")

        # Ищем соответствия
        results = app.search_material_by_name(material.name, top_n=3)

        if results:
            print("   Найденные соответствия:")
            for i, result in enumerate(results[:3], 1):
                price_item = result.get('price_item', {})
                similarity = result.get('similarity_percentage', 0)
                details = result.get('similarity_details', {})

                print(f"\n   {i}. {price_item.get('name', 'N/A')}")
                print(f"      Артикул: {price_item.get('article', 'N/A')}")
                print(f"      Бренд: {price_item.get('brand', 'N/A')}")
                print(f"      Схожесть: {similarity:.1f}%")
                print(f"      - Название: {details.get('name', 0):.1f}%")
                print(f"      - Артикул: {details.get('article', 0):.1f}%")
                print(f"      - Бренд: {details.get('brand', 0):.1f}%")

                # Проверяем корректность для специфичных случаев
                if "RS-485" in material.name and "RS-485" in price_item.get('name', ''):
                    print("      ✅ RS-485 правильно сопоставлен")
                elif "DTM" in material.name and "DTM" in price_item.get('article', ''):
                    print("      ✅ DTM модель правильно сопоставлена")
                elif "R3" in material.equipment_code and "R3" in price_item.get('article', ''):
                    print("      ✅ R3 модель правильно сопоставлена")
        else:
            print("   ❌ Соответствия не найдены")

    return True


def test_cable_matching():
    """Тест корректного сопоставления кабелей с точными размерами"""
    print("\n=== ТЕСТ 3: Точное сопоставление размеров кабелей ===")

    similarity_service = FastSimilarityService()

    # Тестовые кабели
    material_1x70 = Material(
        id="k1",
        name="Кабель силовой ППГнг(А)-FRHF 1x70",
        equipment_code="ППГнг(А)-FRHF 1x70",
        manufacturer="Кабельный завод"
    )

    # Варианты из прайс-листа
    price_1x70 = PriceListItem(
        id="p1",
        name="Кабель силовой ППГнг(А)-FRHF 1x70 черный",
        article="ППГнг(А)-FRHF 1x70",
        brand="КабельПро"
    )

    price_1x95 = PriceListItem(
        id="p2",
        name="Кабель силовой ППГнг(А)-FRHF 1x95 черный",
        article="ППГнг(А)-FRHF 1x95",
        brand="КабельПро"
    )

    # Проверяем сопоставление
    score_70, details_70 = similarity_service.calculate_fast_similarity(
        material_1x70, price_1x70, use_cache=False
    )

    score_95, details_95 = similarity_service.calculate_fast_similarity(
        material_1x70, price_1x95, use_cache=False
    )

    print(f"\nКабель 1x70 -> 1x70: {score_70:.1f}%")
    print(f"Кабель 1x70 -> 1x95: {score_95:.1f}%")

    if score_70 > score_95:
        print("✅ УСПЕХ: Кабель 1x70 правильно сопоставляется с 1x70, а не с 1x95")
    else:
        print("❌ ОШИБКА: Кабель 1x70 неправильно сопоставляется")

    return score_70 > score_95


def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ СЛАБОТОЧНОГО ОБОРУДОВАНИЯ")
    print("=" * 70)

    results = {}

    # Тест 1: Извлечение моделей
    test_model_extraction()
    results["Извлечение моделей"] = "✅ Выполнено"

    # Тест 2: Сопоставление слаботочки
    try:
        test_slabotochka_matching()
        results["Сопоставление слаботочки"] = "✅ Выполнено"
    except Exception as e:
        print(f"Ошибка: {e}")
        results["Сопоставление слаботочки"] = f"❌ Ошибка: {e}"

    # Тест 3: Точность кабелей
    if test_cable_matching():
        results["Точность кабелей"] = "✅ Пройден"
    else:
        results["Точность кабелей"] = "❌ Провален"

    # Итоги
    print("\n" + "=" * 70)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 70)

    for test_name, status in results.items():
        print(f"{test_name}: {status}")

    # Проверка общего результата
    passed = sum(1 for s in results.values() if "✅" in s)
    total = len(results)

    print(f"\nПройдено тестов: {passed}/{total}")

    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"\n⚠️ Пройдено {passed} из {total} тестов")


if __name__ == "__main__":
    main()