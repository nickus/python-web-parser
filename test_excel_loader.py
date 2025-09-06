#!/usr/bin/env python3
"""
Тестирование универсального загрузчика Excel файлов
"""

import sys
import os

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.excel_loader import SmartExcelLoader
from src.material_matcher_app import MaterialMatcherApp

def test_excel_loading():
    """Тестирование загрузки Excel файлов"""
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАГРУЗКИ EXCEL ФАЙЛОВ")
    print("=" * 60)
    
    loader = SmartExcelLoader()
    
    # Тестируем material.xlsx
    print("\n[1] АНАЛИЗ ФАЙЛА material.xlsx")
    print("-" * 40)
    
    try:
        info = loader.get_structure_info('material.xlsx')
        print(f"Тип файла: {info['detected_type']}")
        print(f"Количество строк: {info['total_rows']}")
        print(f"Количество колонок: {info['total_columns']}")
        print(f"Колонки: {', '.join(info['columns'])}")
        print("\nСоответствие колонок:")
        for key, value in info['column_mapping'].items():
            if value:
                print(f"  {key}: {value}")
        
        # Загружаем материалы
        materials = loader.load_materials_from_excel('material.xlsx')
        print(f"\n[OK] Загружено {len(materials)} материалов")
        
        # Показываем первые 3 материала
        print("\nПримеры материалов:")
        for i, material in enumerate(materials[:3], 1):
            print(f"  {i}. {material.name}")
            print(f"     ID: {material.id}")
            print(f"     Категория: {material.category}")
            
    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке material.xlsx: {e}")
    
    # Тестируем pricelist.xlsx
    print("\n[2] АНАЛИЗ ФАЙЛА pricelist.xlsx")
    print("-" * 40)
    
    try:
        info = loader.get_structure_info('pricelist.xlsx')
        print(f"Тип файла: {info['detected_type']}")
        print(f"Количество строк: {info['total_rows']}")
        print(f"Количество колонок: {info['total_columns']}")
        print(f"Колонки: {', '.join(info['columns'])}")
        print("\nСоответствие колонок:")
        for key, value in info['column_mapping'].items():
            if value:
                print(f"  {key}: {value}")
        
        # Загружаем прайс-лист
        price_items = loader.load_pricelist_from_excel('pricelist.xlsx')
        print(f"\n[OK] Загружено {len(price_items)} позиций прайс-листа")
        
        # Показываем первые 3 позиции
        print("\nПримеры позиций:")
        for i, item in enumerate(price_items[:3], 1):
            print(f"  {i}. {item.material_name}")
            print(f"     ID: {item.id}")
            print(f"     Поставщик: {item.supplier}")
            print(f"     Цена: {item.price} {item.currency}")
            
    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке pricelist.xlsx: {e}")
    
    # Тестируем полный цикл с MaterialMatcherApp
    print("\n[3] ТЕСТИРОВАНИЕ ПОЛНОГО ЦИКЛА")
    print("-" * 40)
    
    try:
        app = MaterialMatcherApp()
        
        # Проверяем Elasticsearch
        if not app.es_service.check_connection():
            print("[WARNING] Elasticsearch не доступен, пропускаем полное тестирование")
            return
        
        print("[OK] Elasticsearch подключен")
        
        # Загружаем через приложение
        print("\nЗагрузка материалов через приложение...")
        materials = app.load_materials('material.xlsx', file_format='excel')
        print(f"[OK] Загружено {len(materials)} материалов")
        
        print("\nЗагрузка прайс-листа через приложение...")
        price_items = app.load_price_list('pricelist.xlsx', file_format='excel')
        print(f"[OK] Загружено {len(price_items)} позиций")
        
        # Создаем индексы и индексируем
        print("\nИндексация данных...")
        app.setup_indices()
        app.index_data(materials, price_items)
        print("[OK] Данные проиндексированы")
        
        # Запускаем сопоставление для первых 5 материалов
        print("\nТестовое сопоставление (первые 5 материалов)...")
        test_materials = materials[:5]
        results = app.run_matching(test_materials)
        
        # Показываем результаты
        print("\nРезультаты сопоставления:")
        for material_id, matches in results.items():
            material = next(m for m in test_materials if m.id == material_id)
            print(f"\nМатериал: {material.name}")
            if matches:
                best_match = max(matches, key=lambda x: x.similarity_percentage)
                print(f"  Лучшее совпадение: {best_match.price_item.material_name}")
                print(f"  Похожесть: {best_match.similarity_percentage:.1f}%")
                print(f"  Поставщик: {best_match.price_item.supplier}")
            else:
                print("  Совпадения не найдены")
        
        print("\n[OK] Полный цикл выполнен успешно!")
        
    except Exception as e:
        print(f"[ERROR] Ошибка в полном цикле: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\nТеперь вы можете загружать Excel файлы напрямую через GUI!")
    print("Просто выберите ваши файлы material.xlsx и pricelist.xlsx")

if __name__ == "__main__":
    test_excel_loading()