"""
Архитектурные паттерны для масштабируемости системы сопоставления материалов.

Включает:
- Repository pattern для абстракции доступа к данным
- Factory patterns для создания объектов
- Strategy pattern для алгоритмов сопоставления
- Observer pattern для мониторинга системы
- Command pattern для операций
- Dependency Injection для слабой связанности
- Caching patterns для производительности
- Circuit Breaker для отказоустойчивости
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import (
    Dict, List, Optional, Union, Any, TypeVar, Generic,
    Protocol, Callable, AsyncIterator, Iterator, Type
)
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import asynccontextmanager, contextmanager
import weakref
from functools import wraps, partial
import inspect

from ..models.optimized_material import (
    OptimizedMaterial, OptimizedPriceListItem, OptimizedSearchResult,
    MaterialCategory, Currency
)
from ..services.optimized_similarity_service import OptimizedSimilarityService

logger = logging.getLogger(__name__)

# Type variables для generic patterns
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# ================================
# REPOSITORY PATTERN
# ================================

class Repository(Protocol, Generic[T, K]):
    """Абстрактный репозиторий для доступа к данным"""
    
    async def get_by_id(self, id: K) -> Optional[T]:
        """Получение объекта по ID"""
        ...
    
    async def get_all(self) -> List[T]:
        """Получение всех объектов"""
        ...
    
    async def save(self, entity: T) -> T:
        """Сохранение объекта"""
        ...
    
    async def delete(self, id: K) -> bool:
        """Удаление объекта"""
        ...
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Поиск по критериям"""
        ...


class InMemoryRepository(Generic[T, K]):
    """Реализация репозитория в памяти для тестирования"""
    
    def __init__(self, key_func: Callable[[T], K]):
        self._storage: Dict[K, T] = {}
        self._key_func = key_func
        self._lock = asyncio.Lock()
    
    async def get_by_id(self, id: K) -> Optional[T]:
        async with self._lock:
            return self._storage.get(id)
    
    async def get_all(self) -> List[T]:
        async with self._lock:
            return list(self._storage.values())
    
    async def save(self, entity: T) -> T:
        async with self._lock:
            key = self._key_func(entity)
            self._storage[key] = entity
            return entity
    
    async def delete(self, id: K) -> bool:
        async with self._lock:
            return self._storage.pop(id, None) is not None
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        async with self._lock:
            results = []
            for entity in self._storage.values():
                if self._matches_criteria(entity, criteria):
                    results.append(entity)
            return results
    
    def _matches_criteria(self, entity: T, criteria: Dict[str, Any]) -> bool:
        """Проверка соответствия критериям"""
        for key, value in criteria.items():
            if not hasattr(entity, key):
                return False
            entity_value = getattr(entity, key)
            if entity_value != value:
                return False
        return True


class ElasticsearchRepository(Generic[T, K]):
    """Репозиторий с интеграцией Elasticsearch"""
    
    def __init__(self, es_service, index_name: str, entity_class: Type[T]):
        self.es_service = es_service
        self.index_name = index_name
        self.entity_class = entity_class
    
    async def get_by_id(self, id: K) -> Optional[T]:
        try:
            response = await asyncio.to_thread(
                self.es_service.es.get,
                index=self.index_name,
                id=str(id)
            )
            return self.entity_class.from_dict(response['_source'])
        except Exception as e:
            logger.error(f"Failed to get entity {id}: {e}")
            return None
    
    async def save(self, entity: T) -> T:
        try:
            doc = entity.to_dict()
            await asyncio.to_thread(
                self.es_service.es.index,
                index=self.index_name,
                id=entity.id,
                body=doc
            )
            return entity
        except Exception as e:
            logger.error(f"Failed to save entity: {e}")
            raise
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        # Конвертируем критерии в Elasticsearch query
        query = self._build_query(criteria)
        
        try:
            response = await asyncio.to_thread(
                self.es_service.es.search,
                index=self.index_name,
                body=query
            )
            
            results = []
            for hit in response['hits']['hits']:
                entity = self.entity_class.from_dict(hit['_source'])
                results.append(entity)
            return results
        except Exception as e:
            logger.error(f"Failed to search entities: {e}")
            return []
    
    def _build_query(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Построение Elasticsearch query из критериев"""
        must_clauses = []
        
        for key, value in criteria.items():
            if isinstance(value, str):
                must_clauses.append({"match": {key: value}})
            else:
                must_clauses.append({"term": {key: value}})
        
        return {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            }
        }


# ================================
# FACTORY PATTERNS
# ================================

class EntityFactory(ABC, Generic[T]):
    """Абстрактная фабрика для создания сущностей"""
    
    @abstractmethod
    def create(self, **kwargs) -> T:
        """Создание сущности"""
        pass
    
    @abstractmethod
    def create_from_dict(self, data: Dict[str, Any]) -> T:
        """Создание из словаря"""
        pass


class MaterialFactory(EntityFactory[OptimizedMaterial]):
    """Фабрика для создания материалов с валидацией"""
    
    def create(self, **kwargs) -> OptimizedMaterial:
        # Применяем бизнес-логику и валидацию
        if 'category' in kwargs and isinstance(kwargs['category'], str):
            kwargs['category'] = MaterialCategory.from_string(kwargs['category'])
        
        # Генерируем ID если не указан
        if 'id' not in kwargs:
            kwargs['id'] = self._generate_id(kwargs.get('name', ''))
        
        return OptimizedMaterial(**kwargs)
    
    def create_from_dict(self, data: Dict[str, Any]) -> OptimizedMaterial:
        return OptimizedMaterial.from_dict(data)
    
    def _generate_id(self, name: str) -> str:
        """Генерация уникального ID"""
        import hashlib
        import time
        content = f"{name}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class PriceListItemFactory(EntityFactory[OptimizedPriceListItem]):
    """Фабрика для создания элементов прайс-листа"""
    
    def create(self, **kwargs) -> OptimizedPriceListItem:
        # Валидация и нормализация
        if 'currency' in kwargs and isinstance(kwargs['currency'], str):
            kwargs['currency'] = Currency.from_string(kwargs['currency'])
        
        if 'category' in kwargs and isinstance(kwargs['category'], str):
            kwargs['category'] = MaterialCategory.from_string(kwargs['category'])
        
        if 'id' not in kwargs:
            kwargs['id'] = self._generate_id(
                kwargs.get('material_name', ''),
                kwargs.get('supplier', '')
            )
        
        return OptimizedPriceListItem(**kwargs)
    
    def create_from_dict(self, data: Dict[str, Any]) -> OptimizedPriceListItem:
        return OptimizedPriceListItem.from_dict(data)
    
    def _generate_id(self, material_name: str, supplier: str) -> str:
        import hashlib
        import time
        content = f"{material_name}_{supplier}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class FactoryRegistry:
    """Реестр фабрик для dependency injection"""
    
    def __init__(self):
        self._factories: Dict[Type, EntityFactory] = {}
    
    def register(self, entity_type: Type[T], factory: EntityFactory[T]) -> None:
        """Регистрация фабрики"""
        self._factories[entity_type] = factory
    
    def get_factory(self, entity_type: Type[T]) -> EntityFactory[T]:
        """Получение фабрики"""
        if entity_type not in self._factories:
            raise ValueError(f"No factory registered for {entity_type}")
        return self._factories[entity_type]
    
    def create(self, entity_type: Type[T], **kwargs) -> T:
        """Создание сущности через зарегистрированную фабрику"""
        factory = self.get_factory(entity_type)
        return factory.create(**kwargs)


# ================================
# STRATEGY PATTERN
# ================================

class MatchingStrategy(ABC):
    """Абстрактная стратегия сопоставления"""
    
    @abstractmethod
    async def match(
        self, 
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem]
    ) -> List[OptimizedSearchResult]:
        """Выполнение сопоставления"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Название стратегии"""
        pass


class ExactMatchingStrategy(MatchingStrategy):
    """Стратегия точного совпадения"""
    
    def __init__(self, similarity_service: OptimizedSimilarityService):
        self.similarity_service = similarity_service
    
    async def match(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem]
    ) -> List[OptimizedSearchResult]:
        """Поиск только точных совпадений (>95%)"""
        results = []
        
        for material in materials:
            for price_item in price_items:
                similarity_pct, details = self.similarity_service.calculate_material_similarity(
                    material, price_item
                )
                
                if similarity_pct >= 95.0:
                    result = OptimizedSearchResult(
                        material=material,
                        price_item=price_item,
                        similarity_percentage=similarity_pct,
                        similarity_details=details,
                        elasticsearch_score=0.0
                    )
                    results.append(result)
        
        return results
    
    def get_name(self) -> str:
        return "ExactMatching"


class FuzzyMatchingStrategy(MatchingStrategy):
    """Стратегия нечеткого сопоставления"""
    
    def __init__(self, similarity_service: OptimizedSimilarityService, threshold: float = 70.0):
        self.similarity_service = similarity_service
        self.threshold = threshold
    
    async def match(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem]
    ) -> List[OptimizedSearchResult]:
        """Нечеткое сопоставление с пороговым значением"""
        return await asyncio.to_thread(
            self.similarity_service.batch_similarity,
            materials,
            price_items,
            self.threshold
        )
    
    def get_name(self) -> str:
        return f"FuzzyMatching(threshold={self.threshold})"


class HybridMatchingStrategy(MatchingStrategy):
    """Гибридная стратегия: сначала точное, потом нечеткое"""
    
    def __init__(self, exact_strategy: ExactMatchingStrategy, fuzzy_strategy: FuzzyMatchingStrategy):
        self.exact_strategy = exact_strategy
        self.fuzzy_strategy = fuzzy_strategy
    
    async def match(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem]
    ) -> List[OptimizedSearchResult]:
        """Комбинированный подход"""
        
        # Сначала точное сопоставление
        exact_results = await self.exact_strategy.match(materials, price_items)
        
        # Если нашли точные совпадения, возвращаем их
        exact_material_ids = {result.material.id for result in exact_results}
        
        if exact_results:
            # Исключаем уже найденные материалы из нечеткого поиска
            remaining_materials = [
                m for m in materials if m.id not in exact_material_ids
            ]
            
            if remaining_materials:
                fuzzy_results = await self.fuzzy_strategy.match(remaining_materials, price_items)
                exact_results.extend(fuzzy_results)
        else:
            # Если точных совпадений нет, используем нечеткий поиск
            fuzzy_results = await self.fuzzy_strategy.match(materials, price_items)
            exact_results.extend(fuzzy_results)
        
        return exact_results
    
    def get_name(self) -> str:
        return f"Hybrid({self.exact_strategy.get_name()}, {self.fuzzy_strategy.get_name()})"


class StrategyContext:
    """Контекст для выбора стратегии сопоставления"""
    
    def __init__(self):
        self._strategy: Optional[MatchingStrategy] = None
        self._strategies: Dict[str, MatchingStrategy] = {}
    
    def register_strategy(self, name: str, strategy: MatchingStrategy) -> None:
        """Регистрация стратегии"""
        self._strategies[name] = strategy
    
    def set_strategy(self, strategy_name: str) -> None:
        """Установка текущей стратегии"""
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' not registered")
        self._strategy = self._strategies[strategy_name]
    
    async def execute_matching(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem]
    ) -> List[OptimizedSearchResult]:
        """Выполнение сопоставления с текущей стратегией"""
        if not self._strategy:
            raise ValueError("No strategy set")
        
        logger.info(f"Executing matching with strategy: {self._strategy.get_name()}")
        return await self._strategy.match(materials, price_items)


# ================================
# OBSERVER PATTERN
# ================================

class Event:
    """Базовый класс для событий"""
    
    def __init__(self, event_type: str, data: Dict[str, Any] = None):
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = time.time()


class MatchingStartedEvent(Event):
    def __init__(self, materials_count: int, price_items_count: int):
        super().__init__(
            "matching_started",
            {"materials_count": materials_count, "price_items_count": price_items_count}
        )


class MatchingCompletedEvent(Event):
    def __init__(self, results_count: int, duration_ms: float):
        super().__init__(
            "matching_completed", 
            {"results_count": results_count, "duration_ms": duration_ms}
        )


class Observer(ABC):
    """Абстрактный наблюдатель"""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Обработка события"""
        pass


class LoggingObserver(Observer):
    """Наблюдатель для логирования"""
    
    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.logger = logger_instance or logger
    
    async def handle_event(self, event: Event) -> None:
        self.logger.info(f"Event: {event.event_type}, Data: {event.data}")


class MetricsObserver(Observer):
    """Наблюдатель для сбора метрик"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Any]] = {}
    
    async def handle_event(self, event: Event) -> None:
        if event.event_type not in self.metrics:
            self.metrics[event.event_type] = []
        self.metrics[event.event_type].append(event.data)
    
    def get_metrics(self) -> Dict[str, List[Any]]:
        return self.metrics.copy()
    
    def clear_metrics(self) -> None:
        self.metrics.clear()


class EventEmitter:
    """Эмиттер событий с поддержкой наблюдателей"""
    
    def __init__(self):
        self._observers: List[Observer] = []
        self._lock = threading.Lock()
    
    def subscribe(self, observer: Observer) -> None:
        """Подписка на события"""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
    
    def unsubscribe(self, observer: Observer) -> None:
        """Отписка от событий"""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    async def emit(self, event: Event) -> None:
        """Отправка события всем наблюдателям"""
        observers_copy = list(self._observers)
        
        tasks = []
        for observer in observers_copy:
            task = asyncio.create_task(observer.handle_event(event))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# ================================
# COMMAND PATTERN
# ================================

class Command(ABC):
    """Абстрактная команда"""
    
    @abstractmethod
    async def execute(self) -> Any:
        """Выполнение команды"""
        pass
    
    @abstractmethod
    async def undo(self) -> Any:
        """Отмена команды"""
        pass
    
    def get_description(self) -> str:
        """Описание команды"""
        return self.__class__.__name__


class MatchMaterialsCommand(Command):
    """Команда сопоставления материалов"""
    
    def __init__(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem],
        strategy: MatchingStrategy,
        event_emitter: Optional[EventEmitter] = None
    ):
        self.materials = materials
        self.price_items = price_items
        self.strategy = strategy
        self.event_emitter = event_emitter
        self.results: Optional[List[OptimizedSearchResult]] = None
        self.execution_time: Optional[float] = None
    
    async def execute(self) -> List[OptimizedSearchResult]:
        """Выполнение сопоставления"""
        start_time = time.time()
        
        if self.event_emitter:
            await self.event_emitter.emit(MatchingStartedEvent(
                len(self.materials), len(self.price_items)
            ))
        
        try:
            self.results = await self.strategy.match(self.materials, self.price_items)
            self.execution_time = (time.time() - start_time) * 1000
            
            if self.event_emitter:
                await self.event_emitter.emit(MatchingCompletedEvent(
                    len(self.results), self.execution_time
                ))
            
            return self.results
        
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise
    
    async def undo(self) -> Any:
        """Отмена команды (очистка результатов)"""
        self.results = None
        self.execution_time = None
        return True
    
    def get_description(self) -> str:
        return f"MatchMaterials({len(self.materials)} materials, {len(self.price_items)} price items)"


class CommandInvoker:
    """Инвокер команд с поддержкой истории"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: List[Command] = []
        self._current_index = -1
    
    async def execute(self, command: Command) -> Any:
        """Выполнение команды с сохранением в историю"""
        result = await command.execute()
        
        # Обрезаем историю если превысили лимит
        if len(self._history) >= self.max_history:
            self._history.pop(0)
            self._current_index -= 1
        
        # Добавляем команду в историю
        self._history.append(command)
        self._current_index += 1
        
        logger.info(f"Executed command: {command.get_description()}")
        return result
    
    async def undo_last(self) -> Optional[Any]:
        """Отмена последней команды"""
        if self._current_index >= 0:
            command = self._history[self._current_index]
            result = await command.undo()
            self._current_index -= 1
            logger.info(f"Undone command: {command.get_description()}")
            return result
        return None
    
    def get_history(self) -> List[str]:
        """Получение истории команд"""
        return [cmd.get_description() for cmd in self._history]


# ================================
# CIRCUIT BREAKER PATTERN
# ================================

class CircuitBreakerState(Enum):
    """Состояния Circuit Breaker"""
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Сервис недоступен
    HALF_OPEN = "half_open" # Тестирование восстановления


@dataclass
class CircuitBreakerConfig:
    """Конфигурация Circuit Breaker"""
    failure_threshold: int = 5          # Количество ошибок для открытия
    timeout_duration: float = 60.0      # Время до попытки восстановления (секунды)
    success_threshold: int = 3          # Количество успехов для закрытия
    
    
class CircuitBreaker:
    """Circuit Breaker для отказоустойчивости"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()
    
    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Вызов функции через Circuit Breaker"""
        
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    logger.info("Circuit breaker: HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN - service unavailable")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Проверка, можно ли попытаться восстановить соединение"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout_duration
    
    async def _on_success(self) -> None:
        """Обработка успешного вызова"""
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker: CLOSED state (recovered)")
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0
    
    async def _on_failure(self) -> None:
        """Обработка неудачного вызова"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if (self.state == CircuitBreakerState.CLOSED and 
                self.failure_count >= self.config.failure_threshold):
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker: OPEN state (failures: {self.failure_count})")
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker: OPEN state (half-open failure)")


# ================================
# DEPENDENCY INJECTION CONTAINER
# ================================

class DIContainer:
    """Контейнер для Dependency Injection"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        
    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        """Регистрация singleton сервиса"""
        self._singletons[service_type] = instance
    
    def register_factory(self, service_type: Type[T], factory: Callable[..., T]) -> None:
        """Регистрация фабрики для создания сервиса"""
        self._factories[service_type] = factory
    
    def register_transient(self, service_type: Type[T], implementation: Type[T]) -> None:
        """Регистрация transient сервиса"""
        self._services[service_type] = implementation
    
    def resolve(self, service_type: Type[T]) -> T:
        """Получение экземпляра сервиса"""
        
        # Проверяем singletons
        if service_type in self._singletons:
            return self._singletons[service_type]
        
        # Проверяем фабрики
        if service_type in self._factories:
            factory = self._factories[service_type]
            instance = self._inject_dependencies(factory)
            return instance
        
        # Проверяем transient
        if service_type in self._services:
            implementation = self._services[service_type]
            instance = self._inject_dependencies(implementation)
            return instance
        
        raise ValueError(f"Service {service_type} not registered")
    
    def _inject_dependencies(self, cls_or_func: Union[Type, Callable]) -> Any:
        """Автоматическое внедрение зависимостей"""
        
        if inspect.isclass(cls_or_func):
            # Получаем параметры конструктора
            init_signature = inspect.signature(cls_or_func.__init__)
            
            kwargs = {}
            for param_name, param in init_signature.parameters.items():
                if param_name == 'self':
                    continue
                
                if param.annotation != inspect.Parameter.empty:
                    try:
                        dependency = self.resolve(param.annotation)
                        kwargs[param_name] = dependency
                    except ValueError:
                        if param.default == inspect.Parameter.empty:
                            raise ValueError(
                                f"Cannot resolve dependency {param.annotation} for {cls_or_func}"
                            )
            
            return cls_or_func(**kwargs)
        
        else:
            # Для функций
            return cls_or_func()


# ================================
# APPLICATION SERVICE
# ================================

class MaterialMatchingApplicationService:
    """Основной сервис приложения, объединяющий все паттерны"""
    
    def __init__(
        self,
        material_repository: Repository[OptimizedMaterial, str],
        price_item_repository: Repository[OptimizedPriceListItem, str],
        strategy_context: StrategyContext,
        event_emitter: EventEmitter,
        command_invoker: CommandInvoker,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        self.material_repository = material_repository
        self.price_item_repository = price_item_repository
        self.strategy_context = strategy_context
        self.event_emitter = event_emitter
        self.command_invoker = command_invoker
        self.circuit_breaker = circuit_breaker
        
    async def match_materials(
        self,
        material_criteria: Optional[Dict[str, Any]] = None,
        strategy_name: str = "hybrid"
    ) -> List[OptimizedSearchResult]:
        """Основной метод сопоставления материалов"""
        
        # Получаем данные из репозиториев
        materials = await self._get_materials(material_criteria)
        price_items = await self.price_item_repository.get_all()
        
        if not materials:
            logger.warning("No materials found for matching")
            return []
        
        if not price_items:
            logger.warning("No price items found for matching")
            return []
        
        # Устанавливаем стратегию
        self.strategy_context.set_strategy(strategy_name)
        
        # Создаем команду
        command = MatchMaterialsCommand(
            materials=materials,
            price_items=price_items,
            strategy=self.strategy_context._strategy,
            event_emitter=self.event_emitter
        )
        
        # Выполняем команду через Circuit Breaker если доступен
        if self.circuit_breaker:
            return await self.circuit_breaker.call(
                self.command_invoker.execute, command
            )
        else:
            return await self.command_invoker.execute(command)
    
    async def _get_materials(
        self, criteria: Optional[Dict[str, Any]]
    ) -> List[OptimizedMaterial]:
        """Получение материалов с возможной фильтрацией"""
        if criteria:
            return await self.material_repository.find_by_criteria(criteria)
        else:
            return await self.material_repository.get_all()
    
    async def add_material(self, material: OptimizedMaterial) -> OptimizedMaterial:
        """Добавление нового материала"""
        return await self.material_repository.save(material)
    
    async def add_price_item(self, price_item: OptimizedPriceListItem) -> OptimizedPriceListItem:
        """Добавление элемента прайс-листа"""
        return await self.price_item_repository.save(price_item)
    
    def get_command_history(self) -> List[str]:
        """Получение истории команд"""
        return self.command_invoker.get_history()
    
    async def undo_last_operation(self) -> Optional[Any]:
        """Отмена последней операции"""
        return await self.command_invoker.undo_last()


# ================================
# FACTORY FUNCTIONS
# ================================

def create_application_service(
    es_service=None,
    similarity_service: Optional[OptimizedSimilarityService] = None,
    enable_circuit_breaker: bool = True
) -> MaterialMatchingApplicationService:
    """Factory function для создания полного application service"""
    
    # Создаем DI контейнер
    container = DIContainer()
    
    # Регистрируем базовые сервисы
    if similarity_service:
        container.register_singleton(OptimizedSimilarityService, similarity_service)
    
    # Создаем репозитории
    if es_service:
        material_repo = ElasticsearchRepository(es_service, "materials", OptimizedMaterial)
        price_repo = ElasticsearchRepository(es_service, "price_list", OptimizedPriceListItem)
    else:
        material_repo = InMemoryRepository(lambda m: m.id)
        price_repo = InMemoryRepository(lambda p: p.id)
    
    # Создаем стратегии
    similarity_svc = similarity_service or container.resolve(OptimizedSimilarityService)
    
    exact_strategy = ExactMatchingStrategy(similarity_svc)
    fuzzy_strategy = FuzzyMatchingStrategy(similarity_svc, threshold=70.0)
    hybrid_strategy = HybridMatchingStrategy(exact_strategy, fuzzy_strategy)
    
    # Настраиваем контекст стратегий
    strategy_context = StrategyContext()
    strategy_context.register_strategy("exact", exact_strategy)
    strategy_context.register_strategy("fuzzy", fuzzy_strategy)
    strategy_context.register_strategy("hybrid", hybrid_strategy)
    
    # Создаем наблюдателей
    event_emitter = EventEmitter()
    logging_observer = LoggingObserver()
    metrics_observer = MetricsObserver()
    
    event_emitter.subscribe(logging_observer)
    event_emitter.subscribe(metrics_observer)
    
    # Создаем инвокер команд
    command_invoker = CommandInvoker(max_history=50)
    
    # Создаем Circuit Breaker если нужен
    circuit_breaker = None
    if enable_circuit_breaker:
        cb_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_duration=30.0,
            success_threshold=2
        )
        circuit_breaker = CircuitBreaker(cb_config)
    
    # Создаем основной сервис
    return MaterialMatchingApplicationService(
        material_repository=material_repo,
        price_item_repository=price_repo,
        strategy_context=strategy_context,
        event_emitter=event_emitter,
        command_invoker=command_invoker,
        circuit_breaker=circuit_breaker
    )


@asynccontextmanager
async def application_service_context(**kwargs):
    """Async context manager для application service"""
    service = create_application_service(**kwargs)
    try:
        yield service
    finally:
        # Cleanup if needed
        logger.info("Application service context closed")


# Пример использования всех паттернов вместе
async def demo_usage():
    """Демонстрация использования всех паттернов"""
    
    async with application_service_context() as app_service:
        # Добавляем материалы
        material = OptimizedMaterial(
            id="mat1",
            name="Кабель ВВГ 3x2.5",
            description="Силовой кабель",
            category=MaterialCategory.CABLES
        )
        await app_service.add_material(material)
        
        # Добавляем элементы прайс-листа
        price_item = OptimizedPriceListItem(
            id="price1",
            material_name="Кабель ВВГ 3x2.5",
            description="Силовой кабель для проводки",
            price=100.0,
            currency=Currency.RUB,
            supplier="Поставщик А"
        )
        await app_service.add_price_item(price_item)
        
        # Выполняем сопоставление
        results = await app_service.match_materials(strategy_name="hybrid")
        
        logger.info(f"Found {len(results)} matches")
        for result in results:
            logger.info(
                f"Match: {result.material.name} -> {result.price_item.material_name} "
                f"({result.similarity_percentage:.1f}%)"
            )


if __name__ == "__main__":
    # Запуск демонстрации
    asyncio.run(demo_usage())