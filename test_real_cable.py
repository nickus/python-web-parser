#!/usr/bin/env python3
"""
Тест для проверки поиска реального кабеля из каталога
Кабель силовой ППГнг(А)-FRHF 1х70мк(PE)-1 с кодом 9994067
"""

import sys
import os
import json
from pathlib import Path

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp
from src.models.material import Material
from elasticsearch import Elasticsearch


def test_real_cable_from_catalog():
    """Тест поиска реального кабеля из каталога"""
    print("\n=== ТЕСТ: Поиск кабеля ППГнг(А)-FRHF 1х70 в реальном каталоге ===")

    config = {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "bulk_size": 1000,
            "max_workers": 4
        },
        "matching": {
            "similarity_threshold": 20.0,
            "max_results_per_material": 10
        }
    }

    app = MaterialMatcherApp(config)

    if not app.es_service.check_connection():
        print("❌ Elasticsearch недоступен")
        return False

    # Проверяем количество документов в индексе
    es = Elasticsearch(['http://localhost:9200'])
    stats = es.indices.stats(index='price_list')
    doc_count = stats['indices']['price_list']['primaries']['docs']['count']
    print(f"Документов в индексе: {doc_count}")

    if doc_count < 100:
        print("⚠️ Индекс почти пустой. Загрузите catalog.json командой:")
        print("venv/bin/python main.py --setup --price-list catalog.json")
        return False

    # Тестовый материал - кабель 1х70
    material = Material(
        id="test1",
        name="Кабель силовой ППГнг(А)-FRHF 1х70",
        equipment_code="ППГнг(А)-FRHF 1х70",
        manufacturer="Кабельный завод"
    )

    print(f"\n📦 Ищем: {material.name}")
    print(f"   Код оборудования: {material.equipment_code}")

    # Поиск в Elasticsearch
    results = app.search_material_by_name(material.name, top_n=10)

    if results:
        print(f"\n✅ Найдено {len(results)} совпадений:")

        found_correct = False
        for i, result in enumerate(results[:5], 1):
            price_item = result.get('price_item', {})
            similarity = result.get('similarity_percentage', 0)
            article = price_item.get('article', 'N/A')

            print(f"\n   {i}. {price_item.get('name', 'N/A')}")
            print(f"      Артикул: {article}")
            print(f"      Бренд: {price_item.get('brand', 'N/A')}")
            print(f"      Схожесть: {similarity:.1f}%")

            # Проверяем правильность
            if '1х70' in price_item.get('name', '') or '1x70' in price_item.get('name', ''):
                if '1х95' not in price_item.get('name', '') and '1x95' not in price_item.get('name', ''):
                    print("      ✅ Правильный размер кабеля найден!")
                    found_correct = True

                    # Проверяем конкретный артикул
                    if article == '9994067':
                        print("      🎯 ТОЧНОЕ СОВПАДЕНИЕ: Найден кабель с кодом 9994067!")
            elif '1х95' in price_item.get('name', '') or '1x95' in price_item.get('name', ''):
                print("      ⚠️ Неправильный размер (1х95 вместо 1х70)")

        if found_correct:
            print("\n✅ ТЕСТ ПРОЙДЕН: Кабель 1х70 правильно найден")
            return True
        else:
            print("\n❌ ТЕСТ ПРОВАЛЕН: Кабель 1х70 не найден или найден неправильный размер")
            return False
    else:
        print("\n❌ Результаты не найдены")
        return False


def search_specific_cable_by_code():
    """Прямой поиск кабеля по коду 9994067"""
    print("\n=== ПРЯМОЙ ПОИСК: Кабель с кодом 9994067 ===")

    es = Elasticsearch(['http://localhost:9200'])

    # Поиск по артикулу
    query = {
        'query': {
            'match': {
                'article': '9994067'
            }
        },
        'size': 5
    }

    try:
        results = es.search(index='price_list', body=query)
        hits = results.get('hits', {}).get('hits', [])

        if hits:
            print(f"✅ Найдено {len(hits)} документов с артикулом 9994067:")
            for hit in hits:
                item = hit['_source']
                print(f"\n   Название: {item.get('name', 'N/A')}")
                print(f"   Артикул: {item.get('article', 'N/A')}")
                print(f"   Бренд: {item.get('brand', 'N/A')}")
            return True
        else:
            print("❌ Документ с артикулом 9994067 не найден в индексе")

            # Проверяем в catalog.json
            if Path('catalog.json').exists():
                print("\nПроверяем в catalog.json...")
                with open('catalog.json', 'r', encoding='utf-8') as f:
                    catalog = json.load(f)

                found = [item for item in catalog if str(item.get('article', '')) == '9994067']
                if found:
                    print(f"✅ Найдено в catalog.json:")
                    for item in found:
                        print(f"   {item.get('name', 'N/A')}")
                    print("\n⚠️ Документ есть в catalog.json, но не в индексе. Нужна переиндексация.")
                else:
                    print("❌ Документ не найден и в catalog.json")
            return False
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ПОИСКА РЕАЛЬНОГО КАБЕЛЯ")
    print("=" * 70)

    # Тест 1: Прямой поиск по коду
    print("\nШаг 1: Проверяем наличие кабеля в индексе")
    has_cable = search_specific_cable_by_code()

    # Тест 2: Поиск через систему сопоставления
    print("\nШаг 2: Тестируем систему сопоставления")
    test_passed = test_real_cable_from_catalog()

    # Итоги
    print("\n" + "=" * 70)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 70)

    if has_cable and test_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    elif has_cable:
        print("⚠️ Кабель есть в индексе, но система сопоставления работает некорректно")
    elif test_passed:
        print("⚠️ Система сопоставления работает, но конкретный кабель не найден")
    else:
        print("❌ Требуется загрузка данных или отладка системы")


if __name__ == "__main__":
    main()