#!/usr/bin/env python3
"""
Тесты для проверки точного сопоставления конкретных позиций из таблицы
Каждая позиция должна находить правильный товар с правильным ID
"""

import subprocess
import json
import sys
from pathlib import Path


def run_search(query, top_n=5):
    """Выполняет поиск и возвращает результаты"""
    result = subprocess.run(
        ['venv/bin/python', 'main.py', '--search-material', query, '--top-n', str(top_n)],
        capture_output=True, text=True, encoding='utf-8'
    )
    return result.stdout


def check_result(stdout, expected_id, expected_name_part, expected_brand=None):
    """Проверяет результат поиска"""
    found_id = f"ID: {expected_id}" in stdout
    found_name = expected_name_part.upper() in stdout.upper()
    found_brand = True if expected_brand is None else expected_brand.upper() in stdout.upper()

    return found_id and found_name and found_brand


def test_exact_positions():
    """Тестируем конкретные позиции из таблицы"""

    test_cases = [
        {
            "query": "Прибор приемно-контрольный. RS-485 Рубеж-2ОП прот.R3",
            "expected_id": "3109396",
            "expected_name": "Прибор приемно-контрольный. RS-485",
            "expected_brand": "Rubezh",
            "description": "Рубеж-2ОП прот.R3"
        },
        {
            "query": "Источник вторичного электропитания резервированный 24/2.5 RS-R3 2х17 БР",
            "expected_id": "5028231",
            "expected_name": "ИВЭПР 24/2,5 RS-R3",
            "expected_brand": "Rubezh",
            "description": "24/2,5 RS-R3 2х17 БР"
        },
        {
            "query": "Аккумулятор DTM 12В 17Ач",
            "expected_id": "8057037",
            "expected_name": "DTM 1217",
            "expected_brand": "DELTA",
            "description": "DTM 1217"
        },
        {
            "query": "Пульт дистанционного управления пожаротушения R3-Рубеж-ПДУ-ПТ",
            "expected_id": "4620055",
            "expected_name": "Рубеж-ПДУ-ПТ",
            "expected_brand": "Rubezh",
            "description": "R3-Рубеж-ПДУ-ПТ"
        },
        {
            "query": "Блок индикации и управления Рубеж-БИУ R3",
            "expected_id": "4620055",  # Может быть тот же ID что и ПДУ
            "expected_name": "Рубеж-БИУ",
            "expected_brand": "Rubezh",
            "description": "Рубеж-БИУ R3"
        },
        {
            "query": "FireSec-Pro R3",
            "expected_id": "3104572",
            "expected_name": "FireSec-Pro R3",
            "expected_brand": "Rubezh",
            "description": "FireSec-Pro R3"
        },
        {
            "query": "Модуль сопряжения R3-Link R3-МС-Е",
            "expected_id": "6229094",
            "expected_name": "R3-МС-Е",
            "expected_brand": "Rubezh",
            "description": "R3-МС-Е"
        },
        {
            "query": "Шкаф управления пожарный адресный мощность 18 кВт ШУН/В-18-03-R3",
            "expected_id": "3287967",
            "expected_name": "ШУН/В-18-03-R3",
            "expected_brand": "Rubezh",
            "description": "ШУН/В-18-03-R3"
        },
        {
            "query": "Шкаф управления пожарный адресный мощность 11 кВт ШУН/В-11-03-R3",
            "expected_id": "1617295",
            "expected_name": "ШУН/В-11-03-R3",
            "expected_brand": "Rubezh",
            "description": "ШУН/В-11-03-R3"
        },
        {
            "query": "Шкаф управления пожарный адресный мощность 7.5 кВт ШУН/В-7,5-03-R3",
            "expected_id": "253569",
            "expected_name": "ШУН/В-7,5-03-R3",
            "expected_brand": "Rubezh",
            "description": "ШУН/В-7,5-03-R3"
        }
    ]

    print("="*70)
    print("ТЕСТИРОВАНИЕ ТОЧНОГО СОПОСТАВЛЕНИЯ ПОЗИЦИЙ")
    print("="*70)

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. Тест: {test_case['description']}")
        print(f"   Поиск: '{test_case['query'][:60]}...'")
        print(f"   Ожидается ID: {test_case['expected_id']}")

        stdout = run_search(test_case['query'])

        # Проверяем результат
        if check_result(stdout, test_case['expected_id'], test_case['expected_name'], test_case['expected_brand']):
            print(f"   ✅ УСПЕХ: Найдена правильная позиция с ID {test_case['expected_id']}")
            passed += 1
        else:
            # Детальная проверка что нашли/не нашли
            if f"ID: {test_case['expected_id']}" in stdout:
                print(f"   ✅ ID найден правильно")
            else:
                print(f"   ❌ ID {test_case['expected_id']} НЕ найден")
                # Показываем какие ID нашлись
                lines = stdout.split('\n')
                found_ids = [line.strip() for line in lines if line.strip().startswith("ID:")][:3]
                if found_ids:
                    print(f"      Найдены ID: {', '.join(found_ids)}")

            if test_case['expected_name'].upper() in stdout.upper():
                print(f"   ✅ Название содержит '{test_case['expected_name']}'")
            else:
                print(f"   ❌ Название НЕ содержит '{test_case['expected_name']}'")

            if test_case['expected_brand'] and test_case['expected_brand'].upper() in stdout.upper():
                print(f"   ✅ Бренд {test_case['expected_brand']} найден")
            elif test_case['expected_brand']:
                print(f"   ❌ Бренд {test_case['expected_brand']} НЕ найден")

            failed += 1

    # Итоги
    print("\n" + "="*70)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("="*70)
    print(f"✅ Успешно: {passed}/{len(test_cases)}")
    print(f"❌ Провалено: {failed}/{len(test_cases)}")

    if passed == len(test_cases):
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    elif passed > len(test_cases) * 0.7:
        print(f"\n⚠️ Большинство тестов пройдено ({passed}/{len(test_cases)})")
    else:
        print(f"\n❌ Требуется доработка системы ({passed}/{len(test_cases)} пройдено)")


def test_simplified_search():
    """Тестируем упрощенный поиск по артикулам"""
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ПОИСКА ПО АРТИКУЛАМ")
    print("="*70)

    articles = [
        ("Рубеж-2ОП прот.R3", "3109396"),
        ("24/2,5 RS-R3", "5028231"),
        ("DTM 1217", "8057037"),
        ("R3-Рубеж-ПДУ-ПТ", "4620055"),
        ("FireSec-Pro R3", "3104572"),
        ("R3-МС-Е", "6229094"),
        ("ШУН/В-18-03-R3", "3287967"),
        ("ШУН/В-11-03-R3", "1617295"),
        ("ШУН/В-7,5-03-R3", "253569")
    ]

    for article, expected_id in articles:
        print(f"\n🔍 Поиск по артикулу: '{article}'")
        stdout = run_search(article, top_n=3)

        if f"ID: {expected_id}" in stdout:
            print(f"   ✅ Найден правильный ID: {expected_id}")
        else:
            print(f"   ❌ ID {expected_id} не найден")
            # Показываем первый найденный ID
            lines = stdout.split('\n')
            for line in lines:
                if line.strip().startswith("ID:"):
                    print(f"      Найден: {line.strip()}")
                    break


def verify_catalog_presence():
    """Проверяем наличие товаров в catalog.json"""
    print("\n" + "="*70)
    print("ПРОВЕРКА НАЛИЧИЯ В CATALOG.JSON")
    print("="*70)

    if not Path('catalog.json').exists():
        print("❌ Файл catalog.json не найден")
        return

    with open('catalog.json', 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    # Создаем словарь для быстрого поиска
    catalog_dict = {str(item.get('id')): item for item in catalog}

    required_ids = [
        "3109396",  # Рубеж-2ОП прот.R3
        "5028231",  # 24/2,5 RS-R3 2х17 БР
        "8057037",  # DTM 1217
        "4620055",  # R3-Рубеж-ПДУ-ПТ
        "3104572",  # FireSec-Pro R3
        "6229094",  # R3-МС-Е
        "3287967",  # ШУН/В-18-03-R3
        "1617295",  # ШУН/В-11-03-R3
        "253569"    # ШУН/В-7,5-03-R3
    ]

    found = 0
    not_found = []

    for item_id in required_ids:
        if item_id in catalog_dict:
            item = catalog_dict[item_id]
            print(f"✅ ID {item_id}: {item.get('name', 'N/A')[:60]}")
            found += 1
        else:
            print(f"❌ ID {item_id}: НЕ НАЙДЕН в catalog.json")
            not_found.append(item_id)

    print(f"\nНайдено в каталоге: {found}/{len(required_ids)}")

    if not_found:
        print("\n⚠️ Отсутствующие ID нужно добавить в catalog.json или использовать другие ID")
        print(f"Не найдены: {', '.join(not_found)}")


def main():
    """Запуск всех тестов"""

    # Проверка наличия в каталоге
    verify_catalog_presence()

    # Точное сопоставление
    test_exact_positions()

    # Упрощенный поиск
    test_simplified_search()

    print("\n" + "="*70)
    print("📝 Рекомендации:")
    print("1. Убедитесь, что все ID из таблицы есть в catalog.json")
    print("2. Проверьте индексацию: venv/bin/python main.py --setup --price-list catalog.json")
    print("3. При неудачах смотрите первые 3 результата поиска для анализа")


if __name__ == "__main__":
    main()