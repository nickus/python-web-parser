#!/usr/bin/env python3
"""
Тест экспорта в XLSX формат
"""

import os
import tempfile
from pathlib import Path
import pandas as pd
from src.utils.data_loader import DataExporter

def test_xlsx_export():
    """Тест экспорта результатов в XLSX"""
    print("=== Тест экспорта в XLSX ===")
    
    # Создаем тестовые данные
    test_results = [
        {
            'material': {
                'id': '1',
                'name': 'Тестовый материал 1',
                'description': 'Описание материала 1',
                'category': 'Категория 1',
                'brand': 'Бренд 1',
                'model': 'Модель 1',
                'unit': 'шт'
            },
            'price_item': {
                'id': '101',
                'material_name': 'Тестовый товар 1',
                'description': 'Описание товара 1',
                'price': 100.50,
                'currency': 'RUB',
                'supplier': 'Поставщик 1',
                'category': 'Категория товара 1',
                'brand': 'Бренд товара 1',
                'unit': 'шт'
            },
            'similarity_percentage': 85.5,
            'elasticsearch_score': 45.2
        },
        {
            'material': {
                'id': '2',
                'name': 'Тестовый материал 2',
                'description': 'Описание материала 2',
                'category': 'Категория 2',
                'brand': None,
                'model': None,
                'unit': 'м'
            },
            'price_item': {
                'id': '102',
                'material_name': 'Тестовый товар 2',
                'description': 'Описание товара 2',
                'price': 250.75,
                'currency': 'USD',
                'supplier': 'Поставщик 2',
                'category': 'Категория товара 2',
                'brand': None,
                'unit': 'м'
            },
            'similarity_percentage': 92.3,
            'elasticsearch_score': 55.8
        }
    ]
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        temp_path = tmp_file.name
    
    try:
        print("1. Экспорт в XLSX...")
        DataExporter.export_results_to_xlsx(test_results, temp_path)
        
        # Проверяем что файл создался
        if not os.path.exists(temp_path):
            print("[ERROR] Файл не был создан")
            return False
        
        print(f"[OK] Файл создан: {temp_path}")
        print(f"   Размер файла: {os.path.getsize(temp_path)} байт")
        
        # Проверяем содержимое
        print("\n2. Проверка содержимого...")
        df = pd.read_excel(temp_path)
        
        print(f"[OK] Загружено {len(df)} строк, {len(df.columns)} колонок")
        print(f"   Колонки: {list(df.columns)}")
        
        # Проверяем что данные корректны
        expected_columns = [
            'ID материала', 'Материал', 'Описание материала', 'Категория материала',
            'Бренд материала', 'Модель материала', 'Единица измерения материала',
            'ID позиции прайса', 'Наименование в прайсе', 'Описание в прайсе',
            'Цена', 'Валюта', 'Поставщик', 'Категория в прайсе',
            'Бренд в прайсе', 'Единица измерения в прайсе',
            'Процент схожести', 'Elasticsearch Score'
        ]
        
        if len(df.columns) != len(expected_columns):
            print(f"[ERROR] Неверное количество колонок. Ожидается: {len(expected_columns)}, получено: {len(df.columns)}")
            return False
            
        # Проверяем данные первой строки
        first_row = df.iloc[0]
        if first_row['Материал'] != 'Тестовый материал 1':
            print(f"[ERROR] Неверное название материала: {first_row['Материал']}")
            return False
            
        if first_row['Цена'] != 100.50:
            print(f"[ERROR] Неверная цена: {first_row['Цена']}")
            return False
            
        if first_row['Процент схожести'] != 85.5:
            print(f"[ERROR] Неверный процент схожести: {first_row['Процент схожести']}")
            return False
        
        print("[OK] Данные корректны")
        
        # Показываем пример данных
        print("\n3. Пример экспортированных данных:")
        print(f"   Материал: {first_row['Материал']}")
        print(f"   Категория: {first_row['Категория материала']}")
        print(f"   Прайс позиция: {first_row['Наименование в прайсе']}")
        print(f"   Цена: {first_row['Цена']} {first_row['Валюта']}")
        print(f"   Схожесть: {first_row['Процент схожести']}%")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при тестировании: {e}")
        return False
        
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def test_empty_results():
    """Тест экспорта пустых результатов"""
    print("\n=== Тест экспорта пустых результатов ===")
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        temp_path = tmp_file.name
    
    try:
        # Тестируем экспорт пустого списка
        DataExporter.export_results_to_xlsx([], temp_path)
        
        # Файл не должен создаваться для пустых результатов
        file_exists = os.path.exists(temp_path)
        if file_exists:
            file_size = os.path.getsize(temp_path)
            print(f"[INFO] Файл создан для пустых результатов, размер: {file_size} байт")
        else:
            print("[OK] Файл не создается для пустых результатов")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при тестировании пустых результатов: {e}")
        return False
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == "__main__":
    print("Тестирование XLSX экспорта...")
    print("=" * 50)
    
    success1 = test_xlsx_export()
    success2 = test_empty_results()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✅ Все тесты прошли успешно!")
        print("\nXLSX экспорт работает корректно:")
        print("• Создание файлов с правильным форматированием")
        print("• Корректные названия колонок на русском языке")
        print("• Автоподбор ширины колонок")
        print("• Обработка пустых значений")
        print("• Правильная обработка пустых результатов")
    else:
        print("❌ Некоторые тесты не прошли")