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
    """Модель материала для поиска и сопоставления"""
    id: str
    name: str
    description: str
    category: str
    brand: Optional[str] = None
    model: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    unit: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для индексации в Elasticsearch"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'brand': self.brand,
            'model': self.model,
            'specifications': self.specifications or {},
            'unit': self.unit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Поле для полнотекстового поиска
            'full_text': f"{self.name} {self.description} {self.brand or ''} {self.model or ''} {self.category}"
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
            description=data['description'],
            category=data['category'],
            brand=data.get('brand'),
            model=data.get('model'),
            specifications=data.get('specifications'),
            unit=data.get('unit'),
            created_at=created_at
        )


@dataclass
class PriceListItem:
    """Модель элемента прайс-листа"""
    id: str
    material_name: str
    description: str
    price: float
    currency: str
    supplier: str
    category: Optional[str] = None
    brand: Optional[str] = None
    unit: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'material_name': self.material_name,
            'description': self.description,
            'price': self.price,
            'currency': self.currency,
            'supplier': self.supplier,
            'category': self.category,
            'brand': self.brand,
            'unit': self.unit,
            'specifications': self.specifications or {},
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Поле для полнотекстового поиска
            'full_text': f"{self.material_name} {self.description} {self.brand or ''} {self.category or ''} {self.supplier}"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceListItem':
        """Создание объекта PriceListItem из словаря"""
        updated_at = None
        if data.get('updated_at'):
            updated_at = datetime.fromisoformat(data['updated_at'])
        
        return cls(
            id=data['id'],
            material_name=data['material_name'],
            description=data['description'],
            price=float(data['price']),
            currency=data['currency'],
            supplier=data['supplier'],
            category=data.get('category'),
            brand=data.get('brand'),
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