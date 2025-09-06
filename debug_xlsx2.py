#!/usr/bin/env python3
"""
Детальная отладка загрузки XLSX
"""

import pandas as pd

def debug_read_excel():
    print("=== Отладка pd.read_excel ===")
    
    print("1. Проверяем что возвращает pd.read_excel:")
    result = pd.read_excel('material.xlsx')
    print(f"   Тип результата: {type(result)}")
    print(f"   Результат: {result}")
    print(f"   Есть атрибут columns? {hasattr(result, 'columns')}")
    if hasattr(result, 'columns'):
        print(f"   Колонки: {list(result.columns)}")
    
    print("\n2. Проверяем с sheet_name=None:")
    result2 = pd.read_excel('material.xlsx', sheet_name=None)
    print(f"   Тип результата: {type(result2)}")
    print(f"   Результат: {result2}")
    
    print("\n3. Проверяем с sheet_name=0:")
    result3 = pd.read_excel('material.xlsx', sheet_name=0)
    print(f"   Тип результата: {type(result3)}")
    print(f"   Есть атрибут columns? {hasattr(result3, 'columns')}")
    
if __name__ == "__main__":
    debug_read_excel()