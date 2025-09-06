#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности системы поиска материалов
"""

import sys
import os
import json
import time
from pathlib import Path

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp


def test_basic_functionality():
    """Базовый тест функциональности приложения"""
    print("=== Тестирование системы поиска материалов ===\n")
    
    # Инициализация приложения
    print("1. Инициализация приложения...")
    try:
        app = MaterialMatcherApp()
        print("✓ Приложение инициализировано успешно")
    except Exception as e:
        print(f"✗ Ошибка инициализации: {e}")
        return False
    
    # Проверка подключения к Elasticsearch
    print("\n2. Проверка подключения к Elasticsearch...")
    if app.es_service.check_connection():
        print("✓ Подключение к Elasticsearch успешно")
    else:
        print("✗ Не удается подключиться к Elasticsearch")
        print("   Убедитесь, что Elasticsearch запущен на localhost:9200")
        return False
    
    # Создание индексов
    print("\n3. Создание индексов...")
    if app.setup_indices():
        print("✓ Индексы созданы успешно")
    else:
        print("✗ Ошибка создания индексов")
        return False
    
    # Загрузка тестовых данных
    print("\n4. Загрузка тестовых материалов...")
    materials_path = "data/sample/materials.csv"
    price_list_path = "data/sample/price_list.csv"
    
    if not Path(materials_path).exists():
        print(f"✗ Файл {materials_path} не найден")
        return False
    
    if not Path(price_list_path).exists():
        print(f"✗ Файл {price_list_path} не найден")
        return False
    
    materials = app.load_materials(materials_path)
    price_items = app.load_price_list(price_list_path)
    
    if not materials:
        print("✗ Не удалось загрузить материалы")
        return False
    
    if not price_items:
        print("✗ Не удалось загрузить прайс-лист")
        return False
    
    print(f"✓ Загружено {len(materials)} материалов")
    print(f"✓ Загружено {len(price_items)} позиций прайс-листа")
    
    # Индексация данных
    print("\n5. Индексация данных в Elasticsearch...")
    if app.index_data(materials, price_items):
        print("✓ Данные проиндексированы успешно")
    else:
        print("✗ Ошибка индексации данных")
        return False
    
    # Ожидание индексации
    print("   Ожидание завершения индексации...")
    time.sleep(2)
    
    # Запуск сопоставления
    print("\n6. Запуск процесса сопоставления...")
    start_time = time.time()
    
    results = app.run_matching(materials)
    
    end_time = time.time()
    
    if results:
        print(f"✓ Сопоставление завершено за {end_time - start_time:.2f} секунд")
        
        # Статистика
        total_materials = len(results)
        materials_with_matches = sum(1 for matches in results.values() if matches)
        total_matches = sum(len(matches) for matches in results.values())
        
        print(f"   Всего материалов: {total_materials}")
        print(f"   Найдены соответствия: {materials_with_matches}")
        print(f"   Общее количество соответствий: {total_matches}")
        
        # Показать примеры лучших соответствий
        print("\n7. Примеры лучших соответствий:")
        shown = 0
        for material_id, matches in results.items():
            if matches and shown < 3:
                best_match = max(matches, key=lambda x: x.similarity_percentage)
                print(f"\n   Материал: {best_match.material.name}")
                print(f"   Найден: {best_match.price_item.material_name}")
                print(f"   Поставщик: {best_match.price_item.supplier}")
                print(f"   Цена: {best_match.price_item.price} {best_match.price_item.currency}")
                print(f"   Процент похожести: {best_match.similarity_percentage:.1f}%")
                print(f"   Детали похожести:")
                for detail, value in best_match.similarity_details.items():
                    print(f"     - {detail}: {value:.1f}%")
                shown += 1
        
    else:
        print("✗ Сопоставление не дало результатов")
        return False
    
    # Экспорт результатов
    print("\n8. Экспорт результатов...")
    try:
        app.export_results(results, "test_results.json", "json")
        print("✓ Результаты экспортированы в test_results.json")
        
        app.export_results(results, "test_results.csv", "csv")
        print("✓ Результаты экспортированы в test_results.csv")
    except Exception as e:
        print(f"✗ Ошибка экспорта: {e}")
        return False
    
    print("\n=== Тест завершен успешно! ===")
    return True


def test_individual_material():
    """Тест поиска соответствий для отдельного материала"""
    print("\n=== Тест поиска для отдельного материала ===\n")
    
    try:
        app = MaterialMatcherApp()
        
        # Загружаем все материалы из индекса
        es_materials = app.es_service.get_all_materials()
        if not es_materials:
            print("✗ Материалы не найдены в индексе")
            return False
        
        # Берем первый материал для тестирования
        material_id = es_materials[0]['_id']
        print(f"Тестируем материал ID: {material_id}")
        
        # Поиск соответствий
        matches = app.get_material_matches(material_id, top_n=3)
        
        if matches:
            print(f"✓ Найдено {len(matches)} соответствий:")
            for i, match in enumerate(matches, 1):
                print(f"\n   {i}. {match['price_item']['material_name']}")
                print(f"      Поставщик: {match['price_item']['supplier']}")
                print(f"      Цена: {match['price_item']['price']} {match['price_item']['currency']}")
                print(f"      Похожесть: {match['similarity_percentage']:.1f}%")
        else:
            print("✗ Соответствия не найдены")
            return False
        
        print("✓ Тест индивидуального поиска завершен успешно")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка теста: {e}")
        return False


def main():
    """Главная функция тестирования"""
    print("Запуск тестирования системы поиска материалов...\n")
    
    # Базовый тест
    basic_test_success = test_basic_functionality()
    
    if basic_test_success:
        # Тест индивидуального поиска
        individual_test_success = test_individual_material()
        
        if individual_test_success:
            print("\n🎉 Все тесты прошли успешно!")
            print("\nСистема готова к использованию!")
            print("\nДля запуска с вашими данными используйте:")
            print("python main.py --materials <путь_к_материалам> --price-list <путь_к_прайсу> --setup")
        else:
            print("\n⚠️  Базовая функциональность работает, но есть проблемы с индивидуальным поиском")
    else:
        print("\n❌ Базовые тесты не прошли. Проверьте настройки и наличие Elasticsearch")


if __name__ == '__main__':
    main()