"""
Исправленный загрузчик данных с поддержкой обоих форматов
"""
import csv
import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import chardet
import pandas as pd

from ..models.material import Material, PriceListItem


logger = logging.getLogger(__name__)


class MaterialLoader:
    """Загрузчик материалов из различных источников"""

    @staticmethod
    def detect_encoding(file_path: str) -> str:
        """Автоопределение кодировки файла"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)
                result = chardet.detect(raw_data)
                detected_encoding = result['encoding']
                confidence = result['confidence']

                logger.info(f"Определена кодировка {detected_encoding} с уверенностью {confidence:.2f}")

                if confidence < 0.7:
                    logger.warning(f"Низкая уверенность в кодировке, используем UTF-8")
                    return 'utf-8'

                if detected_encoding and 'windows-1251' in detected_encoding.lower():
                    return 'windows-1251'
                elif detected_encoding and 'utf-8' in detected_encoding.lower():
                    return 'utf-8'
                else:
                    return detected_encoding or 'utf-8'

        except Exception as e:
            logger.warning(f"Ошибка при определении кодировки: {e}")
            return 'utf-8'

    @staticmethod
    def detect_csv_delimiter(file_path: str, encoding: str) -> str:
        """Автоопределение разделителя CSV файла"""
        try:
            with open(file_path, 'r', encoding=encoding) as csvfile:
                sample = csvfile.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                logger.info(f"Определен разделитель CSV: '{delimiter}'")
                return delimiter
        except Exception as e:
            logger.warning(f"Не удалось автоопределить разделитель: {e}")
            return ','

    @staticmethod
    def load_from_csv(file_path: str, encoding: str = None) -> List[Material]:
        """
        Загрузка материалов из CSV с поддержкой обоих форматов:
        - Старый: id, name, description, category, brand, model
        - Новый: id, name, type_mark, equipment_code, manufacturer
        """
        materials = []

        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)

        delimiter = MaterialLoader.detect_csv_delimiter(file_path, encoding)

        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)

            # Определяем формат по заголовкам
            headers = reader.fieldnames
            is_new_format = 'equipment_code' in headers or 'manufacturer' in headers
            is_old_format = 'brand' in headers or 'model' in headers

            logger.info(f"Формат CSV: {'новый' if is_new_format else 'старый'}")

            for row in reader:
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in row and row['specifications']:
                    try:
                        specifications = json.loads(row['specifications'])
                    except json.JSONDecodeError:
                        specifications = {}

                # ВАЖНО: Мапим старый формат на новый для совместимости
                if is_old_format and not is_new_format:
                    # Старый формат -> адаптируем под новый
                    # УЛУЧШЕНО: Интеллектуальное извлечение кода оборудования
                    equipment_code = row.get('model')

                    # Если нет модели, пробуем извлечь код из названия
                    if not equipment_code and row.get('name'):
                        import re
                        # Ищем паттерны типа ВВГНГ-LS 3x2.5, S201-C16
                        pattern = r'[A-ZА-Я][A-ZА-Я0-9\-\.]+(?:\s*\d+[xх×]?\d*(?:[.,]\d+)?)?'
                        matches = re.findall(pattern, row['name'])
                        # Берем самый информативный match
                        for match in matches:
                            if len(match) > 3:
                                equipment_code = match.strip()
                                break

                    material = Material(
                        id=row.get('id', str(uuid.uuid4())),
                        name=row['name'],
                        # Новые поля из старых
                        type_mark=row.get('model'),  # model -> type_mark
                        equipment_code=equipment_code,  # Улучшенное извлечение
                        manufacturer=row.get('brand'),  # brand -> manufacturer
                        # Старые поля для совместимости
                        description=row.get('description', ''),
                        category=row.get('category', 'Unknown'),
                        brand=row.get('brand'),
                        model=row.get('model'),
                        specifications=specifications,
                        unit=row.get('unit'),
                        created_at=datetime.now()
                    )
                else:
                    # Новый формат или смешанный
                    material = Material(
                        id=row.get('id', str(uuid.uuid4())),
                        name=row['name'],
                        type_mark=row.get('type_mark'),
                        equipment_code=row.get('equipment_code'),
                        manufacturer=row.get('manufacturer'),
                        # Старые поля для совместимости
                        description=row.get('description'),
                        category=row.get('category'),
                        brand=row.get('brand', row.get('manufacturer')),  # brand или manufacturer
                        model=row.get('model', row.get('type_mark')),  # model или type_mark
                        specifications=specifications,
                        unit=row.get('unit'),
                        quantity=float(row['quantity']) if row.get('quantity') else None,
                        created_at=datetime.now()
                    )

                materials.append(material)

        logger.info(f"Загружено {len(materials)} материалов")
        return materials


class PriceListLoader:
    """Загрузчик прайс-листов"""

    @staticmethod
    def load_from_csv(file_path: str, encoding: str = None) -> List[PriceListItem]:
        """
        Загрузка прайс-листа из CSV с поддержкой обоих форматов:
        - Старый: material_name, description, price, brand
        - Новый: name, brand, article, class_code
        """
        price_items = []

        if encoding is None:
            encoding = MaterialLoader.detect_encoding(file_path)

        delimiter = MaterialLoader.detect_csv_delimiter(file_path, encoding)

        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)

            # Определяем формат
            headers = reader.fieldnames
            is_new_format = 'article' in headers or 'class_code' in headers
            is_old_format = 'material_name' in headers

            logger.info(f"Формат прайс-листа: {'новый' if is_new_format else 'старый'}")

            for idx, row in enumerate(reader):
                # Обработка спецификаций
                specifications = {}
                if 'specifications' in row and row['specifications']:
                    try:
                        specifications = json.loads(row['specifications'])
                    except json.JSONDecodeError:
                        specifications = {}

                # Определяем цену
                price = None
                if row.get('price'):
                    try:
                        price = float(row['price'])
                    except (ValueError, TypeError):
                        price = None

                # ВАЖНО: Мапим старый формат на новый
                if is_old_format:
                    # Старый формат -> адаптируем
                    # УЛУЧШЕНО: Извлекаем артикул из разных источников
                    article = None

                    # 1. Пробуем из спецификаций
                    if specifications.get('model'):
                        article = specifications.get('model')
                    elif specifications.get('article'):
                        article = specifications.get('article')
                    elif specifications.get('code'):
                        article = specifications.get('code')

                    # 2. Пробуем извлечь из названия (например, "S201-C16" из "Автомат защиты S201-C16 ABB")
                    if not article and row.get('material_name'):
                        import re
                        # Ищем паттерны типа S201-C16, ЩРН-12, ВВГНГ-LS
                        pattern = r'[A-ZА-Я][A-ZА-Я0-9\-\.]+(?:\d+[A-ZА-Я]*)?'
                        matches = re.findall(pattern, row['material_name'])
                        # Берем самый длинный match который выглядит как артикул
                        for match in sorted(matches, key=len, reverse=True):
                            if len(match) > 3 and any(c.isdigit() for c in match):
                                article = match
                                break

                    # 3. Если все еще нет артикула, не создаем фейковый
                    # Лучше оставить None чем создавать "Brand-0"

                    price_item = PriceListItem(
                        id=row.get('id', str(uuid.uuid4())),
                        # Новые поля
                        name=row.get('material_name', ''),
                        brand=row.get('brand'),
                        article=article,  # Генерируем артикул
                        class_code=row.get('category'),  # category как class_code
                        price=price,
                        # Старые поля для совместимости
                        material_name=row.get('material_name'),
                        description=row.get('description'),
                        currency=row.get('currency', 'RUB'),
                        supplier=row.get('supplier'),
                        category=row.get('category'),
                        unit=row.get('unit'),
                        specifications=specifications,
                        updated_at=datetime.now()
                    )
                else:
                    # Новый формат
                    price_item = PriceListItem(
                        id=row.get('id', str(uuid.uuid4())),
                        name=row.get('name', row.get('material_name', '')),
                        brand=row.get('brand'),
                        article=row.get('article'),
                        brand_code=row.get('brand_code'),
                        cli_code=row.get('cli_code'),
                        material_class=row.get('class'),
                        class_code=row.get('class_code'),
                        price=price,
                        # Старые поля
                        material_name=row.get('material_name', row.get('name')),
                        description=row.get('description'),
                        currency=row.get('currency', 'RUB'),
                        supplier=row.get('supplier'),
                        category=row.get('category'),
                        unit=row.get('unit'),
                        specifications=specifications,
                        updated_at=datetime.now()
                    )

                price_items.append(price_item)

        logger.info(f"Загружено {len(price_items)} позиций прайс-листа")
        return price_items