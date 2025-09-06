import csv
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
from datetime import datetime

from ..models.material import Material, PriceListItem
from .excel_loader import SmartExcelLoader


class MaterialLoader:
    """Загрузчик материалов из различных источников"""
    
    @staticmethod
    def load_from_csv(file_path: str, encoding: str = 'utf-8') -> List[Material]:
        """Загрузка материалов из CSV файла"""
        materials = []
        
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
        """Загрузка материалов из JSON файла"""
        with open(file_path, 'r', encoding=encoding) as jsonfile:
            data = json.load(jsonfile)
        
        materials = []
        for item in data:
            material = Material.from_dict(item)
            if not material.created_at:
                material.created_at = datetime.now()
            materials.append(material)
        
        return materials


class PriceListLoader:
    """Загрузчик прайс-листов из различных источников"""
    
    @staticmethod
    def load_from_csv(file_path: str, encoding: str = 'utf-8') -> List[PriceListItem]:
        """Загрузка прайс-листа из CSV файла"""
        price_items = []
        
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
        """Загрузка прайс-листа из JSON файла"""
        with open(file_path, 'r', encoding=encoding) as jsonfile:
            data = json.load(jsonfile)
        
        price_items = []
        for item in data:
            price_item = PriceListItem.from_dict(item)
            if not price_item.updated_at:
                price_item.updated_at = datetime.now()
            price_items.append(price_item)
        
        return price_items


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