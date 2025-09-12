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


class FlexibleJSONMapper:
    """Класс для гибкого маппинга полей JSON"""
    
    # Возможные варианты названий полей для материалов
    FIELD_MAPPINGS = {
        'name': ['name', 'material_name', 'title', 'наименование', 'название'],
        'description': ['description', 'desc', 'details', 'описание', 'детали'],
        'category': ['category', 'class', 'type', 'категория', 'класс', 'тип'],
        'brand': ['brand', 'manufacturer', 'бренд', 'производитель'],
        'model': ['model', 'модель'],
        'unit': ['unit', 'measure', 'единица', 'ед_изм'],
        'id': ['id', 'code', 'article', 'код', 'артикул'],
        # Для прайс-листов
        'material_name': ['material_name', 'name', 'title', 'наименование', 'название'],
        'price': ['price', 'cost', 'цена', 'стоимость'],
        'currency': ['currency', 'валюта'],
        'supplier': ['supplier', 'vendor', 'поставщик', 'продавец']
    }
    
    @staticmethod
    def auto_map_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Автоматический маппинг полей JSON на стандартные поля"""
        if not data:
            return data
            
        mapped_data = {}
        available_keys = [k.lower() for k in data.keys()]
        
        # Проходим по всем возможным полям
        for standard_field, possible_names in FlexibleJSONMapper.FIELD_MAPPINGS.items():
            mapped_value = None
            
            # Ищем соответствие среди возможных названий
            for possible_name in possible_names:
                possible_name_lower = possible_name.lower()
                
                # Точное совпадение
                for original_key in data.keys():
                    if original_key.lower() == possible_name_lower:
                        mapped_value = data[original_key]
                        break
                        
                if mapped_value is not None:
                    break
            
            # Если нашли значение, добавляем его
            if mapped_value is not None:
                mapped_data[standard_field] = mapped_value
        
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
    def load_from_csv(file_path: str, encoding: str = None) -> List[Material]:
        """Загрузка материалов из CSV файла с автоопределением кодировки"""
        logger = logging.getLogger(__name__)
        materials = []
        
        # Автоопределение кодировки если не указана
        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)
            
        logger.info(f"Загрузка материалов из CSV: {file_path} (кодировка: {encoding})")
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
        except UnicodeDecodeError as e:
            logger.warning(f"Ошибка кодировки {encoding}, пробуем другие варианты: {e}")
            # Пробуем альтернативные кодировки
            for alt_encoding in ['windows-1251', 'utf-8', 'cp1252']:
                try:
                    logger.info(f"Попытка загрузки с кодировкой {alt_encoding}")
                    with open(file_path, 'r', encoding=alt_encoding, newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        encoding = alt_encoding
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Не удалось определить правильную кодировку файла")
        
        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
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
    def load_from_json(file_path: str, encoding: str = 'utf-8') -> List[Material]:
        """Загрузка материалов из JSON файла с автоматическим маппингом полей"""
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
                    description=str(mapped_item.get('description', '')).strip(),
                    category=str(mapped_item.get('category', '')).strip(),
                    brand=str(mapped_item.get('brand', '')).strip() if mapped_item.get('brand') else None,
                    model=str(mapped_item.get('model', '')).strip() if mapped_item.get('model') else None,
                    specifications=mapped_item.get('specifications', {}),
                    unit=str(mapped_item.get('unit', '')).strip() if mapped_item.get('unit') else None,
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
    def load_from_csv(file_path: str, encoding: str = None) -> List[PriceListItem]:
        """Загрузка прайс-листа из CSV файла с автоопределением кодировки"""
        logger = logging.getLogger(__name__)
        price_items = []
        
        # Автоопределение кодировки если не указана
        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)
            
        logger.info(f"Загрузка прайс-листа из CSV: {file_path} (кодировка: {encoding})")
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
        except UnicodeDecodeError as e:
            logger.warning(f"Ошибка кодировки {encoding}, пробуем другие варианты: {e}")
            # Пробуем альтернативные кодировки
            for alt_encoding in ['windows-1251', 'utf-8', 'cp1252']:
                try:
                    logger.info(f"Попытка загрузки с кодировкой {alt_encoding}")
                    with open(file_path, 'r', encoding=alt_encoding, newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        encoding = alt_encoding
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Не удалось определить правильную кодировку файла")
        
        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in row and row['specifications']:
                    try:
                        specifications = json.loads(row['specifications'])
                    except json.JSONDecodeError:
                        specifications = {}
                
                price_item = PriceListItem(
                    id=row.get('id', str(uuid.uuid4())),
                    material_name=row['material_name'],
                    description=row.get('description', ''),
                    price=float(row['price']),
                    currency=row.get('currency', 'RUB'),
                    supplier=row['supplier'],
                    category=row.get('category'),
                    brand=row.get('brand'),
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
            if 'material_name' not in df.columns:
                # Если нет material_name, ищем name или используем первую текстовую колонку
                if 'name' in df.columns:
                    df['material_name'] = df['name']
                elif len(df.columns) > 0:
                    # Ищем первую текстовую колонку
                    for col in df.columns:
                        if df[col].dtype == 'object':
                            df['material_name'] = df[col]
                            break
                    if 'material_name' not in df.columns:
                        df['material_name'] = df[df.columns[0]]
            
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
                
                price_item = PriceListItem(
                    id=str(row.get('id', idx + 1)),
                    material_name=str(row.get('material_name', '')),
                    description=str(row.get('description', row.get('material_name', ''))),
                    price=price,
                    currency=str(row.get('currency', 'RUB')),
                    supplier=str(row.get('supplier', 'Не указан')),
                    category=str(row.get('category', 'Общая')) if pd.notna(row.get('category')) else 'Общая',
                    brand=str(row.get('brand')) if pd.notna(row.get('brand')) else None,
                    unit=str(row.get('unit', 'шт')) if pd.notna(row.get('unit')) else 'шт',
                    specifications=specifications,
                    updated_at=datetime.now()
                )
                if price_item.material_name and price_item.material_name != 'nan':
                    price_items.append(price_item)
            
            return price_items
    
    @staticmethod
    def load_from_json(file_path: str, encoding: str = 'utf-8') -> List[PriceListItem]:
        """Загрузка прайс-листа из JSON файла с автоматическим маппингом полей"""
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
                material_name = mapped_item.get('material_name') or mapped_item.get('name')
                if not material_name:
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
                    material_name=str(material_name).strip(),
                    description=str(mapped_item.get('description', '')).strip(),
                    price=price_float,
                    currency=str(mapped_item.get('currency', 'RUB')).strip(),
                    supplier=str(mapped_item.get('supplier', '')).strip(),
                    category=str(mapped_item.get('category', '')).strip() if mapped_item.get('category') else None,
                    brand=str(mapped_item.get('brand', '')).strip() if mapped_item.get('brand') else None,
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
                'price_item_name': result['price_item']['material_name'],
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
        
        # Подготовка данных для XLSX
        xlsx_data = []
        for result in results:
            row = {
                'ID материала': result['material']['id'],
                'Материал': result['material']['name'],
                'Описание материала': result['material']['description'],
                'Категория материала': result['material']['category'],
                'Бренд материала': result['material']['brand'] or '',
                'Модель материала': result['material'].get('model', '') or '',
                'Единица измерения материала': result['material'].get('unit', 'шт'),
                'ID позиции прайса': result['price_item']['id'],
                'Наименование в прайсе': result['price_item']['material_name'],
                'Описание в прайсе': result['price_item']['description'],
                'Цена': result['price_item']['price'],
                'Валюта': result['price_item']['currency'],
                'Поставщик': result['price_item']['supplier'],
                'Категория в прайсе': result['price_item'].get('category', ''),
                'Бренд в прайсе': result['price_item'].get('brand', '') or '',
                'Единица измерения в прайсе': result['price_item'].get('unit', 'шт'),
                'Процент схожести': result['similarity_percentage'],
                'Elasticsearch Score': result['elasticsearch_score']
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