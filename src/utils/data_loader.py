import csv
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
from datetime import datetime
import chardet
import logging

from ..models.material import Material, PriceListItem
from .excel_loader import SmartExcelLoader

# Импорт оптимизированного загрузчика JSON
try:
    from .optimized_json_loader import OptimizedJSONLoader, create_progress_reporter
    OPTIMIZED_LOADER_AVAILABLE = True
except ImportError:
    OPTIMIZED_LOADER_AVAILABLE = False


class FlexibleJSONMapper:
    """Класс для гибкого маппинга полей JSON"""
    
    # Возможные варианты названий полей для материалов
    FIELD_MAPPINGS = {
        'name': ['name', 'material_name', 'title', 'наименование', 'наименования', 'название'],
        'description': ['description', 'desc', 'details', 'описание', 'детали'],
        'category': ['category', 'class', 'type', 'категория', 'класс', 'тип'],
        'brand': ['brand', 'бренд'],
        'manufacturer': ['manufacturer', 'производитель', 'завод производитель', 'завод изг', 'завод изг.', 'Завод изг', 'Завод изг.', 'завод изг.', 'Завод изг .'],
        'equipment_code': ['equipment_code', 'код обор', 'код обор.', 'код оборудования', 'equipment', 'Код обор', 'Код обор.'],
        'type_mark': ['type_mark', 'тип марка', 'тип, марка', 'марка', 'тип'],
        'model': ['model', 'модель'],
        'unit': ['unit', 'measure', 'единица', 'ед_изм', 'ед. изм.'],
        'quantity': ['quantity', 'qty', 'кол-во', 'количество'],
        'id': ['id', 'article', 'артикул'],  # Убираем 'code' и 'код' чтобы не конфликтовало с equipment_code
        # Для прайс-листов (новая структура)
        'article': ['article', 'артикул'],  # Убираем 'код' чтобы не конфликтовало с equipment_code
        'brand_code': ['brand_code', 'код_бренда', 'код бренда'],
        'cli_code': ['cli_code', 'client_code', 'клиентский_код', 'клиентский код'],
        'material_class': ['class', 'material_class', 'класс', 'класс материала'],
        'class_code': ['class_code', 'код_класса', 'код класса'],
        'price': ['price', 'cost', 'цена', 'стоимость'],
        'currency': ['currency', 'валюта'],
        'supplier': ['supplier', 'vendor', 'поставщик', 'продавец'],
        # Для обратной совместимости
        'material_name': ['material_name', 'name', 'title', 'наименование', 'название']
    }
    
    @staticmethod
    def auto_map_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Автоматический маппинг полей JSON на стандартные поля"""
        if not data:
            return data
            
        mapped_data = {}
        available_keys = [k.lower() for k in data.keys()]
        
        # ИСПРАВЛЕНИЕ: Сначала ищем все точные совпадения, потом частичные
        used_keys = set()  # Отслеживаем уже использованные ключи

        # ЭТАП 1: Точные совпадения (высокий приоритет)
        for standard_field, possible_names in FlexibleJSONMapper.FIELD_MAPPINGS.items():
            mapped_value = None
            mapped_key = None

            # Ищем только точные совпадения
            for possible_name in possible_names:
                possible_name_lower = possible_name.lower().strip()

                for original_key in data.keys():
                    if original_key not in used_keys and original_key.lower().strip() == possible_name_lower:
                        mapped_value = data[original_key]
                        mapped_key = original_key
                        break

                if mapped_value is not None:
                    break

            # Если нашли точное совпадение, добавляем его
            if mapped_value is not None:
                mapped_data[standard_field] = mapped_value
                used_keys.add(mapped_key)

        # ЭТАП 2: Частичные совпадения (низкий приоритет)
        for standard_field, possible_names in FlexibleJSONMapper.FIELD_MAPPINGS.items():
            # Пропускаем уже заполненные поля
            if standard_field in mapped_data:
                continue

            mapped_value = None
            mapped_key = None

            # Ищем частичные совпадения среди неиспользованных ключей
            for possible_name in possible_names:
                possible_name_lower = possible_name.lower().strip()

                for original_key in data.keys():
                    if original_key not in used_keys and possible_name_lower in original_key.lower().strip():
                        mapped_value = data[original_key]
                        mapped_key = original_key
                        break

                if mapped_value is not None:
                    break

            # Если нашли частичное совпадение, добавляем его
            if mapped_value is not None:
                mapped_data[standard_field] = mapped_value
                used_keys.add(mapped_key)
        
        # Добавляем оставшиеся поля как specifications
        specifications = {}
        for key, value in data.items():
            # Проверяем, не был ли этот ключ уже смаппен
            key_was_mapped = False
            for possible_names in FlexibleJSONMapper.FIELD_MAPPINGS.values():
                if key.lower() in [name.lower() for name in possible_names]:
                    key_was_mapped = True
                    break
            
            if not key_was_mapped and value is not None:
                specifications[key] = value
        
        if specifications:
            mapped_data['specifications'] = specifications
            
        return mapped_data


class MaterialLoader:
    """Загрузчик материалов из различных источников"""
    
    @staticmethod
    def detect_encoding(file_path: str) -> str:
        """Автоопределение кодировки файла"""
        logger = logging.getLogger(__name__)
        
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # Читаем первые 10KB для определения кодировки
                result = chardet.detect(raw_data)
                detected_encoding = result['encoding']
                confidence = result['confidence']
                
                logger.info(f"Определена кодировка {detected_encoding} с уверенностью {confidence:.2f} для файла {file_path}")
                
                # Если уверенность низкая, используем UTF-8 по умолчанию
                if confidence < 0.7:
                    logger.warning(f"Низкая уверенность в кодировке, используем UTF-8 по умолчанию")
                    return 'utf-8'
                    
                # Особая обработка для Windows-1251
                if detected_encoding and 'windows-1251' in detected_encoding.lower():
                    return 'windows-1251'
                elif detected_encoding and 'utf-8' in detected_encoding.lower():
                    return 'utf-8'
                else:
                    return detected_encoding or 'utf-8'
                    
        except Exception as e:
            logger.warning(f"Ошибка при определении кодировки файла {file_path}: {e}. Используем UTF-8")
            return 'utf-8'
    
    @staticmethod
    def detect_csv_delimiter(file_path: str, encoding: str) -> str:
        """Автоопределение разделителя CSV файла"""
        logger = logging.getLogger(__name__)
        
        try:
            with open(file_path, 'r', encoding=encoding) as csvfile:
                # Читаем первые несколько строк для определения разделителя
                sample = csvfile.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                logger.info(f"Определен разделитель CSV: '{delimiter}'")
                return delimiter
        except Exception as e:
            logger.warning(f"Не удалось автоопределить разделитель: {e}. Используем ';' по умолчанию")
            return ';'
    
    @staticmethod
    def load_from_csv(file_path: str, encoding: str = None) -> List[Material]:
        """Загрузка материалов из CSV файла с автоопределением кодировки и разделителя"""
        logger = logging.getLogger(__name__)
        materials = []
        
        # Автоопределение кодировки если не указана
        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)
            
        logger.info(f"Загрузка материалов из CSV: {file_path} (кодировка: {encoding})")
        
        # Определяем разделитель
        delimiter = MaterialLoader.detect_csv_delimiter(file_path, encoding)
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=delimiter)
        except UnicodeDecodeError as e:
            logger.warning(f"Ошибка кодировки {encoding}, пробуем другие варианты: {e}")
            # Пробуем альтернативные кодировки
            for alt_encoding in ['windows-1251', 'utf-8', 'cp1252']:
                try:
                    logger.info(f"Попытка загрузки с кодировкой {alt_encoding}")
                    delimiter = MaterialLoader.detect_csv_delimiter(file_path, alt_encoding)
                    with open(file_path, 'r', encoding=alt_encoding, newline='') as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=delimiter)
                        encoding = alt_encoding
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Не удалось определить правильную кодировку файла")
        
        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            for row in reader:
                # Обработка спецификаций если они есть в JSON формате
                specifications = {}
                if 'specifications' in row and row['specifications']:
                    try:
                        specifications = json.loads(row['specifications'])
                    except json.JSONDecodeError:
                        specifications = {}
                
                material = Material(
                    id=row.get('id', str(uuid.uuid4())),
                    name=row['name'],
                    description=row.get('description', ''),
                    category=row.get('category', 'Unknown'),
                    brand=row.get('brand'),
                    model=row.get('model'),
                    specifications=specifications,
                    unit=row.get('unit'),
                    created_at=datetime.now()
                )
                materials.append(material)
        
        return materials
    
    @staticmethod
    def load_from_excel(file_path: str, sheet_name: Optional[str] = None) -> List[Material]:
        """Загрузка материалов из Excel файла с автоопределением колонок"""
        try:
            # Пытаемся использовать умный загрузчик
            loader = SmartExcelLoader()
            return loader.load_materials_from_excel(file_path, sheet_name)
        except Exception as e:
            # Fallback на старый метод для файлов со стандартной структурой
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            materials = []
            
            # Проверяем наличие обязательных колонок
            if 'name' not in df.columns:
                # Если нет стандартных колонок, используем первую колонку как name
                if len(df.columns) > 0:
                    df['name'] = df[df.columns[0]]
                else:
                    raise ValueError("Не удалось определить структуру файла")
            
            for idx, row in df.iterrows():
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in df.columns and pd.notna(row.get('specifications')):
                    try:
                        specifications = json.loads(str(row['specifications']))
                    except (json.JSONDecodeError, TypeError):
                        specifications = {}
                
                material = Material(
                    id=str(row.get('id', idx + 1)),
                    name=str(row.get('name', '')),
                    description=str(row.get('description', row.get('name', ''))),
                    category=str(row.get('category', 'Общая')),
                    brand=str(row.get('brand')) if pd.notna(row.get('brand')) else None,
                    model=str(row.get('model')) if pd.notna(row.get('model')) else None,
                    specifications=specifications,
                    unit=str(row.get('unit', 'шт')) if pd.notna(row.get('unit')) else 'шт',
                    created_at=datetime.now()
                )
                if material.name and material.name != 'nan':
                    materials.append(material)
            
            return materials
    
    @staticmethod
    def load_from_json(file_path: str, encoding: str = 'utf-8', use_optimized: bool = None) -> List[Material]:
        """Загрузка материалов из JSON файла с автоматическим маппингом полей

        Args:
            file_path: Путь к JSON файлу
            encoding: Кодировка файла
            use_optimized: Использовать оптимизированный загрузчик (автоопределение если None)
        """
        # Автоопределение необходимости оптимизированного загрузчика
        if use_optimized is None:
            try:
                file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                # Используем оптимизированный загрузчик для файлов > 5 МБ
                use_optimized = file_size_mb > 5
            except:
                use_optimized = False

        # Если выбран оптимизированный загрузчик и он доступен
        if use_optimized:
            print(f"[INFO] Использование оптимизированного загрузчика JSON")
            try:
                optimized_loader = OptimizedJSONLoader()
                progress_callback = create_progress_reporter(update_interval=10000)
                return optimized_loader.load_materials_from_json(file_path, encoding, progress_callback)
            except Exception as e:
                print(f"[WARNING] Ошибка оптимизированного загрузчика: {e}")
                print(f"[INFO] Переключение на стандартный загрузчик")

        # Стандартный загрузчик (оригинальный код)
        print(f"[INFO] Начинаю загрузку JSON файла: {file_path}")
        start_time = datetime.now()

        with open(file_path, 'r', encoding=encoding) as jsonfile:
            data = json.load(jsonfile)

        if not isinstance(data, list):
            print("[ERROR] JSON файл должен содержать массив объектов")
            return []

        print(f"[INFO] Загружено {len(data)} записей из JSON")

        materials = []
        mapped_count = 0

        for i, item in enumerate(data):
            try:
                # Применяем гибкий маппинг полей
                mapped_item = FlexibleJSONMapper.auto_map_fields(item)

                # Проверяем обязательные поля
                if not mapped_item.get('name'):
                    continue

                # Создаем объект Material с обработкой отсутствующих полей
                material = Material(
                    id=mapped_item.get('id', str(i + 1)),
                    name=str(mapped_item['name']).strip(),
                    type_mark=str(mapped_item.get('type_mark', '')).strip() if mapped_item.get('type_mark') else None,
                    equipment_code=str(mapped_item.get('equipment_code', '')).strip() if mapped_item.get('equipment_code') else None,
                    manufacturer=str(mapped_item.get('manufacturer', '')).strip() if mapped_item.get('manufacturer') else None,
                    unit=str(mapped_item.get('unit', '')).strip() if mapped_item.get('unit') else None,
                    quantity=mapped_item.get('quantity') if mapped_item.get('quantity') is not None else None,
                    # Для обратной совместимости
                    description=str(mapped_item.get('description', '')).strip(),
                    category=str(mapped_item.get('category', '')).strip(),
                    brand=str(mapped_item.get('brand', '')).strip() if mapped_item.get('brand') else None,
                    model=str(mapped_item.get('model', '')).strip() if mapped_item.get('model') else None,
                    specifications=mapped_item.get('specifications', {}),
                    created_at=datetime.now()
                )

                materials.append(material)
                mapped_count += 1

                # Логируем прогресс для больших файлов
                if len(data) > 1000 and (i + 1) % 10000 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    print(f"[INFO] Обработано {i + 1}/{len(data)} записей за {elapsed:.2f}сек")

            except Exception as e:
                print(f"[WARNING] Ошибка обработки записи {i}: {e}")
                continue

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"[OK] Гибкий JSON маппинг завершен:")
        print(f"      - Успешно загружено {len(materials)} материалов")
        print(f"      - Время загрузки: {elapsed:.2f} секунды")
        if mapped_count < len(data):
            print(f"      - Пропущено записей без обязательных полей: {len(data) - mapped_count}")

        return materials


class PriceListLoader:
    """Загрузчик прайс-листов из различных источников"""
    
    @staticmethod
    def detect_csv_delimiter(file_path: str, encoding: str) -> str:
        """Автоопределение разделителя CSV файла"""
        logger = logging.getLogger(__name__)
        
        try:
            with open(file_path, 'r', encoding=encoding) as csvfile:
                # Читаем первые несколько строк для определения разделителя
                sample = csvfile.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                logger.info(f"Определен разделитель CSV: '{delimiter}'")
                return delimiter
        except Exception as e:
            logger.warning(f"Не удалось автоопределить разделитель: {e}. Используем ';' по умолчанию")
            return ';'
    
    @staticmethod
    def load_from_csv(file_path: str, encoding: str = None) -> List[PriceListItem]:
        """Загрузка прайс-листа из CSV файла с автоопределением кодировки и разделителя"""
        logger = logging.getLogger(__name__)
        price_items = []
        
        # Автоопределение кодировки если не указана
        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)
            
        logger.info(f"Загрузка прайс-листа из CSV: {file_path} (кодировка: {encoding})")
        
        # Определяем разделитель
        delimiter = PriceListLoader.detect_csv_delimiter(file_path, encoding)
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=delimiter)
        except UnicodeDecodeError as e:
            logger.warning(f"Ошибка кодировки {encoding}, пробуем другие варианты: {e}")
            # Пробуем альтернативные кодировки
            for alt_encoding in ['windows-1251', 'utf-8', 'cp1252']:
                try:
                    logger.info(f"Попытка загрузки с кодировкой {alt_encoding}")
                    delimiter = PriceListLoader.detect_csv_delimiter(file_path, alt_encoding)
                    with open(file_path, 'r', encoding=alt_encoding, newline='') as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=delimiter)
                        encoding = alt_encoding
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Не удалось определить правильную кодировку файла")
        
        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            for row in reader:
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in row and row['specifications']:
                    try:
                        specifications = json.loads(row['specifications'])
                    except json.JSONDecodeError:
                        specifications = {}
                
                # Получаем цену
                price_value = 0.0
                try:
                    price_value = float(row.get('price', 0))
                except (ValueError, TypeError):
                    price_value = 0.0
                
                price_item = PriceListItem(
                    id=row.get('id', str(uuid.uuid4())),
                    name=row.get('name', row.get('material_name', '')),
                    brand=row.get('brand'),
                    article=row.get('article'),
                    brand_code=row.get('brand_code'),
                    cli_code=row.get('cli_code'),
                    material_class=row.get('class', row.get('material_class')),
                    class_code=row.get('class_code'),
                    price=price_value,
                    # Для обратной совместимости
                    material_name=row.get('material_name', row.get('name', '')),
                    description=row.get('description', ''),
                    currency=row.get('currency', 'RUB'),
                    supplier=row.get('supplier', ''),
                    category=row.get('category'),
                    unit=row.get('unit'),
                    specifications=specifications,
                    updated_at=datetime.now()
                )
                price_items.append(price_item)
        
        return price_items
    
    @staticmethod
    def load_from_excel(file_path: str, sheet_name: Optional[str] = None) -> List[PriceListItem]:
        """Загрузка прайс-листа из Excel файла с автоопределением колонок"""
        try:
            # Пытаемся использовать умный загрузчик
            loader = SmartExcelLoader()
            return loader.load_pricelist_from_excel(file_path, sheet_name)
        except Exception as e:
            # Fallback на старый метод для файлов со стандартной структурой
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            price_items = []
            
            # Проверяем наличие обязательных колонок
            name_col = None
            if 'name' in df.columns:
                name_col = 'name'
            elif 'material_name' in df.columns:
                name_col = 'material_name'
            elif len(df.columns) > 0:
                # Ищем первую текстовую колонку
                for col in df.columns:
                    if df[col].dtype == 'object':
                        name_col = col
                        break
                if not name_col:
                    name_col = df.columns[0]
            
            if not name_col:
                raise ValueError("Не удалось определить колонку с названием материала")
            
            # Если нет цены, ставим 0
            if 'price' not in df.columns:
                df['price'] = 0.0
            
            # Если нет поставщика, ставим "Не указан"
            if 'supplier' not in df.columns:
                df['supplier'] = 'Не указан'
            
            for idx, row in df.iterrows():
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in df.columns and pd.notna(row.get('specifications')):
                    try:
                        specifications = json.loads(str(row['specifications']))
                    except (json.JSONDecodeError, TypeError):
                        specifications = {}
                
                # Попытка извлечь цену
                price = 0.0
                try:
                    price = float(row.get('price', 0))
                except:
                    price = 0.0
                
                # Получаем название материала
                name_value = str(row.get(name_col, ''))
                if pd.isna(row.get(name_col)):
                    name_value = ''
                
                price_item = PriceListItem(
                    id=str(row.get('id', idx + 1)),
                    name=name_value,
                    brand=str(row.get('brand')) if pd.notna(row.get('brand')) else None,
                    article=str(row.get('article')) if pd.notna(row.get('article')) else None,
                    brand_code=str(row.get('brand_code')) if pd.notna(row.get('brand_code')) else None,
                    cli_code=str(row.get('cli_code')) if pd.notna(row.get('cli_code')) else None,
                    material_class=str(row.get('class', row.get('material_class'))) if pd.notna(row.get('class', row.get('material_class'))) else None,
                    class_code=str(row.get('class_code')) if pd.notna(row.get('class_code')) else None,
                    price=price,
                    # Для обратной совместимости
                    material_name=name_value,
                    description=str(row.get('description', name_value)),
                    currency=str(row.get('currency', 'RUB')),
                    supplier=str(row.get('supplier', 'Не указан')),
                    category=str(row.get('category', 'Общая')) if pd.notna(row.get('category')) else 'Общая',
                    unit=str(row.get('unit', 'шт')) if pd.notna(row.get('unit')) else 'шт',
                    specifications=specifications,
                    updated_at=datetime.now()
                )
                if price_item.name and price_item.name != 'nan':
                    price_items.append(price_item)
            
            return price_items
    
    @staticmethod
    def load_from_json(file_path: str, encoding: str = 'utf-8', use_optimized: bool = None) -> List[PriceListItem]:
        """Загрузка прайс-листа из JSON файла с автоматическим маппингом полей

        Args:
            file_path: Путь к JSON файлу
            encoding: Кодировка файла
            use_optimized: Использовать оптимизированный загрузчик (автоопределение если None)
        """
        # Автоопределение необходимости оптимизированного загрузчика
        if use_optimized is None:
            try:
                file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                # Используем оптимизированный загрузчик для файлов > 5 МБ
                use_optimized = file_size_mb > 5
            except:
                use_optimized = False

        # Если выбран оптимизированный загрузчик и он доступен
        if use_optimized:
            print(f"[INFO] Использование быстрого загрузчика JSON для прайс-листа")
            try:
                # Сначала пробуем быстрый загрузчик
                from .fast_json_loader import load_json_fast

                def progress_callback(current, total, message=""):
                    print(f"[INFO] Обработано {current}/{total} записей за {message}")

                return load_json_fast(file_path, progress_callback)

            except ImportError:
                print(f"[INFO] Быстрый загрузчик недоступен, пробуем оптимизированный")
                try:
                    optimized_loader = OptimizedJSONLoader()
                    progress_callback = create_progress_reporter(update_interval=10000)
                    return optimized_loader.load_price_list_from_json(file_path, encoding, progress_callback)
                except Exception as e:
                    print(f"[WARNING] Ошибка оптимизированного загрузчика: {e}")
            except Exception as e:
                print(f"[WARNING] Ошибка быстрого загрузчика: {e}")
                print(f"[INFO] Переключение на стандартный загрузчик")

        # Стандартный загрузчик (оригинальный код)
        print(f"[INFO] Начинаю загрузку JSON прайс-листа: {file_path}")
        start_time = datetime.now()

        with open(file_path, 'r', encoding=encoding) as jsonfile:
            data = json.load(jsonfile)
        
        if not isinstance(data, list):
            print("[ERROR] JSON файл должен содержать массив объектов")
            return []
        
        print(f"[INFO] Загружено {len(data)} записей из JSON прайс-листа")
        
        price_items = []
        mapped_count = 0
        
        for i, item in enumerate(data):
            try:
                # Применяем гибкий маппинг полей
                mapped_item = FlexibleJSONMapper.auto_map_fields(item)
                
                # Проверяем обязательные поля для прайс-листа
                name_value = mapped_item.get('name') or mapped_item.get('material_name')
                if not name_value:
                    continue
                    
                # Обрабатываем цену
                price_value = mapped_item.get('price', 0)
                try:
                    price_float = float(str(price_value).replace(',', '.').replace(' ', ''))
                except (ValueError, AttributeError):
                    price_float = 0.0
                    
                # Создаем объект PriceListItem с обработкой отсутствующих полей
                price_item = PriceListItem(
                    id=mapped_item.get('id', str(i + 1)),
                    name=str(name_value).strip(),
                    brand=str(mapped_item.get('brand', '')).strip() if mapped_item.get('brand') else None,
                    article=str(mapped_item.get('article', '')).strip() if mapped_item.get('article') else None,
                    brand_code=str(mapped_item.get('brand_code', '')).strip() if mapped_item.get('brand_code') else None,
                    cli_code=str(mapped_item.get('cli_code', '')).strip() if mapped_item.get('cli_code') else None,
                    material_class=str(mapped_item.get('material_class', '')).strip() if mapped_item.get('material_class') else None,
                    class_code=str(mapped_item.get('class_code', '')).strip() if mapped_item.get('class_code') else None,
                    price=price_float,
                    # Для обратной совместимости
                    material_name=str(name_value).strip(),
                    description=str(mapped_item.get('description', '')).strip(),
                    currency=str(mapped_item.get('currency', 'RUB')).strip(),
                    supplier=str(mapped_item.get('supplier', '')).strip(),
                    category=str(mapped_item.get('category', '')).strip() if mapped_item.get('category') else None,
                    unit=str(mapped_item.get('unit', '')).strip() if mapped_item.get('unit') else None,
                    specifications=mapped_item.get('specifications', {}),
                    updated_at=datetime.now()
                )
                
                price_items.append(price_item)
                mapped_count += 1
                
                # Логируем прогресс для больших файлов
                if len(data) > 1000 and (i + 1) % 10000 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    print(f"[INFO] Обработано {i + 1}/{len(data)} записей за {elapsed:.2f}сек")
                    
            except Exception as e:
                print(f"[WARNING] Ошибка обработки записи прайс-листа {i}: {e}")
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"[OK] Гибкий JSON маппинг прайс-листа завершен:")
        print(f"      - Успешно загружено {len(price_items)} позиций")
        print(f"      - Время загрузки: {elapsed:.2f} секунды")
        if mapped_count < len(data):
            print(f"      - Пропущено записей без обязательных полей: {len(data) - mapped_count}")
            
        return price_items


class DataLoader:
    """Универсальный загрузчик данных - объединяет функционал MaterialLoader и PriceListLoader"""
    
    def load_materials(self, file_path: str) -> List[Material]:
        """Загрузка материалов из файла (автоопределение формата)"""
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.csv':
            return MaterialLoader.load_from_csv(str(file_path))
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            return MaterialLoader.load_from_excel(str(file_path))
        elif file_path.suffix.lower() == '.json':
            return MaterialLoader.load_from_json(str(file_path))
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_path.suffix}")
    
    def load_price_list(self, file_path: str) -> List[PriceListItem]:
        """Загрузка прайс-листа из файла (автоопределение формата)"""
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.csv':
            return PriceListLoader.load_from_csv(str(file_path))
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            return PriceListLoader.load_from_excel(str(file_path))
        elif file_path.suffix.lower() == '.json':
            return PriceListLoader.load_from_json(str(file_path))
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_path.suffix}")


class DataExporter:
    """Экспортер результатов поиска"""
    
    @staticmethod
    def export_results_to_csv(results: List[Dict[str, Any]], file_path: str):
        """Экспорт результатов в CSV файл"""
        if not results:
            return
        
        # Подготовка данных для CSV
        csv_data = []
        for result in results:
            row = {
                'material_id': result['material']['id'],
                'material_name': result['material']['name'],
                'material_description': result['material']['description'],
                'material_category': result['material']['category'],
                'material_brand': result['material']['brand'] or '',
                'price_item_id': result['price_item']['id'],
                'price_item_name': result['price_item'].get('name', result['price_item'].get('material_name', '')),
                'price_item_description': result['price_item']['description'],
                'price': result['price_item']['price'],
                'currency': result['price_item']['currency'],
                'supplier': result['price_item']['supplier'],
                'similarity_percentage': result['similarity_percentage'],
                'elasticsearch_score': result['elasticsearch_score']
            }
            csv_data.append(row)
        
        # Запись в CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(file_path, index=False, encoding='utf-8')
    
    @staticmethod
    def export_results_to_xlsx(results: List[Dict[str, Any]], file_path: str):
        """Экспорт результатов в XLSX файл"""
        if not results:
            return
        
        # Подготовка данных для XLSX под новую структуру
        xlsx_data = []
        for result in results:
            # Получаем данные материала и прайс-листа
            material = result['material']
            price_item = result['price_item']
            
            row = {
                # Колонки материала (левая часть таблицы)
                'Наименования': material.get('name', ''),
                'Код обор.': material.get('equipment_code', ''),
                'Завод изг.': material.get('manufacturer', ''),
                
                # Колонка релевантности
                'Релевантность': f"{result['similarity_percentage']:.1f}%",
                
                # Колонки прайс-листа (правая часть таблицы)
                'name': price_item.get('name', ''),
                'article': price_item.get('article', ''),
                'brand': price_item.get('brand', ''),
                'id': price_item.get('id', ''),
                'Цена': price_item.get('price', ''),
                
                # Дополнительные поля для совместимости
                'ID материала': material.get('id', ''),
                'Описание материала': material.get('description', ''),
                'Категория материала': material.get('category', ''),
                'Тип, марка': material.get('type_mark', ''),
                'Ед. изм. (материал)': material.get('unit', ''),
                'Кол-во': material.get('quantity', ''),
                
                'Описание в прайсе': price_item.get('description', ''),
                'Код бренда': price_item.get('brand_code', ''),
                'Класс': price_item.get('material_class', ''),
                'Код класса': price_item.get('class_code', ''),
                'Валюта': price_item.get('currency', 'RUB'),
                'Elasticsearch Score': result.get('elasticsearch_score', 0)
            }
            xlsx_data.append(row)
        
        # Создание DataFrame и запись в XLSX
        df = pd.DataFrame(xlsx_data)
        
        # Простая запись в XLSX без сложного форматирования
        try:
            df.to_excel(file_path, sheet_name='Результаты сопоставления', index=False, engine='openpyxl')
        except Exception as e:
            # Fallback: запись без названия листа
            df.to_excel(file_path, index=False, engine='openpyxl')
    
    @staticmethod
    def export_results_to_json(results: List[Dict[str, Any]], file_path: str):
        """Экспорт результатов в JSON файл"""
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(results, jsonfile, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_from_price_list_directory(directory_path: str = None) -> List[PriceListItem]:
        """
        Автоматическая загрузка всех файлов прайс-листов из папки price-list
        
        Args:
            directory_path: Путь к папке с прайс-листами (по умолчанию: price-list)
            
        Returns:
            Список объектов PriceListItem
        """
        if directory_path is None:
            directory_path = Path.cwd() / 'price-list'
        else:
            directory_path = Path(directory_path)
            
        if not directory_path.exists():
            logging.warning(f"Папка {directory_path} не найдена")
            return []
        
        data_loader = DataLoader()
        all_price_items = []
        supported_extensions = ['.xlsx', '.json', '.csv']
        
        for file_path in directory_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    logging.info(f"Загружаем прайс-лист: {file_path}")
                    items = data_loader.load_price_list(str(file_path))
                    all_price_items.extend(items)
                except Exception as e:
                    logging.error(f"Ошибка при загрузке {file_path}: {e}")
                    continue
        
        logging.info(f"Загружено {len(all_price_items)} позиций из папки price-list")
        return all_price_items
    
    @staticmethod
    def load_from_material_directory(directory_path: str = None) -> List[Material]:
        """
        Автоматическая загрузка всех файлов материалов из папки material
        
        Args:
            directory_path: Путь к папке с материалами (по умолчанию: material)
            
        Returns:
            Список объектов Material
        """
        if directory_path is None:
            directory_path = Path.cwd() / 'material'
        else:
            directory_path = Path(directory_path)
            
        if not directory_path.exists():
            logging.warning(f"Папка {directory_path} не найдена")
            return []
        
        data_loader = DataLoader()
        all_materials = []
        supported_extensions = ['.xlsx', '.json', '.csv']
        
        for file_path in directory_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    logging.info(f"Загружаем материалы: {file_path}")
                    items = data_loader.load_materials(str(file_path))
                    all_materials.extend(items)
                except Exception as e:
                    logging.error(f"Ошибка при загрузке {file_path}: {e}")
                    continue
        
        logging.info(f"Загружено {len(all_materials)} материалов из папки material")
        return all_materials