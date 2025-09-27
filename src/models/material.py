from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TypeVar, Generic, Protocol, Final, ClassVar
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import weakref
from functools import lru_cache
import hashlib


@dataclass
class Material:
    """Модель материала для поиска и сопоставления
    
    Структура под новый формат:
    - name: Наименования
    - type_mark: Тип, марка  
    - equipment_code: Код обор.
    - manufacturer: Завод изг.
    - unit: Ед. изм.
    - quantity: Кол-во
    """
    id: str
    name: str  # Наименования
    type_mark: Optional[str] = None  # Тип, марка
    equipment_code: Optional[str] = None  # Код обор.
    manufacturer: Optional[str] = None  # Завод изг.
    unit: Optional[str] = None  # Ед. изм.
    quantity: Optional[float] = None  # Кол-во
    
    # Для обратной совместимости со старым форматом
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для индексации в Elasticsearch"""
        return {
            'id': self.id,
            'name': self.name,
            'type_mark': self.type_mark,
            'equipment_code': self.equipment_code,
            'manufacturer': self.manufacturer,
            'unit': self.unit,
            'quantity': self.quantity,
            # Для обратной совместимости
            'description': self.description,
            'category': self.category,
            'brand': self.brand,
            'model': self.model,
            'specifications': self.specifications or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Поле для полнотекстового поиска
            'full_text': f"{self.name} {self.type_mark or ''} {self.equipment_code or ''} {self.manufacturer or ''} {self.description or ''} {self.brand or ''} {self.category or ''}"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Material':
        """Создание объекта Material из словаря"""
        created_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'])
        
        return cls(
            id=data['id'],
            name=data['name'],
            type_mark=data.get('type_mark'),
            equipment_code=data.get('equipment_code'),
            manufacturer=data.get('manufacturer'),
            unit=data.get('unit'),
            quantity=data.get('quantity'),
            # Для обратной совместимости
            description=data.get('description'),
            category=data.get('category'),
            brand=data.get('brand'),
            model=data.get('model'),
            specifications=data.get('specifications'),
            created_at=created_at
        )


@dataclass
class PriceListItem:
    """Модель элемента прайс-листа
    
    Структура под новый формат:
    - id: идентификатор
    - name: название(материала)
    - brand: бренд(завод производитель)
    - article: артикул
    - brand_code: код бренда
    - cli_code: клиентский код (игнорируется)
    - class: класс (игнорируется)
    - class_code: код класса, важно
    - price: цена
    """
    id: str
    name: str  # название(материала)
    brand: Optional[str] = None  # бренд(завод производитель)
    article: Optional[str] = None  # артикул
    brand_code: Optional[str] = None  # код бренда
    cli_code: Optional[str] = None  # клиентский код (игнорируется)
    material_class: Optional[str] = None  # класс (игнорируется)
    class_code: Optional[str] = None  # код класса, важно
    price: Optional[float] = None  # цена
    
    # Для обратной совместимости со старым форматом
    material_name: Optional[str] = None
    description: Optional[str] = None
    currency: Optional[str] = 'RUB'
    supplier: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'brand': self.brand,
            'article': self.article,
            'brand_code': self.brand_code,
            'cli_code': self.cli_code,
            'material_class': self.material_class,
            'class_code': self.class_code,
            'price': self.price,
            # Для обратной совместимости
            'material_name': self.material_name or self.name,
            'description': self.description,
            'currency': self.currency,
            'supplier': self.supplier,
            'category': self.category,
            'unit': self.unit,
            'specifications': self.specifications or {},
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Поле для полнотекстового поиска
            'full_text': f"{self.name} {self.brand or ''} {self.article or ''} {self.class_code or ''} {self.description or ''} {self.category or ''} {self.supplier or ''}"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceListItem':
        """Создание объекта PriceListItem из словаря"""
        updated_at = None
        if data.get('updated_at'):
            try:
                updated_at = datetime.fromisoformat(data['updated_at'])
            except (ValueError, TypeError):
                updated_at = None
        
        # Определяем цену
        price = None
        if data.get('price') is not None:
            try:
                price = float(data['price'])
            except (ValueError, TypeError):
                price = None
        
        return cls(
            id=str(data.get('id') or ''),  # Используем or для правильной обработки None
            name=data.get('name', data.get('material_name', '')),
            brand=data.get('brand'),
            article=data.get('article'),
            brand_code=data.get('brand_code'),
            cli_code=data.get('cli_code'),
            material_class=data.get('class', data.get('material_class')),
            class_code=data.get('class_code'),
            price=price,
            # Для обратной совместимости
            material_name=data.get('material_name', data.get('name')),
            description=data.get('description'),
            currency=data.get('currency', 'RUB'),
            supplier=data.get('supplier'),
            category=data.get('category'),
            unit=data.get('unit'),
            specifications=data.get('specifications'),
            updated_at=updated_at
        )


@dataclass
class SearchResult:
    """Результат поиска с процентом похожести"""
    material: Material
    price_item: PriceListItem
    similarity_percentage: float
    similarity_details: Dict[str, float]  # Детали сопоставления (название, описание, бренд и т.д.)
    elasticsearch_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для вывода результатов"""
        return {
            'material': self.material.to_dict(),
            'price_item': self.price_item.to_dict(),
            'similarity_percentage': round(self.similarity_percentage, 2),
            'similarity_details': {k: round(v, 2) for k, v in self.similarity_details.items()},
            'elasticsearch_score': round(self.elasticsearch_score, 4)
        }