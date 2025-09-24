#!/usr/bin/env python3
"""
Универсальный загрузчик Excel файлов с автоматическим определением структуры
"""

import pandas as pd
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import re

from ..models.material import Material, PriceListItem


class SmartExcelLoader:
    """Умный загрузчик Excel файлов с автоопределением колонок"""
    
    # Возможные названия колонок для материалов
    MATERIAL_NAME_COLUMNS = [
        'наименование', 'название', 'материал', 'name', 'material', 
        'material_name', 'наименование материала', 'item', 'товар',
        'продукт', 'product', 'артикул', 'номенклатура'
    ]
    
    DESCRIPTION_COLUMNS = [
        'описание', 'description', 'характеристика', 'комментарий',
        'примечание', 'comment', 'note', 'спецификация', 'тех.характеристики'
    ]
    
    CATEGORY_COLUMNS = [
        'категория', 'category', 'тип', 'type', 'группа', 'group',
        'раздел', 'класс', 'вид', 'classification'
    ]
    
    BRAND_COLUMNS = [
        'бренд', 'brand', 'производитель', 'изготовитель', 'manufacturer',
        'vendor', 'марка', 'фирма', 'поставщик производителя'
    ]
    
    MODEL_COLUMNS = [
        'модель', 'model', 'артикул', 'article', 'код', 'code',
        'sku', 'part_number', 'код товара', 'код изготовителя'
    ]
    
    UNIT_COLUMNS = [
        'ед.изм', 'единица', 'unit', 'ед', 'единица измерения',
        'units', 'uom', 'ед изм', 'measure'
    ]
    
    PRICE_COLUMNS = [
        'цена', 'price', 'стоимость', 'cost', 'тариф', 'расценка',
        'цена за единицу', 'unit_price', 'прайс'
    ]
    
    SUPPLIER_COLUMNS = [
        'поставщик', 'supplier', 'vendor', 'продавец', 'дилер',
        'компания', 'company', 'организация', 'контрагент'
    ]
    
    ID_COLUMNS = [
        'id', 'код', 'номер', 'артикул', 'sku', '№', 'number',
        'item_id', 'product_id', 'код товара', 'идентификатор'
    ]

    # ДОБАВЛЕНО: Поддержка equipment_code
    EQUIPMENT_CODE_COLUMNS = [
        'код обор', 'код обор.', 'код оборудования', 'equipment_code',
        'equipment', 'оборудование', 'код оборудования', 'код оборудование'
    ]
    
    def __init__(self):
        """Инициализация загрузчика"""
        self.column_mapping = {}
        self.detected_type = None  # 'materials' или 'pricelist'
        
    def detect_file_type(self, df: pd.DataFrame) -> str:
        """
        Определение типа файла (материалы или прайс-лист)
        
        Args:
            df: DataFrame с данными
            
        Returns:
            'materials' или 'pricelist'
        """
        columns_lower = [col.lower() for col in df.columns]
        original_columns = list(df.columns)
        
        # Признаки прайс-листа
        price_indicators = any([
            self._find_column(columns_lower, self.PRICE_COLUMNS, original_columns),
            self._find_column(columns_lower, self.SUPPLIER_COLUMNS, original_columns)
        ])
        
        # Если есть цены или поставщики - это прайс-лист
        if price_indicators:
            return 'pricelist'
        
        # Иначе считаем материалами
        return 'materials'
    
    def _find_column(self, columns: List[str], patterns: List[str], original_columns: List[str] = None) -> Optional[str]:
        """
        Поиск колонки по списку возможных названий
        
        Args:
            columns: Список названий колонок (в нижнем регистре)
            patterns: Список возможных паттернов
            original_columns: Оригинальные названия колонок (если нет, используется self.df.columns)
            
        Returns:
            Название найденной колонки или None
        """
        if original_columns is None and hasattr(self, 'df'):
            original_columns = list(self.df.columns)
        elif original_columns is None:
            return None
            
        for col in columns:
            col_clean = col.strip()
            for pattern in patterns:
                if pattern.lower() in col_clean or col_clean in pattern.lower():
                    # Возвращаем оригинальное название колонки
                    original_idx = columns.index(col)
                    return original_columns[original_idx]
        return None
    
    def analyze_structure(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Анализ структуры DataFrame и определение соответствия колонок
        
        Args:
            df: DataFrame для анализа
            
        Returns:
            Словарь соответствия назначений колонкам
        """
        self.df = df
        columns_lower = [col.lower() for col in df.columns]
        mapping = {}
        
        # Определяем тип файла
        self.detected_type = self.detect_file_type(df)
        
        # Ищем основные колонки
        mapping['id'] = self._find_column(columns_lower, self.ID_COLUMNS)
        mapping['name'] = self._find_column(columns_lower, self.MATERIAL_NAME_COLUMNS)
        mapping['description'] = self._find_column(columns_lower, self.DESCRIPTION_COLUMNS)
        mapping['category'] = self._find_column(columns_lower, self.CATEGORY_COLUMNS)
        mapping['brand'] = self._find_column(columns_lower, self.BRAND_COLUMNS)
        mapping['model'] = self._find_column(columns_lower, self.MODEL_COLUMNS)
        mapping['unit'] = self._find_column(columns_lower, self.UNIT_COLUMNS)
        mapping['equipment_code'] = self._find_column(columns_lower, self.EQUIPMENT_CODE_COLUMNS)  # ДОБАВЛЕНО
        
        # Для прайс-листа ищем дополнительные колонки
        if self.detected_type == 'pricelist':
            mapping['price'] = self._find_column(columns_lower, self.PRICE_COLUMNS)
            mapping['supplier'] = self._find_column(columns_lower, self.SUPPLIER_COLUMNS)
        
        # Если не нашли название материала, берем первую текстовую колонку
        if not mapping['name']:
            for col in df.columns:
                if df[col].dtype == 'object':
                    mapping['name'] = col
                    break
        
        # Если нет ID, используем индекс
        if not mapping['id']:
            mapping['id'] = None  # Будем генерировать
        
        self.column_mapping = mapping
        return mapping
    
    def load_materials_from_excel(self, file_path: str, sheet_name: Optional[str] = None) -> List[Material]:
        """
        Загрузка материалов из Excel с автоопределением колонок
        
        Args:
            file_path: Путь к файлу
            sheet_name: Название листа (если None - первый лист)
            
        Returns:
            Список материалов
        """
        # Читаем файл
        if sheet_name is None:
            # Берем первый лист
            df = pd.read_excel(file_path, sheet_name=0)
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Анализируем структуру
        self.analyze_structure(df)
        
        if not self.column_mapping.get('name'):
            raise ValueError("Не удалось определить колонку с названием материала")
        
        materials = []
        
        for idx, row in df.iterrows():
            # Получаем значения из правильных колонок
            material_id = str(row[self.column_mapping['id']]) if self.column_mapping['id'] else str(idx + 1)
            name = str(row[self.column_mapping['name']]).strip() if pd.notna(row[self.column_mapping['name']]) else ''
            
            # Пропускаем пустые строки
            if not name or name == 'nan':
                continue
            
            # Получаем остальные поля если они есть
            description = ''
            if self.column_mapping.get('description'):
                desc_val = row[self.column_mapping['description']]
                description = str(desc_val).strip() if pd.notna(desc_val) else name
            else:
                description = name
            
            category = 'Общая'
            if self.column_mapping.get('category'):
                cat_val = row[self.column_mapping['category']]
                category = str(cat_val).strip() if pd.notna(cat_val) else 'Общая'
            
            brand = None
            if self.column_mapping.get('brand'):
                brand_val = row[self.column_mapping['brand']]
                brand = str(brand_val).strip() if pd.notna(brand_val) and str(brand_val) != 'nan' else None
            
            model = None
            if self.column_mapping.get('model'):
                model_val = row[self.column_mapping['model']]
                model = str(model_val).strip() if pd.notna(model_val) and str(model_val) != 'nan' else None

            unit = 'шт'
            if self.column_mapping.get('unit'):
                unit_val = row[self.column_mapping['unit']]
                unit = str(unit_val).strip() if pd.notna(unit_val) and str(unit_val) != 'nan' else 'шт'

            # ДОБАВЛЕНО: Обработка equipment_code
            equipment_code = None
            if self.column_mapping.get('equipment_code'):
                eq_val = row[self.column_mapping['equipment_code']]
                equipment_code = str(eq_val).strip() if pd.notna(eq_val) and str(eq_val) != 'nan' else None

            # Собираем спецификации из дополнительных колонок
            specifications = {}
            for col in df.columns:
                if col not in self.column_mapping.values():
                    val = row[col]
                    if pd.notna(val) and str(val) != 'nan':
                        specifications[col] = str(val)
            
            material = Material(
                id=material_id,
                name=name,
                description=description,
                category=category,
                brand=brand,
                model=model,
                equipment_code=equipment_code,  # ДОБАВЛЕНО: equipment_code
                specifications=specifications,
                unit=unit,
                created_at=datetime.now()
            )
            
            materials.append(material)
        
        return materials
    
    def load_pricelist_from_excel(self, file_path: str, sheet_name: Optional[str] = None) -> List[PriceListItem]:
        """
        Загрузка прайс-листа из Excel с автоопределением колонок
        
        Args:
            file_path: Путь к файлу
            sheet_name: Название листа (если None - первый лист)
            
        Returns:
            Список позиций прайс-листа
        """
        # Читаем файл
        if sheet_name is None:
            # Берем первый лист
            df = pd.read_excel(file_path, sheet_name=0)
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Анализируем структуру
        self.analyze_structure(df)
        
        if not self.column_mapping.get('name'):
            raise ValueError("Не удалось определить колонку с названием товара")
        
        price_items = []
        
        for idx, row in df.iterrows():
            # Получаем значения из правильных колонок
            item_id = str(row[self.column_mapping['id']]) if self.column_mapping['id'] else str(idx + 1)
            name = str(row[self.column_mapping['name']]).strip() if pd.notna(row[self.column_mapping['name']]) else ''
            
            # Пропускаем пустые строки
            if not name or name == 'nan':
                continue
            
            # Получаем остальные поля
            description = ''
            if self.column_mapping.get('description'):
                desc_val = row[self.column_mapping['description']]
                description = str(desc_val).strip() if pd.notna(desc_val) else name
            else:
                description = name
            
            # Цена
            price = 0.0
            if self.column_mapping.get('price'):
                price_val = row[self.column_mapping['price']]
                if pd.notna(price_val):
                    try:
                        # Убираем возможные символы валюты и пробелы
                        price_str = str(price_val).replace('₽', '').replace('руб', '').replace(' ', '').replace(',', '.')
                        price = float(price_str)
                    except:
                        price = 0.0
            
            # Поставщик
            supplier = 'Не указан'
            if self.column_mapping.get('supplier'):
                supp_val = row[self.column_mapping['supplier']]
                supplier = str(supp_val).strip() if pd.notna(supp_val) and str(supp_val) != 'nan' else 'Не указан'
            
            # Категория
            category = 'Общая'
            if self.column_mapping.get('category'):
                cat_val = row[self.column_mapping['category']]
                category = str(cat_val).strip() if pd.notna(cat_val) else 'Общая'
            
            # Бренд
            brand = None
            if self.column_mapping.get('brand'):
                brand_val = row[self.column_mapping['brand']]
                brand = str(brand_val).strip() if pd.notna(brand_val) and str(brand_val) != 'nan' else None
            
            # Единица измерения
            unit = 'шт'
            if self.column_mapping.get('unit'):
                unit_val = row[self.column_mapping['unit']]
                unit = str(unit_val).strip() if pd.notna(unit_val) and str(unit_val) != 'nan' else 'шт'
            
            # Собираем спецификации из дополнительных колонок
            specifications = {}
            for col in df.columns:
                if col not in self.column_mapping.values():
                    val = row[col]
                    if pd.notna(val) and str(val) != 'nan':
                        specifications[col] = str(val)
            
            price_item = PriceListItem(
                id=item_id,
                material_name=name,
                description=description,
                price=price,
                currency='RUB',
                supplier=supplier,
                category=category,
                brand=brand,
                unit=unit,
                specifications=specifications,
                updated_at=datetime.now()
            )
            
            price_items.append(price_item)
        
        return price_items
    
    def get_structure_info(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение информации о структуре файла
        
        Args:
            file_path: Путь к файлу
            sheet_name: Название листа
            
        Returns:
            Информация о структуре файла
        """
        # Читаем файл
        if sheet_name is None:
            # Берем первый лист
            df = pd.read_excel(file_path, sheet_name=0)
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        self.analyze_structure(df)
        
        return {
            'detected_type': self.detected_type,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': list(df.columns),
            'column_mapping': self.column_mapping,
            'sample_data': df.head(3).to_dict(orient='records')
        }