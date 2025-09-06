#!/usr/bin/env python3
"""
Конвертер Excel файлов в формат совместимый с системой сопоставления материалов
Преобразует ваши файлы material.xlsx и pricelist.xlsx в нужный формат
"""

import pandas as pd
import json
from pathlib import Path
import sys

def convert_materials_file():
    """Конвертация файла material.xlsx в формат системы"""
    try:
        print("Конвертирую material.xlsx...")
        df = pd.read_excel('material.xlsx')
        
        # Используем первую колонку (по индексу 0)
        name_column = df.columns[0]
        
        # Создаем данные в формате системы
        materials = []
        for index, row in df.iterrows():
            material_name = str(row[name_column]).strip()
            if material_name and material_name != 'nan':
                material = {
                    'id': str(index + 1),
                    'name': material_name,
                    'description': material_name,
                    'category': 'Электротехника',
                    'brand': '',
                    'model': '',
                    'unit': 'шт',
                    'specifications': '{}'
                }
                materials.append(material)
        
        # Сохраняем в CSV
        materials_df = pd.DataFrame(materials)
        materials_df.to_csv('materials_converted.csv', index=False, encoding='utf-8')
        
        print(f"[OK] Создан файл materials_converted.csv с {len(materials)} материалами")
        return materials
        
    except Exception as e:
        print(f"[ERROR] Ошибка конвертации material.xlsx: {e}")
        return []

def convert_pricelist_file():
    """Конвертация файла pricelist.xlsx в формат системы"""
    try:
        print("Конвертирую pricelist.xlsx...")
        df = pd.read_excel('pricelist.xlsx')
        
        # Используем колонки по индексу для избежания проблем с кодировкой
        columns = df.columns.tolist()
        print(f"Найденные колонки: {columns}")
        
        # ID - колонка 0, Наименование - колонка 1, Изготовитель - колонка 2, и т.д.
        id_col = columns[0]
        name_col = columns[1] 
        manufacturer_col = columns[2] if len(columns) > 2 else None
        manufacturer_code_col = columns[3] if len(columns) > 3 else None
        article_col = columns[4] if len(columns) > 4 else None
        tru_code_col = columns[5] if len(columns) > 5 else None
        
        # Создаем данные в формате системы
        price_items = []
        for index, row in df.iterrows():
            # Очищаем и проверяем данные
            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ''
            manufacturer = str(row[manufacturer_col]).strip() if manufacturer_col and pd.notna(row[manufacturer_col]) else ''
            manufacturer_code = str(row[manufacturer_code_col]).strip() if manufacturer_code_col and pd.notna(row[manufacturer_code_col]) else ''
            article = str(row[article_col]).strip() if article_col and pd.notna(row[article_col]) else ''
            tru_code = str(row[tru_code_col]).strip() if tru_code_col and pd.notna(row[tru_code_col]) else ''
            
            if not name or name == 'nan':
                continue  # Пропускаем строки без названия
            
            price_item = {
                'id': str(row[id_col]),
                'material_name': name,
                'description': name,  # Используем название как описание
                'price': 0.0,  # Цена не указана в файле
                'currency': 'RUB',
                'supplier': manufacturer if manufacturer and manufacturer != 'nan' else 'Не указан',
                'category': 'Электротехника',
                'brand': manufacturer if manufacturer and manufacturer != 'nan' else '',
                'unit': 'шт',
                'specifications': json.dumps({
                    'manufacturer_code': manufacturer_code if manufacturer_code != 'nan' else '',
                    'article': article if article != 'nan' else '',
                    'tru_code': tru_code if tru_code != 'nan' else ''
                }, ensure_ascii=False)
            }
            price_items.append(price_item)
        
        # Сохраняем в CSV
        pricelist_df = pd.DataFrame(price_items)
        pricelist_df.to_csv('pricelist_converted.csv', index=False, encoding='utf-8')
        
        print(f"[OK] Создан файл pricelist_converted.csv с {len(price_items)} позициями")
        return price_items
        
    except Exception as e:
        print(f"[ERROR] Ошибка конвертации pricelist.xlsx: {e}")
        return []

def show_preview(materials, price_items):
    """Показать предварительный просмотр данных"""
    print("\n" + "="*60)
    print("ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР КОНВЕРТИРОВАННЫХ ДАННЫХ")
    print("="*60)
    
    if materials:
        print(f"\n[MATERIALS] МАТЕРИАЛЫ (всего {len(materials)}):")
        print("-" * 40)
        for i, material in enumerate(materials[:5], 1):
            print(f"{i}. {material['name']}")
        if len(materials) > 5:
            print(f"... и еще {len(materials) - 5} материалов")
    
    if price_items:
        print(f"\n[PRICELIST] ПРАЙС-ЛИСТ (всего {len(price_items)}):")
        print("-" * 40)
        for i, item in enumerate(price_items[:5], 1):
            supplier_info = f" ({item['supplier']})" if item['supplier'] != 'Не указан' else ""
            print(f"{i}. {item['material_name']}{supplier_info}")
        if len(price_items) > 5:
            print(f"... и еще {len(price_items) - 5} позиций")

def create_test_script():
    """Создание скрипта для тестирования"""
    script_content = '''#!/usr/bin/env python3
"""
Скрипт для тестирования сопоставления ваших файлов
"""

import sys
import os

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp

def main():
    print("🚀 ТЕСТИРОВАНИЕ СОПОСТАВЛЕНИЯ ВАШИХ ФАЙЛОВ")
    print("="*50)
    
    # Инициализация приложения
    app = MaterialMatcherApp()
    
    # Проверка подключения к Elasticsearch
    if not app.es_service.check_connection():
        print("❌ Elasticsearch не доступен!")
        print("Запустите: docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e 'discovery.type=single-node' -e 'xpack.security.enabled=false' elasticsearch:8.15.1")
        return False
    
    print("✅ Elasticsearch подключен")
    
    # Создание индексов
    print("🔧 Создание индексов...")
    if not app.setup_indices():
        print("❌ Ошибка создания индексов")
        return False
    
    # Загрузка ваших данных
    print("📁 Загрузка материалов...")
    materials = app.load_materials('materials_converted.csv')
    if not materials:
        print("❌ Ошибка загрузки материалов")
        return False
    print(f"✅ Загружено {len(materials)} материалов")
    
    print("💰 Загрузка прайс-листа...")
    price_items = app.load_price_list('pricelist_converted.csv')
    if not price_items:
        print("❌ Ошибка загрузки прайс-листа")
        return False
    print(f"✅ Загружено {len(price_items)} позиций прайс-листа")
    
    # Индексация
    print("🔄 Индексация данных...")
    if not app.index_data(materials, price_items):
        print("❌ Ошибка индексации")
        return False
    print("✅ Данные проиндексированы")
    
    # Запуск сопоставления
    print("⚙️ Запуск сопоставления...")
    results = app.run_matching(materials)
    
    if not results:
        print("❌ Сопоставление не дало результатов")
        return False
    
    # Анализ результатов
    total_materials = len(results)
    materials_with_matches = sum(1 for matches in results.values() if matches)
    total_matches = sum(len(matches) for matches in results.values())
    
    print(f"\\n📊 РЕЗУЛЬТАТЫ:")
    print(f"   Всего материалов: {total_materials}")
    print(f"   Найдены соответствия: {materials_with_matches}")
    print(f"   Общее количество соответствий: {total_matches}")
    print(f"   Процент успеха: {materials_with_matches/total_materials*100:.1f}%")
    
    # Показать лучшие результаты
    print("\\n🏆 ЛУЧШИЕ СООТВЕТСТВИЯ:")
    print("-" * 50)
    
    best_results = []
    for material_id, matches in results.items():
        if matches:
            best_match = max(matches, key=lambda x: x.similarity_percentage)
            material = next(m for m in materials if m.id == material_id)
            best_results.append((material, best_match))
    
    # Сортируем по проценту похожести
    best_results.sort(key=lambda x: x[1].similarity_percentage, reverse=True)
    
    for i, (material, best_match) in enumerate(best_results[:10], 1):
        print(f"\\n{i}. ИСКАЛИ: {material.name}")
        print(f"   НАЙДЕНО: {best_match.price_item.material_name}")
        print(f"   ПОСТАВЩИК: {best_match.price_item.supplier}")
        print(f"   ПОХОЖЕСТЬ: {best_match.similarity_percentage:.1f}%")
    
    # Экспорт результатов
    output_file = "your_matching_results.json"
    app.export_results(results, output_file)
    print(f"\\n💾 Результаты сохранены в {output_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\\n🎉 Тестирование завершено успешно!")
    else:
        print("\\n❌ Тестирование завершилось с ошибками")
'''
    
    with open('test_your_files.py', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("✅ Создан скрипт test_your_files.py для тестирования")

def main():
    """Главная функция"""
    print("[INFO] КОНВЕРТАЦИЯ EXCEL ФАЙЛОВ")
    print("="*40)
    
    # Проверка наличия файлов
    if not Path('material.xlsx').exists():
        print("❌ Файл material.xlsx не найден!")
        return False
    
    if not Path('pricelist.xlsx').exists():
        print("❌ Файл pricelist.xlsx не найден!")
        return False
    
    # Конвертация
    materials = convert_materials_file()
    price_items = convert_pricelist_file()
    
    if not materials or not price_items:
        print("❌ Ошибка конвертации файлов")
        return False
    
    # Предварительный просмотр
    show_preview(materials, price_items)
    
    # Создание тестового скрипта
    create_test_script()
    
    print("\n" + "="*60)
    print("✅ КОНВЕРТАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    print("="*60)
    print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Убедитесь что Elasticsearch запущен:")
    print("   docker ps | grep elasticsearch")
    print("\n2. Запустите тестирование:")
    print("   python test_your_files.py")
    print("\n3. Или используйте GUI:")
    print("   python main.py --gui")
    print("   - Загрузите materials_converted.csv как файл материалов")
    print("   - Загрузите pricelist_converted.csv как прайс-лист")
    
    return True

if __name__ == "__main__":
    main()