#!/usr/bin/env python3
"""
Отладка загрузчика XLSX файлов
"""

import pandas as pd
from src.utils.excel_loader import SmartExcelLoader

def test_direct_xlsx():
    print("=== Тестирование прямой загрузки XLSX ===")
    
    # Проверяем pandas
    try:
        print("1. Прямой тест pandas:")
        df = pd.read_excel('material.xlsx')
        print(f"   Колонки: {list(df.columns)}")
        print(f"   Размер: {df.shape}")
        print(f"   Первая строка: {df.iloc[0].tolist()}")
    except Exception as e:
        print(f"   [ERROR] {e}")
    
    # Проверяем SmartExcelLoader
    print("\n2. Тест SmartExcelLoader:")
    try:
        loader = SmartExcelLoader()
        info = loader.get_structure_info('material.xlsx')
        print(f"   Информация получена: {info}")
    except Exception as e:
        import traceback
        print(f"   [ERROR] {e}")
        print(f"   Трассировка: {traceback.format_exc()}")
    
    print("\n3. Тест прямой загрузки материалов:")
    try:
        loader = SmartExcelLoader()
        materials = loader.load_materials_from_excel('material.xlsx')
        print(f"   Загружено материалов: {len(materials)}")
        if materials:
            print(f"   Первый материал: {materials[0].name}")
    except Exception as e:
        import traceback
        print(f"   [ERROR] {e}")
        print(f"   Трассировка: {traceback.format_exc()}")

if __name__ == "__main__":
    test_direct_xlsx()