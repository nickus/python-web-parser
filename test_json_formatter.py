#!/usr/bin/env python3
"""
Тестирование нового форматирования JSON с топ-7 вариантами
"""

import sys
import os
import json

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp
from src.utils.json_formatter import MatchingResultFormatter

def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ НОВОГО JSON ФОРМАТИРОВАНИЯ")
    print("=" * 60)
    
    # Инициализация приложения
    app = MaterialMatcherApp()
    
    # Проверка Elasticsearch
    if not app.es_service.check_connection():
        print("[ERROR] Elasticsearch не доступен!")
        return False
    
    print("[OK] Elasticsearch подключен")
    
    # Создание индексов
    print("[INFO] Создание индексов...")
    app.setup_indices()
    
    # Загрузка данных
    print("[INFO] Загрузка материалов из materials_converted.csv...")
    materials = app.load_materials('materials_converted.csv')
    print(f"[OK] Загружено {len(materials)} материалов")
    
    print("[INFO] Загрузка прайс-листа из pricelist_converted.csv...")
    price_items = app.load_price_list('pricelist_converted.csv')
    print(f"[OK] Загружено {len(price_items)} позиций прайс-листа")
    
    # Индексация
    print("[INFO] Индексация данных...")
    app.index_data(materials, price_items)
    print("[OK] Данные проиндексированы")
    
    # Сопоставление
    print("[INFO] Запуск сопоставления...")
    results = app.run_matching(materials)
    
    # Форматирование результатов
    print("\n" + "=" * 60)
    print("ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 60)
    
    formatter = MatchingResultFormatter(max_matches=7)
    formatted_results = formatter.format_matching_results(results)
    
    # Статистика
    stats = formatter.get_statistics()
    print(f"\n[СТАТИСТИКА]")
    print(f"  Всего материалов: {stats['total_materials']}")
    print(f"  С найденными соответствиями: {stats['materials_with_matches']}")
    print(f"  Всего вариантов: {stats['total_variants_found']}")
    print(f"  Средняя релевантность: {stats['average_relevance']*100:.1f}%")
    
    # Показываем первые 3 материала с топ-7 вариантами
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ РЕЗУЛЬТАТОВ (первые 3 материала)")
    print("=" * 60)
    
    for i, result in enumerate(formatted_results[:3], 1):
        print(f"\n[МАТЕРИАЛ {i}]: {result['material_name']}")
        print(f"  ID: {result['material_id']}")
        
        if result['matches']:
            print(f"  Найдено вариантов: {len(result['matches'])} (топ-7)")
            print("\n  ТОП-7 ВАРИАНТОВ:")
            for j, match in enumerate(result['matches'][:7], 1):
                print(f"\n  {j}. {match['variant_name']}")
                print(f"     Релевантность: {match['relevance']*100:.1f}%")
                print(f"     Цена: {match['price']:.2f} RUB")
                print(f"     Поставщик: {match['supplier']}")
                print(f"     Бренд: {match['brand'] or '-'}")
        else:
            print("  Соответствия не найдены")
    
    # Экспорт в новом формате
    output_file = "test_formatted_results.json"
    print(f"\n[INFO] Экспорт результатов в {output_file}...")
    success = formatter.export_to_json(output_file, include_unselected=True, pretty=True)
    
    if success:
        print(f"[OK] Результаты сохранены в {output_file}")
        
        # Пример выбора варианта
        print("\n" + "=" * 60)
        print("ТЕСТИРОВАНИЕ ВЫБОРА ВАРИАНТА")
        print("=" * 60)
        
        # Выбираем первый вариант для первого материала
        if formatted_results and formatted_results[0]['matches']:
            first_material = formatted_results[0]
            first_variant = first_material['matches'][0]
            
            print(f"\nВыбираем вариант для материала: {first_material['material_name']}")
            print(f"Выбранный вариант: {first_variant['variant_name']}")
            
            selected = formatter.select_variant(
                first_material['material_id'],
                first_variant['variant_id']
            )
            
            if 'error' not in selected:
                print("[OK] Вариант успешно выбран")
                
                # Экспорт с выбранным вариантом
                output_selected = "test_selected_results.json"
                formatter.export_to_json(output_selected, include_unselected=False, pretty=True)
                print(f"[OK] Результаты с выбранными вариантами сохранены в {output_selected}")
            else:
                print(f"[ERROR] {selected['error']}")
    else:
        print("[ERROR] Не удалось сохранить результаты")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    main()