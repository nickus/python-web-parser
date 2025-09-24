"""
Оптимизированные модели данных для системы сопоставления материалов.

Эта версия включает:
- Строгую типизацию с использованием современных возможностей Python
- Memory-efficient структуры с slots и frozen dataclasses
- Кеширование для оптимизации производительности
- Валидацию данных и безопасные конструкторы
- Архитектурные паттерны (Protocols, Factory patterns)
- Enum-based категории для type safety
- Weak references для управления памятью
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import (
    Optional, Dict, Any, TypeVar, Generic, Protocol, Final, ClassVar,
    List, Union, Tuple, Set
)
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import weakref
from functools import lru_cache, cached_property
import hashlib
import time
from decimal import Decimal, ROUND_HALF_UP

# Type definitions для лучшей type safety
TMaterialId = TypeVar('TMaterialId', bound=str)
TSpecValue = TypeVar('TSpecValue', bound=Any)


class MaterialCategory(Enum):
    """Enum для категорий материалов с валидацией"""
    ELECTRICAL = "electrical"
    CABLES = "cables"
    LIGHTING = "lighting"
    SWITCHES = "switches"
    AUTOMATION = "automation"
    GENERAL = "general"
    
    @classmethod
    def from_string(cls, value: str) -> MaterialCategory:
        """Безопасное преобразование строки в категорию"""
        if not value:
            return cls.GENERAL
            
        normalized = value.lower().strip()
        mapping = {
            'кабель': cls.CABLES,
            'провод': cls.CABLES,
            'светильник': cls.LIGHTING,
            'лампа': cls.LIGHTING,
            'выключатель': cls.SWITCHES,
            'автомат': cls.AUTOMATION,
            'электрик': cls.ELECTRICAL,
        }
        return mapping.get(normalized, cls.GENERAL)
    
    def localized_name(self) -> str:
        """Локализованное название категории"""
        names = {
            self.ELECTRICAL: "Электрооборудование",
            self.CABLES: "Кабели и провода", 
            self.LIGHTING: "Освещение",
            self.SWITCHES: "Выключатели",
            self.AUTOMATION: "Автоматика",
            self.GENERAL: "Общее",
        }
        return names[self]


class Currency(Enum):
    """Enum для валют с нормализацией"""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    
    @classmethod
    def from_string(cls, value: str) -> Currency:
        """Безопасное преобразование строки в валюту"""
        normalized = value.upper().strip()
        mapping = {
            'РУБ': cls.RUB,
            'РУБЛЬ': cls.RUB,
            'РУБ.': cls.RUB,
            'RUR': cls.RUB,
            '$': cls.USD,
            'ДОЛЛАР': cls.USD,
            '€': cls.EUR,
            'ЕВРО': cls.EUR,
        }
        return mapping.get(normalized, cls.RUB)


class Cacheable(Protocol):
    """Протокол для кешируемых объектов"""
    def get_cache_key(self) -> str: ...
    def invalidate_cache(self) -> None: ...


class Serializable(Protocol):
    """Протокол для сериализуемых объектов"""
    def to_dict(self) -> Dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Serializable: ...


class Validatable(Protocol):
    """Протокол для валидируемых объектов"""
    def validate(self) -> bool: ...
    def get_validation_errors(self) -> List[str]: ...


@dataclass(frozen=True, slots=True)  # Immutable и memory-efficient
class OptimizedMaterial(Cacheable, Serializable, Validatable):
    """
    Оптимизированная модель материала с типобезопасностью и кешированием
    
    Использует slots для экономии памяти, frozen для immutability,
    и lru_cache для оптимизации повторных вычислений.
    """
    
    # Core fields with strict typing
    id: Final[str]  # Immutable ID
    name: str
    description: str
    category: MaterialCategory
    
    # Optional fields with defaults
    brand: Optional[str] = None
    model: Optional[str] = None
    specifications: Dict[str, Any] = field(default_factory=dict)
    unit: Optional[str] = None
    created_at: Optional[datetime] = field(default_factory=lambda: datetime.now())
    
    # Metadata для оптимизации
    _hash_cache: Optional[int] = field(default=None, init=False, compare=False)
    
    # Class-level cache для performance
    _cache: ClassVar[weakref.WeakValueDictionary] = weakref.WeakValueDictionary()
    
    def __post_init__(self) -> None:
        """Валидация и нормализация данных после инициализации"""
        errors = self.get_validation_errors()
        if errors:
            raise ValueError(f"Material validation failed: {', '.join(errors)}")
        
        # Нормализуем строковые поля
        object.__setattr__(self, 'name', self.name.strip())
        object.__setattr__(self, 'description', self.description.strip())
        
        # Кешируем хеш для быстрого поиска
        object.__setattr__(self, '_hash_cache', self._compute_hash())
    
    def validate(self) -> bool:
        """Проверка валидности материала"""
        return len(self.get_validation_errors()) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Получение списка ошибок валидации"""
        errors = []
        
        if not self.id or len(self.id.strip()) == 0:
            errors.append("Material ID cannot be empty")
        
        if not self.name or len(self.name.strip()) == 0:
            errors.append("Material name cannot be empty")
        
        if not self.description:
            errors.append("Material description cannot be empty")
        
        if not isinstance(self.category, MaterialCategory):
            errors.append("Invalid category type")
        
        return errors
    
    @lru_cache(maxsize=128)
    def get_cache_key(self) -> str:
        """Генерация ключа кеша для оптимизации"""
        content = f"{self.id}:{self.name}:{self.category.value}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def invalidate_cache(self) -> None:
        """Очистка кеша для данного объекта"""
        self.get_cache_key.cache_clear()
        self.get_full_text.cache_clear()
        self.get_search_tokens.cache_clear()
    
    @lru_cache(maxsize=64)
    def get_full_text(self) -> str:
        """Кешированное получение полного текста для поиска"""
        parts = [self.name, self.description]
        
        if self.brand:
            parts.append(self.brand)
        if self.model:
            parts.append(self.model)
        
        parts.append(self.category.value)
        
        # Добавляем спецификации
        if self.specifications:
            spec_text = ' '.join(str(v) for v in self.specifications.values() if v)
            parts.append(spec_text)
        
        return ' '.join(filter(None, parts))
    
    @lru_cache(maxsize=32)
    def get_search_tokens(self) -> Set[str]:
        """Кешированные поисковые токены для быстрого поиска"""
        text = self.get_full_text().lower()
        # Простая токенизация - можно заменить на более сложную
        tokens = set(text.split())
        return tokens
    
    @cached_property
    def category_name(self) -> str:
        """Человекочитаемое название категории"""
        return self.category.localized_name()
    
    @cached_property  
    def display_name(self) -> str:
        """Отображаемое имя с дополнительной информацией"""
        parts = [self.name]
        if self.brand:
            parts.append(f"({self.brand})")
        if self.model:
            parts.append(f"Модель: {self.model}")
        return ' '.join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Оптимизированное преобразование в словарь с кешированием"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category.value,
            'brand': self.brand,
            'model': self.model,
            'specifications': self.specifications,
            'unit': self.unit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'full_text': self.get_full_text(),  # Используем кешированную версию
            'display_name': self.display_name,
            'category_localized': self.category_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizedMaterial:
        """Типобезопасное создание из словаря с валидацией"""
        
        # Валидация обязательных полей
        required_fields = ['id', 'name', 'description', 'category']
        for field_name in required_fields:
            if field_name not in data or data[field_name] is None:
                raise ValueError(f"Missing required field: {field_name}")
        
        # Парсинг даты
        created_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                try:
                    created_at = datetime.fromisoformat(data['created_at'])
                except ValueError:
                    # Fallback для других форматов даты
                    created_at = datetime.now()
            elif isinstance(data['created_at'], datetime):
                created_at = data['created_at']
        
        # Парсинг категории
        category = data['category']
        if isinstance(category, str):
            category = MaterialCategory.from_string(category)
        elif not isinstance(category, MaterialCategory):
            category = MaterialCategory.GENERAL
        
        return cls(
            id=str(data['id']),
            name=str(data['name']),
            description=str(data['description']),
            category=category,
            brand=data.get('brand'),
            model=data.get('model'),
            specifications=data.get('specifications', {}),
            unit=data.get('unit'),
            created_at=created_at
        )
    
    def _compute_hash(self) -> int:
        """Вычисление хеша для оптимизации"""
        return hash((self.id, self.name, self.category))
    
    def __hash__(self) -> int:
        """Хеш для использования в set/dict"""
        return self._hash_cache if self._hash_cache is not None else self._compute_hash()
    
    def __eq__(self, other: object) -> bool:
        """Сравнение материалов"""
        if not isinstance(other, OptimizedMaterial):
            return NotImplemented
        return self.id == other.id and self.name == other.name
    
    def __repr__(self) -> str:
        return f"OptimizedMaterial(id='{self.id}', name='{self.name}', category={self.category.value})"


@dataclass(frozen=True, slots=True)  
class OptimizedPriceListItem(Cacheable, Serializable, Validatable):
    """
    Оптимизированная модель элемента прайс-листа с типобезопасностью
    
    Включает валидацию цены, нормализацию валют и кешированную сериализацию.
    """
    
    # Core fields
    id: Final[str]
    material_name: str
    description: str
    price: Decimal  # Используем Decimal для точности цен
    currency: Currency
    supplier: str
    
    # Optional fields
    category: Optional[MaterialCategory] = None
    brand: Optional[str] = None
    unit: Optional[str] = None
    specifications: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[datetime] = field(default_factory=lambda: datetime.now())
    
    # Metadata
    _hash_cache: Optional[int] = field(default=None, init=False, compare=False)
    
    # Кеш для производительности
    _cache: ClassVar[weakref.WeakValueDictionary] = weakref.WeakValueDictionary()
    
    def __post_init__(self) -> None:
        """Валидация после инициализации"""
        errors = self.get_validation_errors()
        if errors:
            raise ValueError(f"PriceListItem validation failed: {', '.join(errors)}")
        
        # Нормализуем строковые поля
        object.__setattr__(self, 'material_name', self.material_name.strip())
        object.__setattr__(self, 'description', self.description.strip())
        object.__setattr__(self, 'supplier', self.supplier.strip())
        
        # Кешируем хеш
        object.__setattr__(self, '_hash_cache', self._compute_hash())
    
    def validate(self) -> bool:
        """Проверка валидности элемента прайс-листа"""
        return len(self.get_validation_errors()) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Список ошибок валидации"""
        errors = []
        
        if not self.id or len(self.id.strip()) == 0:
            errors.append("PriceListItem ID cannot be empty")
        
        if not self.material_name or len(self.material_name.strip()) == 0:
            errors.append("Material name cannot be empty")
        
        if self.price < 0:
            errors.append(f"Price cannot be negative: {self.price}")
        
        if not isinstance(self.currency, Currency):
            errors.append("Invalid currency type")
        
        if not self.supplier or len(self.supplier.strip()) == 0:
            errors.append("Supplier cannot be empty")
        
        return errors
    
    @lru_cache(maxsize=128)
    def get_cache_key(self) -> str:
        """Ключ кеша для оптимизации"""
        content = f"{self.id}:{self.material_name}:{self.supplier}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def invalidate_cache(self) -> None:
        """Очистка кеша"""
        self.get_cache_key.cache_clear()
        self.get_full_text.cache_clear()
        self.formatted_price.cache_clear()
    
    @lru_cache(maxsize=64)
    def get_full_text(self) -> str:
        """Кешированный полный текст"""
        parts = [self.material_name, self.description, self.supplier]
        
        if self.brand:
            parts.append(self.brand)
        
        if self.category:
            parts.append(self.category.value)
        
        if self.specifications:
            spec_text = ' '.join(str(v) for v in self.specifications.values() if v)
            parts.append(spec_text)
        
        return ' '.join(filter(None, parts))
    
    @lru_cache(maxsize=32)
    def formatted_price(self) -> str:
        """Отформатированная цена с валютой"""
        # Округляем до 2 знаков после запятой
        rounded_price = self.price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return f"{rounded_price} {self.currency.value}"
    
    @cached_property
    def display_name(self) -> str:
        """Отображаемое имя с ценой"""
        return f"{self.material_name} - {self.formatted_price()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Оптимизированное преобразование в словарь"""
        return {
            'id': self.id,
            'material_name': self.material_name,
            'description': self.description,
            'price': float(self.price),  # Для JSON сериализации
            'price_decimal': str(self.price),  # Точное значение
            'currency': self.currency.value,
            'supplier': self.supplier,
            'category': self.category.value if self.category else None,
            'brand': self.brand,
            'unit': self.unit,
            'specifications': self.specifications,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'full_text': self.get_full_text(),
            'formatted_price': self.formatted_price(),
            'display_name': self.display_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizedPriceListItem:
        """Типобезопасное создание из словаря с валидацией"""
        
        # Валидация обязательных полей
        required_fields = ['id', 'material_name', 'description', 'price', 'currency', 'supplier']
        for field_name in required_fields:
            if field_name not in data or data[field_name] is None:
                raise ValueError(f"Missing required field: {field_name}")
        
        # Валидация и преобразование цены
        try:
            if 'price_decimal' in data:
                # Используем точное значение если доступно
                price = Decimal(str(data['price_decimal']))
            else:
                price = Decimal(str(data['price']))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid price value: {data.get('price', 'N/A')}") from e
        
        # Парсинг валюты
        currency = data['currency']
        if isinstance(currency, str):
            currency = Currency.from_string(currency)
        elif not isinstance(currency, Currency):
            currency = Currency.RUB
        
        # Парсинг даты
        updated_at = None
        if data.get('updated_at'):
            if isinstance(data['updated_at'], str):
                try:
                    updated_at = datetime.fromisoformat(data['updated_at'])
                except ValueError:
                    updated_at = datetime.now()
            elif isinstance(data['updated_at'], datetime):
                updated_at = data['updated_at']
        
        # Парсинг категории
        category = None
        if data.get('category'):
            if isinstance(data['category'], str):
                category = MaterialCategory.from_string(data['category'])
            elif isinstance(data['category'], MaterialCategory):
                category = data['category']
        
        return cls(
            id=str(data['id']),
            material_name=str(data['material_name']),
            description=str(data['description']),
            price=price,
            currency=currency,
            supplier=str(data['supplier']),
            category=category,
            brand=data.get('brand'),
            unit=data.get('unit'),
            specifications=data.get('specifications', {}),
            updated_at=updated_at
        )
    
    def _compute_hash(self) -> int:
        """Вычисление хеша"""
        return hash((self.id, self.material_name, self.supplier))
    
    def __hash__(self) -> int:
        """Хеш для коллекций"""
        return self._hash_cache if self._hash_cache is not None else self._compute_hash()
    
    def __eq__(self, other: object) -> bool:
        """Сравнение элементов прайс-листа"""
        if not isinstance(other, OptimizedPriceListItem):
            return NotImplemented
        return self.id == other.id
    
    def __repr__(self) -> str:
        return f"OptimizedPriceListItem(id='{self.id}', name='{self.material_name}', price={self.formatted_price()})"


@dataclass(frozen=True, slots=True)
class OptimizedSearchResult(Serializable):
    """
    Типобезопасный результат поиска с метриками производительности
    
    Включает детализированные метрики сопоставления и кешированную сериализацию.
    """
    
    material: OptimizedMaterial
    price_item: OptimizedPriceListItem
    similarity_percentage: float
    similarity_details: Dict[str, float]
    elasticsearch_score: float
    
    # Дополнительные метрики для анализа
    processing_time_ms: float = 0.0
    match_confidence: float = field(init=False)  # Вычисляемое поле
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self) -> None:
        """Валидация и вычисление дополнительных метрик"""
        if not (0 <= self.similarity_percentage <= 100):
            raise ValueError(f"Similarity percentage must be 0-100, got: {self.similarity_percentage}")
        
        if self.elasticsearch_score < 0:
            raise ValueError(f"Elasticsearch score cannot be negative: {self.elasticsearch_score}")
        
        # Вычисляем уверенность совпадения
        confidence = min(
            self.similarity_percentage / 100.0 + 
            min(self.elasticsearch_score / 10.0, 0.3), 
            1.0
        )
        object.__setattr__(self, 'match_confidence', confidence)
    
    @cached_property
    def is_high_confidence_match(self) -> bool:
        """Проверка на высокую уверенность совпадения"""
        return self.similarity_percentage >= 85.0 and self.match_confidence >= 0.8
    
    @cached_property
    def is_perfect_match(self) -> bool:
        """Проверка на идеальное совпадение"""
        return self.similarity_percentage >= 99.0
    
    @cached_property
    def quality_score(self) -> float:
        """Комбинированная оценка качества совпадения"""
        return (
            self.similarity_percentage * 0.6 +
            min(self.elasticsearch_score * 10, 30) * 0.3 +
            self.match_confidence * 100 * 0.1
        )
    
    @cached_property
    def match_grade(self) -> str:
        """Человекочитаемая оценка качества"""
        if self.quality_score >= 90:
            return "Отличное"
        elif self.quality_score >= 75:
            return "Хорошее"
        elif self.quality_score >= 60:
            return "Удовлетворительное"
        elif self.quality_score >= 40:
            return "Слабое"
        else:
            return "Плохое"
    
    def to_dict(self) -> Dict[str, Any]:
        """Расширенная сериализация с метриками производительности"""
        return {
            'material': self.material.to_dict(),
            'price_item': self.price_item.to_dict(),
            'similarity_percentage': round(self.similarity_percentage, 2),
            'similarity_details': {k: round(v, 2) for k, v in self.similarity_details.items()},
            'elasticsearch_score': round(self.elasticsearch_score, 4),
            'match_confidence': round(self.match_confidence, 3),
            'quality_score': round(self.quality_score, 2),
            'match_grade': self.match_grade,
            'is_high_confidence': self.is_high_confidence_match,
            'is_perfect_match': self.is_perfect_match,
            'processing_time_ms': round(self.processing_time_ms, 2),
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizedSearchResult:
        """Создание из словаря с валидацией"""
        material = OptimizedMaterial.from_dict(data['material'])
        price_item = OptimizedPriceListItem.from_dict(data['price_item'])
        
        timestamp = datetime.now()
        if 'timestamp' in data:
            if isinstance(data['timestamp'], str):
                try:
                    timestamp = datetime.fromisoformat(data['timestamp'])
                except ValueError:
                    pass
        
        return cls(
            material=material,
            price_item=price_item,
            similarity_percentage=float(data['similarity_percentage']),
            similarity_details=data['similarity_details'],
            elasticsearch_score=float(data['elasticsearch_score']),
            processing_time_ms=data.get('processing_time_ms', 0.0),
            timestamp=timestamp
        )
    
    def __hash__(self) -> int:
        """Хеш для уникальности результатов"""
        return hash((self.material.id, self.price_item.id))
    
    def __eq__(self, other: object) -> bool:
        """Сравнение результатов поиска"""
        if not isinstance(other, OptimizedSearchResult):
            return NotImplemented
        return (self.material.id == other.material.id and 
                self.price_item.id == other.price_item.id)
    
    def __lt__(self, other: OptimizedSearchResult) -> bool:
        """Сравнение для сортировки по качеству"""
        return self.quality_score < other.quality_score
    
    def __repr__(self) -> str:
        return (f"OptimizedSearchResult(material='{self.material.name}', "
                f"similarity={self.similarity_percentage:.1f}%, "
                f"grade='{self.match_grade}')")


# Factory functions для создания объектов с валидацией
def create_optimized_material(
    id: str, 
    name: str, 
    description: str,
    category: Union[str, MaterialCategory], 
    **kwargs
) -> OptimizedMaterial:
    """Factory function для создания OptimizedMaterial с валидацией"""
    if isinstance(category, str):
        category = MaterialCategory.from_string(category)
    
    return OptimizedMaterial(
        id=id,
        name=name,
        description=description,
        category=category,
        **kwargs
    )


def create_optimized_price_list_item(
    id: str,
    material_name: str,
    description: str,
    price: Union[float, Decimal, str],
    currency: Union[str, Currency],
    supplier: str,
    **kwargs
) -> OptimizedPriceListItem:
    """Factory function для создания OptimizedPriceListItem с валидацией"""
    
    # Преобразуем цену в Decimal
    if not isinstance(price, Decimal):
        price = Decimal(str(price))
    
    # Преобразуем валюту
    if isinstance(currency, str):
        currency = Currency.from_string(currency)
    
    return OptimizedPriceListItem(
        id=id,
        material_name=material_name,
        description=description,
        price=price,
        currency=currency,
        supplier=supplier,
        **kwargs
    )


def create_optimized_search_result(
    material: OptimizedMaterial,
    price_item: OptimizedPriceListItem,
    similarity_percentage: float,
    similarity_details: Dict[str, float],
    elasticsearch_score: float,
    **kwargs
) -> OptimizedSearchResult:
    """Factory function для создания OptimizedSearchResult"""
    return OptimizedSearchResult(
        material=material,
        price_item=price_item,
        similarity_percentage=similarity_percentage,
        similarity_details=similarity_details,
        elasticsearch_score=elasticsearch_score,
        **kwargs
    )


# Type aliases для удобства использования
OptimizedMaterialCollection = Dict[str, OptimizedMaterial]
OptimizedPriceListCollection = Dict[str, OptimizedPriceListItem]
OptimizedSearchResults = List[OptimizedSearchResult]

# Константы для оптимизации
DEFAULT_CACHE_SIZE: Final[int] = 128
MAX_SIMILARITY_DETAILS: Final[int] = 10
PERFORMANCE_THRESHOLD_MS: Final[float] = 100.0


class PerformanceMonitor:
    """Утилитарный класс для мониторинга производительности"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.metrics: Dict[str, Any] = {}
    
    def start(self) -> None:
        """Начать измерение времени"""
        self.start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Остановить измерение и вернуть время в миллисекундах"""
        if self.start_time is None:
            return 0.0
        
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.start_time = None
        return elapsed
    
    def record_metric(self, name: str, value: Any) -> None:
        """Записать метрику производительности"""
        self.metrics[name] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить все метрики"""
        return self.metrics.copy()
    
    def reset(self) -> None:
        """Сбросить все метрики"""
        self.start_time = None
        self.metrics.clear()


# Context manager для автоматического измерения производительности
class performance_timer:
    """Context manager для измерения времени выполнения"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0.0
    
    def __enter__(self) -> performance_timer:
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
    
    def get_elapsed_ms(self) -> float:
        """Получить время выполнения в миллисекундах"""
        return self.elapsed_ms