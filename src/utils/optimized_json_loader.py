#!/usr/bin/env python3
"""
Оптимизированный загрузчик JSON файлов с потоковой обработкой
Поддерживает обработку больших файлов с минимальным использованием памяти
"""

import json
import ijson
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
import time
from datetime import datetime
import logging

from ..models.material import Material, PriceListItem

logger = logging.getLogger(__name__)


class OptimizedJSONLoader:
    """Оптимизированный загрузчик JSON с потоковой обработкой"""

    def __init__(self, chunk_size: int = 10000):
        """
        Инициализация загрузчика

        Args:
            chunk_size: Размер чанка для обработки
        """
        self.chunk_size = chunk_size

    def load_price_list_from_json(self,
                                 file_path: str,
                                 encoding: str = 'utf-8',
                                 progress_callback: Optional[Callable] = None) -> List[PriceListItem]:
        """
        Загрузка прайс-листа из JSON с потоковой обработкой

        Args:
            file_path: Путь к JSON файлу
            encoding: Кодировка файла
            progress_callback: Функция для отображения прогресса

        Returns:
            Список элементов прайс-листа
        """
        print(f"[INFO] Запуск оптимизированного загрузчика JSON для {file_path}")
        start_time = time.time()

        price_items = []
        processed_count = 0

        try:
            with open(file_path, 'rb') as file:
                # Используем ijson для потоковой обработки
                parser = ijson.parse(file)
                current_item = {}
                in_array = False
                current_key = None

                for prefix, event, value in parser:
                    if prefix == '' and event == 'start_array':
                        in_array = True
                        continue
                    elif prefix == '' and event == 'end_array':
                        break
                    elif in_array and event == 'start_map':
                        current_item = {}
                    elif in_array and event == 'end_map':
                        # Обрабатываем завершенный элемент
                        if current_item:
                            price_item = self._convert_to_price_item(current_item)
                            if price_item:
                                price_items.append(price_item)
                                processed_count += 1

                                # Обновляем прогресс
                                if progress_callback and processed_count % self.chunk_size == 0:
                                    elapsed = time.time() - start_time
                                    progress_callback(processed_count, None, f"{elapsed:.2f}сек")

                        current_item = {}
                    elif in_array and event in ('string', 'number', 'boolean', 'null'):
                        # Получаем ключ из prefix
                        if '.' in prefix:
                            key = prefix.split('.')[-1]
                            current_item[key] = value

        except Exception as e:
            logger.error(f"Ошибка при потоковой обработке JSON: {e}")
            # Fallback на стандартную загрузку
            return self._load_standard_json(file_path, encoding, progress_callback)

        elapsed_time = time.time() - start_time
        print(f"[OK] Оптимизированная загрузка завершена: {processed_count} записей за {elapsed_time:.2f} секунд")

        return price_items

    def _load_standard_json(self,
                           file_path: str,
                           encoding: str,
                           progress_callback: Optional[Callable] = None) -> List[PriceListItem]:
        """Стандартная загрузка JSON как fallback"""
        print(f"[INFO] Использование стандартной загрузки JSON")
        start_time = time.time()

        with open(file_path, 'r', encoding=encoding) as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("[ERROR] JSON файл должен содержать массив объектов")
            return []

        price_items = []
        total_items = len(data)

        for i, item in enumerate(data):
            price_item = self._convert_to_price_item(item)
            if price_item:
                price_items.append(price_item)

            # Обновляем прогресс
            if progress_callback and (i + 1) % self.chunk_size == 0:
                elapsed = time.time() - start_time
                progress_callback(i + 1, total_items, f"{elapsed:.2f}сек")

        elapsed_time = time.time() - start_time
        print(f"[OK] Стандартная загрузка завершена: {len(price_items)} записей за {elapsed_time:.2f} секунд")

        return price_items

    def _convert_to_price_item(self, item: Dict[str, Any]) -> Optional[PriceListItem]:
        """
        Конвертация словаря в PriceListItem с гибким маппингом полей

        Args:
            item: Словарь с данными элемента

        Returns:
            PriceListItem или None если данные некорректны
        """
        try:
            # Применяем гибкий маппинг полей
            mapped_item = self._auto_map_fields(item)

            # Проверяем обязательные поля
            name = mapped_item.get('name') or mapped_item.get('material_name', '')
            if not name:
                return None

            # Создаем PriceListItem
            price_item = PriceListItem(
                id=str(mapped_item.get('id', '')),
                name=name,
                brand=mapped_item.get('brand', ''),
                article=mapped_item.get('article', ''),
                brand_code=mapped_item.get('brand_code', ''),
                cli_code=mapped_item.get('cli_code', ''),
                material_class=mapped_item.get('material_class', ''),
                class_code=mapped_item.get('class_code', ''),
                price=float(mapped_item.get('price', 0.0)),
                material_name=mapped_item.get('material_name', name),
                description=mapped_item.get('description', ''),
                currency=mapped_item.get('currency', 'RUB'),
                supplier=mapped_item.get('supplier', ''),
                category=mapped_item.get('category'),
                unit=mapped_item.get('unit'),
                specifications=mapped_item.get('specifications', {}),
                updated_at=datetime.now().isoformat()
            )

            return price_item

        except Exception as e:
            logger.warning(f"Ошибка конвертации элемента: {e}")
            return None

    def _auto_map_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Автоматический маппинг полей из различных вариантов названий

        Args:
            item: Исходный словарь

        Returns:
            Словарь с стандартизированными названиями полей
        """
        # Возможные варианты названий полей
        field_mappings = {
            'name': ['name', 'material_name', 'title', 'наименование', 'наименования', 'название'],
            'description': ['description', 'desc', 'details', 'описание', 'детали'],
            'category': ['category', 'class', 'type', 'категория', 'класс', 'тип'],
            'brand': ['brand', 'бренд'],
            'manufacturer': ['manufacturer', 'производитель', 'завод производитель', 'завод изг', 'завод изг.'],
            'article': ['article', 'артикул', 'код'],
            'brand_code': ['brand_code', 'код_бренда', 'код бренда'],
            'cli_code': ['cli_code', 'client_code', 'клиентский_код', 'клиентский код'],
            'material_class': ['class', 'material_class', 'класс', 'класс материала'],
            'class_code': ['class_code', 'код_класса', 'код класса'],
            'price': ['price', 'cost', 'цена', 'стоимость'],
            'currency': ['currency', 'валюта'],
            'supplier': ['supplier', 'vendor', 'поставщик', 'продавец'],
            'material_name': ['material_name', 'name', 'title', 'наименование', 'название'],
            'id': ['id', 'item_id', '_id']
        }

        mapped_item = {}

        # Приводим ключи к нижнему регистру для поиска
        item_lower = {k.lower(): v for k, v in item.items()}

        for target_field, possible_names in field_mappings.items():
            value = None
            for possible_name in possible_names:
                if possible_name.lower() in item_lower:
                    value = item_lower[possible_name.lower()]
                    break

            if value is not None:
                mapped_item[target_field] = value
            else:
                # Ищем частичные совпадения для сложных полей
                for key, val in item_lower.items():
                    if any(pn in key for pn in possible_names):
                        mapped_item[target_field] = val
                        break

        # Добавляем оригинальные поля если они не были замаплены
        for key, value in item.items():
            if key.lower() not in [k.lower() for k in mapped_item.keys()]:
                mapped_item[key] = value

        return mapped_item

    def load_materials_from_json(self,
                               file_path: str,
                               encoding: str = 'utf-8',
                               progress_callback: Optional[Callable] = None) -> List[Material]:
        """
        Загрузка материалов из JSON (аналогично для прайс-листов, но возвращает Material)

        Args:
            file_path: Путь к JSON файлу
            encoding: Кодировка файла
            progress_callback: Функция для отображения прогресса

        Returns:
            Список материалов
        """
        # Можно реализовать аналогично, но пока используем простую загрузку
        with open(file_path, 'r', encoding=encoding) as file:
            data = json.load(file)

        materials = []
        total_items = len(data) if isinstance(data, list) else 0

        if isinstance(data, list):
            for i, item in enumerate(data):
                material = self._convert_to_material(item)
                if material:
                    materials.append(material)

                if progress_callback and (i + 1) % self.chunk_size == 0:
                    progress_callback(i + 1, total_items)

        return materials

    def _convert_to_material(self, item: Dict[str, Any]) -> Optional[Material]:
        """Конвертация словаря в Material"""
        try:
            mapped_item = self._auto_map_fields(item)

            name = mapped_item.get('name', '')
            if not name:
                return None

            return Material(
                id=str(mapped_item.get('id', '')),
                name=name,
                description=mapped_item.get('description', ''),
                category=mapped_item.get('category', ''),
                brand=mapped_item.get('brand', ''),
                manufacturer=mapped_item.get('manufacturer', ''),
                equipment_code=mapped_item.get('equipment_code', ''),
                type_mark=mapped_item.get('type_mark', ''),
                model=mapped_item.get('model', ''),
                unit=mapped_item.get('unit', ''),
                quantity=float(mapped_item.get('quantity', 0.0))
            )
        except Exception as e:
            logger.warning(f"Ошибка конвертации материала: {e}")
            return None


def create_progress_reporter(update_interval: int = 10000) -> Callable:
    """
    Создает функцию для отображения прогресса

    Args:
        update_interval: Интервал обновления в количестве записей

    Returns:
        Функция обратного вызова для прогресса
    """
    def progress_callback(current: int, total: Optional[int] = None, message: str = ""):
        if current % update_interval == 0:
            if total:
                percentage = (current / total) * 100
                print(f"[INFO] Обработано {current}/{total} записей ({percentage:.1f}%) - {message}")
            else:
                print(f"[INFO] Обработано {current} записей - {message}")

    return progress_callback


# Установка ijson если не установлен
try:
    import ijson
except ImportError:
    print("[WARNING] ijson не установлен. Установите командой: pip install ijson")
    print("[INFO] Будет использоваться стандартная загрузка JSON")