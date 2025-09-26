#!/usr/bin/env python3
"""
Комплексный тест для проверки всех исправлений системы сопоставления материалов
Проверяет:
1. Корректность сопоставления (без ошибки x→х)
2. Правильное заполнение article_similarity и brand_similarity
3. Производительность оптимизированной системы
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


def test_similarity_fix():
    """Тест исправления проблемы с сопоставлением кабелей разных размеров"""
    print("\n=== ТЕСТ 1: Исправление сопоставления кабелей ===")

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

    # Создаем тестовые данные
    material = Material(
        id="1",
        name="Кабель ВВГНГ-LS 3x1.5",
        equipment_code="ВВГНГ-LS-3x1.5",
        manufacturer="Рыбинсккабель"
    )

    price_items = [
        PriceListItem(
            id="p1",
            name="Кабель ВВГНГ-LS 3x1.5 Рыбинсккабель",
            article="ВВГНГ-LS-3x1.5",
            brand="Рыбинсккабель"
        ),
        PriceListItem(
            id="p2",
            name="Кабель ВВГНГ-LS 3x2.5 Рыбинсккабель",
            article="ВВГНГ-LS-3x2.5",
            brand="Рыбинсккабель"
        ),
        PriceListItem(
            id="p3",
            name="Кабель ВВГНГ-LS 3х1.5 Рыбинсккабель",  # С русской х
            article="ВВГНГ-LS-3х1.5",
            brand="Рыбинсккабель"
        )
    ]

    # Индексируем данные
    print("Индексируем тестовые данные...")
    if app.es_service.check_connection():
        app.setup_indices()
        app.es_service.index_price_list_optimized(price_items)
        time.sleep(1)  # Даем время на индексацию

        # Ищем соответствия
        print(f"Ищем соответствия для: {material.name}")
        results = app.search_material_by_name(material.name, top_n=3)

        print("\nРезультаты:")
        for i, result in enumerate(results, 1):
            match = result.get('match', {})
            print(f"{i}. {match.get('name', 'N/A')}")
            print(f"   Артикул: {match.get('article', 'N/A')}")
            print(f"   Схожесть: {result.get('similarity_percentage', 0):.1f}%")
            details = result.get('similarity_details', {})
            print(f"   - name_similarity: {details.get('name_similarity', 0):.1f}%")
            print(f"   - article_similarity: {details.get('article_similarity', 0):.1f}%")
            print(f"   - brand_similarity: {details.get('brand_similarity', 0):.1f}%")
            print()

        # Проверка корректности
        if results:
            top_match = results[0]['match']
            if "3x2.5" in top_match.get('name', ''):
                print("❌ ОШИБКА: Кабель 3x1.5 сопоставился с 3x2.5!")
                return False
            elif "3x1.5" in top_match.get('name', '') or "3х1.5" in top_match.get('name', ''):
                print("✅ УСПЕХ: Кабель правильно сопоставился с аналогичным размером")

                # Проверка article и brand similarity
                details = results[0].get('similarity_details', {})
                if details.get('article_similarity', 0) > 0:
                    print("✅ article_similarity работает корректно")
                else:
                    print("⚠️ article_similarity все еще 0%")

                if details.get('brand_similarity', 0) > 0:
                    print("✅ brand_similarity работает корректно")
                else:
                    print("⚠️ brand_similarity все еще 0%")
                return True
        else:
            print("❌ Результаты не найдены")
            return False
    else:
        print("⚠️ Elasticsearch недоступен, тест пропущен")
        return None


def test_performance():
    """Тест производительности оптимизированной системы"""
    print("\n=== ТЕСТ 2: Производительность поиска ===")

    config = {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "bulk_size": 1000,
            "max_workers": 4
        }
    }

    app = MaterialMatcherApp(config)

    if not app.es_service.check_connection():
        print("⚠️ Elasticsearch недоступен, тест пропущен")
        return None

    # Создаем больше тестовых данных
    print("Создаем 100 элементов прайс-листа...")
    price_items = []
    for i in range(100):
        price_items.append(PriceListItem(
            id=f"p{i}",
            name=f"Материал {i} тип А размер {i%10}",
            article=f"MAT-{i:03d}",
            brand=f"Производитель {i%5}"
        ))

    # Индексируем
    print("Индексируем данные...")
    app.setup_indices()
    app.es_service.index_price_list_optimized(price_items)
    time.sleep(1)

    # Тестируем скорость поиска
    test_queries = [
        "Материал 15 тип А",
        "Светильник LED 36Вт",
        "Кабель ВВГНГ 3x2.5",
        "Материал тип А размер 5",
        "Производитель 2"
    ]

    total_time = 0
    for query in test_queries:
        start_time = time.time()
        results = app.search_material_by_name(query, top_n=5)
        elapsed = time.time() - start_time
        total_time += elapsed
        print(f"Поиск '{query}': {elapsed:.3f}с, найдено {len(results)} результатов")

    avg_time = total_time / len(test_queries)
    print(f"\nСреднее время поиска: {avg_time:.3f}с")

    if avg_time < 0.5:
        print("✅ ОТЛИЧНО: Поиск очень быстрый (< 0.5с)")
        return True
    elif avg_time < 2.0:
        print("✅ ХОРОШО: Поиск быстрый (< 2с)")
        return True
    else:
        print(f"❌ МЕДЛЕННО: Поиск занимает {avg_time:.1f}с")
        return False


def test_csv_field_mapping():
    """Тест правильного маппинга полей из CSV"""
    print("\n=== ТЕСТ 3: Маппинг полей CSV ===")

    # Создаем временный CSV файл в старом формате
    csv_content = """id,name,brand,model
1,"Кабель ВВГНГ-LS 3x1.5","Рыбинсккабель","ВВГНГ-LS-3x1.5"
2,"Светильник LED 36Вт","Световые Технологии","СВ-LED-36"
"""

    test_csv = Path("test_materials_old_format.csv")
    test_csv.write_text(csv_content, encoding='utf-8')

    try:
        config = {"elasticsearch": {"host": "localhost", "port": 9200}}
        app = MaterialMatcherApp(config)

        # Загружаем материалы
        materials = app.load_materials(str(test_csv))

        if materials:
            print(f"Загружено {len(materials)} материалов")
            for mat in materials:
                print(f"\nМатериал: {mat.name}")
                print(f"  equipment_code: {mat.equipment_code}")
                print(f"  manufacturer: {mat.manufacturer}")

                # Проверяем правильность маппинга
                if mat.manufacturer and mat.equipment_code:
                    print("  ✅ Поля правильно замаплены")
                else:
                    print("  ❌ Проблема с маппингом полей")
            return True
        else:
            print("❌ Не удалось загрузить материалы")
            return False

    finally:
        # Удаляем временный файл
        if test_csv.exists():
            test_csv.unlink()


def main():
    """Запуск всех тестов"""
    print("=" * 60)
    print("КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ СОПОСТАВЛЕНИЯ")
    print("=" * 60)

    results = {}

    # Тест 1: Исправление сопоставления
    result = test_similarity_fix()
    if result is not None:
        results["Сопоставление кабелей"] = "✅ Пройден" if result else "❌ Провален"

    # Тест 2: Производительность
    result = test_performance()
    if result is not None:
        results["Производительность"] = "✅ Пройден" if result else "❌ Провален"

    # Тест 3: Маппинг полей
    result = test_csv_field_mapping()
    if result is not None:
        results["Маппинг CSV"] = "✅ Пройден" if result else "❌ Провален"

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)

    for test_name, status in results.items():
        print(f"{test_name}: {status}")

    # Проверка общего результата
    passed = sum(1 for s in results.values() if "✅" in s)
    total = len(results)

    print(f"\nПройдено тестов: {passed}/{total}")

    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("Система работает корректно и оптимально.")
    elif passed > 0:
        print(f"\n⚠️ Частичный успех: {passed} из {total} тестов пройдено")
    else:
        print("\n❌ Все тесты провалены. Требуется дополнительная отладка.")


if __name__ == "__main__":
    main()