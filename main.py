#!/usr/bin/env python3
"""
Главный файл для запуска приложения поиска материалов с процентом похожести
Обеспечивает полную интеграцию с Elasticsearch для сопоставления материалов
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp


def interactive_setup():
    """Интерактивная настройка системы для первоначальной загрузки"""
    print("=" * 60)
    print("   НАСТРОЙКА СИСТЕМЫ СОПОСТАВЛЕНИЯ МАТЕРИАЛОВ")
    print("=" * 60)
    print()
    
    # Шаг 1: Проверка Elasticsearch
    print("ШАГ 1: Проверка подключения к Elasticsearch")
    print("-" * 50)
    
    config = load_config()
    app = MaterialMatcherApp(config)
    
    print("Проверяем подключение к Elasticsearch...")
    if not app.es_service.check_connection():
        print("[ERROR] Не удается подключиться к Elasticsearch!")
        print("\nДля работы системы необходим Elasticsearch.")
        print("Запустите Elasticsearch командой:")
        print("docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e \"discovery.type=single-node\" elasticsearch:8.15.1")
        print("\nИли установите Elasticsearch локально и убедитесь что он запущен на localhost:9200")
        
        choice = input("\nПродолжить без подключения к Elasticsearch? (y/N): ").lower().strip()
        if choice != 'y':
            print("Настройка прервана. Запустите Elasticsearch и повторите попытку.")
            return False
        print("[WARNING] Продолжаем без Elasticsearch. Некоторые функции могут не работать.")
    else:
        print("[OK] Подключение к Elasticsearch успешно!")
    
    print()
    
    # Шаг 2: Создание индексов
    print("ШАГ 2: Настройка индексов")
    print("-" * 50)
    
    if app.es_service.check_connection():
        create_indices = input("Создать/пересоздать индексы Elasticsearch? (Y/n): ").lower().strip()
        if create_indices != 'n':
            print("Создаем индексы (если не существуют)...")
            if app.setup_indices(force_recreate=False):
                print("[OK] Индексы готовы к работе!")
            else:
                print("[ERROR] Ошибка создания индексов!")
                return False
        else:
            print("Пропускаем создание индексов.")
    else:
        print("Пропускаем создание индексов (нет подключения к Elasticsearch).")
    
    print()
    
    # Шаг 3: Загрузка материалов
    print("ШАГ 3: Загрузка файла материалов")
    print("-" * 50)
    
    materials_file = None
    materials = []
    
    while not materials_file:
        print("Форматы: CSV, Excel (.xlsx), JSON")
        print("Пример структуры CSV:")
        print("id,name,description,category,brand,model,unit,specifications")
        print('1,"Кабель ВВГНГ","Силовой кабель","Кабели","Рыбинсккабель","ВВГНГ-LS 3x2.5","м","{""voltage"": ""0.66кВ""}"')
        print()
        
        materials_file = input("Путь к файлу материалов (или 'skip' для пропуска): ").strip()
        
        if materials_file.lower() == 'skip':
            print("Пропускаем загрузку материалов.")
            break
            
        if not Path(materials_file).exists():
            print(f"[ERROR] Файл '{materials_file}' не найден!")
            materials_file = None
            continue
        
        try:
            print(f"Загружаем материалы из {materials_file}...")
            materials = app.load_materials(materials_file)
            if materials:
                print(f"[OK] Загружено {len(materials)} материалов")
                
                # Показать примеры
                show_preview = input("Показать первые 3 материала для проверки? (Y/n): ").lower().strip()
                if show_preview != 'n':
                    for i, material in enumerate(materials[:3], 1):
                        print(f"\n  {i}. {material.name}")
                        print(f"     Категория: {material.category}")
                        print(f"     Бренд: {material.brand}")
                        print(f"     Описание: {material.description[:100]}{'...' if len(material.description) > 100 else ''}")
                
                confirm = input(f"\nПродолжить с этими {len(materials)} материалами? (Y/n): ").lower().strip()
                if confirm == 'n':
                    materials_file = None
                    materials = []
                    continue
                break
            else:
                print("[ERROR] Не удалось загрузить материалы из файла!")
                materials_file = None
        except Exception as e:
            print(f"[ERROR] Ошибка загрузки файла: {e}")
            materials_file = None
    
    print()
    
    # Шаг 4: Загрузка прайс-листа
    print("ШАГ 4: Загрузка прайс-листа")
    print("-" * 50)
    
    price_file = None
    price_items = []
    
    while not price_file:
        print("Форматы: CSV, Excel (.xlsx), JSON")
        print("Пример структуры CSV:")
        print("id,material_name,description,price,currency,supplier,category,brand,unit,specifications")
        print('1,"Кабель силовой ВВГНГ-LS","Кабель для проводки",150.50,"RUB","ООО Поставщик","Кабели","Рыбинсккабель","м","{""voltage"": ""660В""}"')
        print()
        
        price_file = input("Путь к файлу прайс-листа (или 'skip' для пропуска): ").strip()
        
        if price_file.lower() == 'skip':
            print("Пропускаем загрузку прайс-листа.")
            break
            
        if not Path(price_file).exists():
            print(f"[ERROR] Файл '{price_file}' не найден!")
            price_file = None
            continue
        
        try:
            print(f"Загружаем прайс-лист из {price_file}...")
            price_items = app.load_price_list(price_file)
            if price_items:
                print(f"[OK] Загружено {len(price_items)} позиций прайс-листа")
                
                # Показать примеры
                show_preview = input("Показать первые 3 позиции для проверки? (Y/n): ").lower().strip()
                if show_preview != 'n':
                    for i, item in enumerate(price_items[:3], 1):
                        print(f"\n  {i}. {item.material_name}")
                        print(f"     Поставщик: {item.supplier}")
                        print(f"     Цена: {item.price} {item.currency}")
                        print(f"     Категория: {item.category}")
                        print(f"     Описание: {item.description[:100]}{'...' if len(item.description) > 100 else ''}")
                
                confirm = input(f"\nПродолжить с этими {len(price_items)} позициями? (Y/n): ").lower().strip()
                if confirm == 'n':
                    price_file = None
                    price_items = []
                    continue
                break
            else:
                print("[ERROR] Не удалось загрузить прайс-лист из файла!")
                price_file = None
        except Exception as e:
            print(f"[ERROR] Ошибка загрузки файла: {e}")
            price_file = None
    
    print()
    
    # Шаг 5: Индексация данных
    if materials or price_items:
        print("ШАГ 5: Индексация данных в Elasticsearch")
        print("-" * 50)
        
        if app.es_service.check_connection():
            index_data = input("Проиндексировать загруженные данные? (Y/n): ").lower().strip()
            if index_data != 'n':
                print("Индексируем данные...")
                if app.index_data(materials, price_items):
                    print("[OK] Данные успешно проиндексированы!")
                else:
                    print("[ERROR] Ошибка индексации данных!")
                    return False
            else:
                print("Пропускаем индексацию данных.")
        else:
            print("Пропускаем индексацию (нет подключения к Elasticsearch).")
        
        print()
    
    # Шаг 6: Тестовое сопоставление
    if materials and price_items and app.es_service.check_connection():
        print("ШАГ 6: Тестовое сопоставление")
        print("-" * 50)
        
        test_matching = input("Запустить тестовое сопоставление первых материалов? (Y/n): ").lower().strip()
        if test_matching != 'n':
            print("Запускаем тестовое сопоставление...")
            
            # Берем первые 5 материалов для теста
            test_materials = materials[:5]
            results = app.run_matching(test_materials)
            
            if results:
                print(f"[OK] Тест завершен! Найдены соответствия для материалов.")
                
                # Показать лучшие результаты
                for material_id, matches in results.items():
                    if matches:
                        best_match = max(matches, key=lambda x: x.similarity_percentage)
                        material = next(m for m in test_materials if m.id == material_id)
                        print(f"\n  • {material.name}")
                        print(f"    Лучшее соответствие: {best_match.price_item.material_name}")
                        print(f"    Похожесть: {best_match.similarity_percentage:.1f}%")
                        print(f"    Поставщик: {best_match.price_item.supplier}")
                        print(f"    Цена: {best_match.price_item.price} {best_match.price_item.currency}")
                        break  # Показываем только один пример
                
                # Предложить полное сопоставление
                full_matching = input(f"\nЗапустить полное сопоставление всех {len(materials)} материалов? (y/N): ").lower().strip()
                if full_matching == 'y':
                    print("Запускаем полное сопоставление...")
                    results = app.run_matching(materials)
                    
                    if results:
                        output_file = f"setup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        app.export_results(results, output_file)
                        print(f"[OK] Результаты сохранены в {output_file}")
            else:
                print("[WARNING] Тестовое сопоставление не дало результатов.")
    
    print()
    print("=" * 60)
    print("   НАСТРОЙКА ЗАВЕРШЕНА!")
    print("=" * 60)
    print()
    print("Система готова к использованию!")
    print()
    print("Основные команды:")
    print("  python main.py --materials <файл> --price-list <файл> --output results.json")
    print("  python main.py --search-material 'название материала'")
    print("  python main.py --help")
    print()
    
    return True


def load_config(config_path: str = None):
    """Загрузка оптимизированной конфигурации приложения"""
    default_config = {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "username": None,
            "password": None,
            # ОПТИМИЗАЦИЯ: Добавляем новые параметры производительности
            "bulk_size": 750,
            "max_workers": 4
        },
        "matching": {
            "similarity_threshold": 20.0,
            "max_results_per_material": 4,
            "max_workers": 4
        }
    }
    
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Объединяем с дефолтной конфигурацией
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subvalue
            return config
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            print("Используется конфигурация по умолчанию")
    
    return default_config


def main():
    """Главная функция для запуска приложения с поддержкой Elasticsearch"""
    parser = argparse.ArgumentParser(
        description="Material Matching System with Elasticsearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  
  # Запуск графического интерфейса (РЕКОМЕНДУЕТСЯ)
  python main.py --gui
  
  # Интерактивная первоначальная настройка
  python main.py --init
  
  # Инициализация индексов Elasticsearch
  python main.py --setup
  
  # Полное сопоставление с созданием индексов
  python main.py --setup --materials data/sample/materials.csv --price-list data/sample/price_list.csv --output results.json
  
  # Сопоставление с существующими индексами
  python main.py --materials data/materials.csv --price-list data/price_list.csv --threshold 30 --format csv --output results.csv
  
  # Поиск отдельного материала
  python main.py --search-material "Кабель ВВГНГ" --top-n 5
        """
    )
    
    parser.add_argument('--config', type=str, default='config.json', 
                       help='Путь к файлу конфигурации (по умолчанию: config.json)')
    parser.add_argument('--materials', type=str, 
                       help='Путь к файлу материалов (CSV, Excel, JSON)')
    parser.add_argument('--price-list', type=str, 
                       help='Путь к файлу прайс-листа (CSV, Excel, JSON)')
    parser.add_argument('--output', type=str, default='results.json', 
                       help='Путь к выходному файлу (по умолчанию: results.json)')
    parser.add_argument('--format', type=str, choices=['json', 'csv', 'xlsx'], default='json', 
                       help='Формат выходного файла (по умолчанию: json)')
    parser.add_argument('--setup', action='store_true', 
                       help='Создать/пересоздать индексы Elasticsearch')
    parser.add_argument('--threshold', type=float, default=None, 
                       help='Порог похожести 0-100 (по умолчанию из конфигурации)')
    parser.add_argument('--search-material', type=str, 
                       help='Поиск соответствий для конкретного материала по названию')
    parser.add_argument('--top-n', type=int, default=10, 
                       help='Количество лучших соответствий (по умолчанию: 10)')
    parser.add_argument('--check-connection', action='store_true', 
                       help='Проверить подключение к Elasticsearch')
    parser.add_argument('--init', action='store_true', 
                       help='Интерактивная настройка системы для первоначальной загрузки')
    parser.add_argument('--gui', action='store_true', 
                       help='Запуск графического интерфейса')
    
    args = parser.parse_args()
    
    try:
        # GUI интерфейс
        if args.gui:
            try:
                import gui_app
                gui_app.main()
                return 0
            except Exception as e:
                print(f"[ERROR] Ошибка запуска GUI: {e}")
                return 1
        
        # Интерактивная настройка
        if args.init:
            return 0 if interactive_setup() else 1
        
        # Загрузка конфигурации
        print("Загрузка конфигурации...")
        config = load_config(args.config)
        
        # Переопределение порога похожести из аргументов
        if args.threshold is not None:
            config['matching']['similarity_threshold'] = args.threshold
        
        # Инициализация приложения
        print("Инициализация приложения...")
        app = MaterialMatcherApp(config)
        
        # Проверка подключения к Elasticsearch только если требуется
        needs_elasticsearch = args.setup or args.materials or args.price_list or args.search_material or args.check_connection
        
        if needs_elasticsearch:
            print("Проверка подключения к Elasticsearch...")
            if app.es_service.check_connection():
                print("[OK] Подключение к Elasticsearch успешно")
                if args.check_connection:
                    return 0
            else:
                print("[ERROR] Не удается подключиться к Elasticsearch")
                print("Убедитесь, что Elasticsearch запущен:")
                print("docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e \"discovery.type=single-node\" elasticsearch:8.15.1")
                return 1
        elif args.check_connection:
            print("Проверка подключения к Elasticsearch...")
            if app.es_service.check_connection():
                print("[OK] Подключение к Elasticsearch успешно")
            else:
                print("[ERROR] Не удается подключиться к Elasticsearch")
                print("Убедитесь, что Elasticsearch запущен:")
                print("docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e \"discovery.type=single-node\" elasticsearch:8.15.1")
                return 1
            return 0
        
        # Создание индексов
        if args.setup:
            print("Пересоздание индексов Elasticsearch...")
            # Принудительное пересоздание только для --setup
            if app.setup_indices(force_recreate=True):
                print("[OK] Индексы пересозданы успешно")
            else:
                print("[ERROR] Ошибка пересоздания индексов")
                return 1
        
        # Поиск конкретного материала
        if args.search_material:
            print(f"Поиск соответствий для материала: {args.search_material}")
            matches = app.search_material_by_name(args.search_material, top_n=args.top_n)
            
            if matches:
                print(f"\nНайдено {len(matches)} соответствий:")
                for i, match in enumerate(matches, 1):
                    print(f"\n{i}. {match['price_item']['material_name']}")
                    print(f"   Поставщик: {match['price_item']['supplier']}")
                    print(f"   Цена: {match['price_item']['price']} {match['price_item']['currency']}")
                    print(f"   Похожесть: {match['similarity_percentage']:.1f}%")
                    print(f"   Детали похожести:")
                    for detail, value in match['similarity_details'].items():
                        print(f"     - {detail}: {value:.1f}%")
            else:
                print("Соответствия не найдены")
            return 0
        
        # Полный процесс сопоставления
        if args.materials and args.price_list:
            print("Начинаем процесс сопоставления материалов...")
            
            # Загрузка данных
            print("Загрузка материалов...")
            materials = app.load_materials(args.materials)
            if not materials:
                print("[ERROR] Ошибка загрузки материалов")
                return 1
            print(f"[OK] Загружено {len(materials)} материалов")
            
            print("Загрузка прайс-листа...")
            price_items = app.load_price_list(args.price_list)
            if not price_items:
                print("[ERROR] Ошибка загрузки прайс-листа")
                return 1
            print(f"[OK] Загружено {len(price_items)} позиций прайс-листа")
            
            # Индексация данных
            print("Индексация данных в Elasticsearch...")
            if app.index_data(materials, price_items):
                print("[OK] Данные проиндексированы успешно")
            else:
                print("[ERROR] Ошибка индексации данных")
                return 1
            
            # Запуск сопоставления
            print("Запуск процесса сопоставления...")
            results = app.run_matching(materials)
            
            if results:
                # Статистика
                total_materials = len(results)
                materials_with_matches = sum(1 for matches in results.values() if matches)
                total_matches = sum(len(matches) for matches in results.values())
                
                print(f"\n[OK] Сопоставление завершено:")
                print(f"   Всего материалов: {total_materials}")
                print(f"   Найдены соответствия: {materials_with_matches}")
                print(f"   Общее количество соответствий: {total_matches}")
                
                # Экспорт результатов
                print(f"Экспорт результатов в {args.output}...")
                app.export_results(results, args.output, args.format)
                print(f"[OK] Результаты экспортированы в {args.output}")
                
            else:
                print("[ERROR] Сопоставление не дало результатов")
                return 1
        
        elif args.materials or args.price_list:
            print("Для полного сопоставления требуются оба файла: --materials и --price-list")
            return 1
        
        elif not args.setup and not args.search_material and not args.check_connection:
            print("Используйте --help для просмотра доступных команд")
            parser.print_help()
            return 0
        
        print("\n[OK] Операция завершена успешно")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Операция прервана пользователем")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Ошибка выполнения: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())