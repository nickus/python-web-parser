#!/usr/bin/env python3
"""
End-to-End тесты для main.py
Проверяем всю функциональность через командную строку
"""

import subprocess
import json
import sys
import time
from pathlib import Path


def run_command(cmd):
    """Выполняет команду и возвращает результат"""
    print(f"\n{'='*70}")
    print(f"Выполняем: {' '.join(cmd)}")
    print('='*70)

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)

    return result.returncode, result.stdout, result.stderr


def test_connection():
    """Тест 1: Проверка подключения к Elasticsearch"""
    print("\n📌 ТЕСТ 1: Проверка подключения к Elasticsearch")

    code, stdout, stderr = run_command(['venv/bin/python', 'main.py', '--check-connection'])

    if code == 0 and "[OK] Подключение к Elasticsearch успешно" in stdout:
        print("✅ Elasticsearch подключен успешно")
        return True
    else:
        print("❌ Проблема с подключением к Elasticsearch")
        return False


def test_search_cable():
    """Тест 2: Поиск конкретного кабеля"""
    print("\n📌 ТЕСТ 2: Поиск кабеля ППГнг(А)-FRHF 1х70")

    test_cases = [
        # Точный поиск
        "Кабель силовой ППГнг(А)-FRHF 1х70мк(PE)-1 ТРТС Кабэкс",
        # Упрощенный поиск
        "ППГнг(А)-FRHF 1х70",
        # Поиск с ошибкой в написании
        "Кабель ППГнг FRHF 1x70"
    ]

    for query in test_cases:
        print(f"\n🔍 Поиск: '{query}'")
        code, stdout, stderr = run_command([
            'venv/bin/python', 'main.py',
            '--search-material', query,
            '--top-n', '3'
        ])

        # Проверяем результаты
        if "Найдено" in stdout and "соответствий" in stdout:
            # Проверяем наличие важных полей
            checks = {
                "ID:": "ID позиции",
                "Бренд/Поставщик:": "Бренд",
                "Похожесть:": "Процент схожести",
                "1х70": "Правильный размер кабеля"
            }

            for check, desc in checks.items():
                if check in stdout:
                    print(f"  ✅ {desc} найден")
                else:
                    print(f"  ⚠️ {desc} не найден")

            # Проверяем, что НЕ нашли неправильный размер
            if "1х95" in stdout or "1x95" in stdout:
                print("  ❌ ОШИБКА: Найден неправильный размер кабеля (1х95)")
        else:
            print("  ❌ Результаты не найдены")


def test_search_slabotochka():
    """Тест 3: Поиск слаботочного оборудования"""
    print("\n📌 ТЕСТ 3: Поиск слаботочного оборудования")

    test_cases = [
        ("RS-485", "RS-485"),
        ("Аккумулятор DTM 12В", "DTM"),
        ("Блок индикации Рубеж-БИУ R3", "R3"),
        ("FireSec", "FIRESEC")
    ]

    for query, expected_model in test_cases:
        print(f"\n🔍 Поиск: '{query}'")
        code, stdout, stderr = run_command([
            'venv/bin/python', 'main.py',
            '--search-material', query,
            '--top-n', '2'
        ])

        if expected_model.upper() in stdout.upper():
            print(f"  ✅ Модель {expected_model} найдена")
        else:
            print(f"  ❌ Модель {expected_model} НЕ найдена")


def test_search_by_id():
    """Тест 4: Поиск по ID из каталога"""
    print("\n📌 ТЕСТ 4: Поиск по конкретным ID из каталога")

    # ID кабеля из catalog.json
    test_ids = [
        ("9994067", "ППГнг(А)-FRHF 1х70мк(PE)-1"),  # Кабель из примера
        ("308804", "ППГнг(А)-FRHF 1х70мк(PE)"),     # Другой кабель 1х70
    ]

    for item_id, expected_name in test_ids:
        # Сначала получаем название из каталога
        if Path('catalog.json').exists():
            with open('catalog.json', 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            item = next((x for x in catalog if str(x.get('id')) == item_id), None)
            if item:
                name = item.get('name', '')
                print(f"\n🔍 Поиск ID {item_id}: '{name}'")

                code, stdout, stderr = run_command([
                    'venv/bin/python', 'main.py',
                    '--search-material', name,
                    '--top-n', '5'
                ])

                # Проверяем, что нашли правильный ID
                if f"ID: {item_id}" in stdout:
                    print(f"  ✅ Точное совпадение по ID {item_id}")
                elif expected_name in stdout:
                    print(f"  ⚠️ Найден похожий товар, но другой ID")
                else:
                    print(f"  ❌ Товар с ID {item_id} не найден")


def test_price_availability():
    """Тест 5: Проверка наличия цен"""
    print("\n📌 ТЕСТ 5: Проверка вывода цен")

    # Ищем популярные товары, у которых должны быть цены
    queries = [
        "Кабель ВВГНГ",
        "Автомат ABB",
        "Розетка Legrand"
    ]

    for query in queries:
        print(f"\n🔍 Поиск: '{query}'")
        code, stdout, stderr = run_command([
            'venv/bin/python', 'main.py',
            '--search-material', query,
            '--top-n', '1'
        ])

        if "Цена:" in stdout:
            if "Цена: не указана" in stdout:
                print("  ⚠️ Цена не указана в каталоге")
            else:
                print("  ✅ Цена отображается корректно")
        else:
            print("  ❌ Поле цены отсутствует в выводе")


def test_performance():
    """Тест 6: Производительность поиска"""
    print("\n📌 ТЕСТ 6: Производительность поиска")

    queries = [
        "Кабель",
        "Светильник LED",
        "Автомат защиты",
        "RS-485",
        "ППГнг(А)-FRHF"
    ]

    times = []
    for query in queries:
        start = time.time()
        code, stdout, stderr = run_command([
            'venv/bin/python', 'main.py',
            '--search-material', query,
            '--top-n', '10'
        ])
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  Поиск '{query[:20]}...': {elapsed:.2f} сек")

    avg_time = sum(times) / len(times)
    print(f"\n  Среднее время поиска: {avg_time:.2f} сек")

    if avg_time < 3:
        print("  ✅ Производительность отличная (< 3 сек)")
    elif avg_time < 5:
        print("  ⚠️ Производительность приемлемая (< 5 сек)")
    else:
        print("  ❌ Производительность низкая (> 5 сек)")


def main():
    """Запуск всех E2E тестов"""
    print("="*70)
    print("END-TO-END ТЕСТИРОВАНИЕ ЧЕРЕЗ main.py")
    print("="*70)

    results = {}

    # Тест 1: Подключение
    if test_connection():
        results["Подключение к Elasticsearch"] = "✅ Работает"
    else:
        results["Подключение к Elasticsearch"] = "❌ Не работает"
        print("\n❌ Elasticsearch недоступен. Остальные тесты невозможны.")
        print("Запустите: docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e \"discovery.type=single-node\" elasticsearch:8.15.1")
        return

    # Тест 2: Поиск кабеля
    test_search_cable()
    results["Поиск кабелей"] = "✅ Протестирован"

    # Тест 3: Слаботочка
    test_search_slabotochka()
    results["Поиск слаботочки"] = "✅ Протестирован"

    # Тест 4: Поиск по ID
    test_search_by_id()
    results["Поиск по ID"] = "✅ Протестирован"

    # Тест 5: Цены
    test_price_availability()
    results["Вывод цен"] = "✅ Протестирован"

    # Тест 6: Производительность
    test_performance()
    results["Производительность"] = "✅ Протестирован"

    # Итоги
    print("\n" + "="*70)
    print("ИТОГОВЫЙ ОТЧЕТ E2E ТЕСТИРОВАНИЯ")
    print("="*70)

    for test_name, status in results.items():
        print(f"{test_name}: {status}")

    print("\n📝 Рекомендации:")
    print("1. Убедитесь, что catalog.json загружен в Elasticsearch")
    print("2. Для перезагрузки данных: venv/bin/python main.py --setup --price-list catalog.json")
    print("3. Проверьте логи в material_matcher.log при проблемах")


if __name__ == "__main__":
    main()