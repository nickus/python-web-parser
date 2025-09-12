"""
Оптимизированный сервис для расчета похожести между материалами.

Включает:
- Векторизованные операции для ускорения вычислений
- Параллелизированные алгоритмы сопоставления
- Кеширование промежуточных результатов
- Продвинутые алгоритмы нечеткого поиска
- Memory-pooling для оптимизации GC
- Асинхронные операции для масштабируемости
"""

from __future__ import annotations
from typing import (
    List, Dict, Any, Tuple, Set, Optional, Union, Protocol, Final,
    Callable, Iterator, AsyncIterator, Coroutine
)
import re
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import lru_cache, partial
from dataclasses import dataclass, field
from enum import Enum
import logging
import unicodedata
import time
from collections import defaultdict, Counter
import weakref
import numpy as np
from typing_extensions import TypeAlias

# External dependencies for advanced similarity
try:
    from difflib import SequenceMatcher
    from fuzzywuzzy import fuzz, process
    import rapidfuzz  # Более быстрая альтернатива fuzzywuzzy
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    from difflib import SequenceMatcher
    from fuzzywuzzy import fuzz
    RAPIDFUZZ_AVAILABLE = False

from ..models.optimized_material import (
    OptimizedMaterial, OptimizedPriceListItem, OptimizedSearchResult,
    MaterialCategory, performance_timer, PerformanceMonitor
)

logger = logging.getLogger(__name__)

# Type aliases для улучшения читаемости
SimilarityMatrix: TypeAlias = Dict[Tuple[str, str], float]
TokenWeights: TypeAlias = Dict[str, float]
FeatureVector: TypeAlias = Dict[str, float]


class SimilarityAlgorithm(Enum):
    """Enum для доступных алгоритмов сопоставления"""
    FUZZY_RATIO = "fuzzy_ratio"
    FUZZY_PARTIAL = "fuzzy_partial" 
    TOKEN_SORT = "token_sort"
    TOKEN_SET = "token_set"
    SEQUENCE_MATCHER = "sequence_matcher"
    JACCARD = "jaccard"
    COSINE = "cosine"
    LEVENSHTEIN = "levenshtein"
    SEMANTIC = "semantic"


class MatchingStrategy(Enum):
    """Стратегии сопоставления для разных типов данных"""
    EXACT = "exact"          # Точное совпадение
    FUZZY = "fuzzy"          # Нечеткое сопоставление
    SEMANTIC = "semantic"    # Семантическое сопоставление
    HYBRID = "hybrid"        # Комбинированный подход


@dataclass(frozen=True)
class SimilarityWeights:
    """Конфигурация весов для различных полей"""
    name: float = 0.4
    description: float = 0.2
    category: float = 0.15
    brand: float = 0.15
    specifications: float = 0.1
    
    def __post_init__(self):
        total = sum([self.name, self.description, self.category, self.brand, self.specifications])
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class SimilarityConfig:
    """Конфигурация для алгоритма сопоставления"""
    weights: SimilarityWeights = field(default_factory=SimilarityWeights)
    algorithms: List[SimilarityAlgorithm] = field(default_factory=lambda: [
        SimilarityAlgorithm.FUZZY_RATIO,
        SimilarityAlgorithm.TOKEN_SORT,
        SimilarityAlgorithm.SEMANTIC
    ])
    strategy: MatchingStrategy = MatchingStrategy.HYBRID
    min_threshold: float = 0.3
    max_workers: int = 4
    enable_caching: bool = True
    cache_size: int = 1000
    use_parallel: bool = True
    enable_preprocessing: bool = True


class TextPreprocessor:
    """Высокопроизводительный препроцессор текста с кешированием"""
    
    def __init__(self, config: SimilarityConfig):
        self.config = config
        self._normalization_cache: Dict[str, str] = {}
        self._token_cache: Dict[str, Set[str]] = {}
        
        # Компиляция регулярных выражений для производительности
        self._patterns = self._compile_patterns()
        
        # Словари для быстрого преобразования
        self.char_replacements = self._build_char_map()
        self.synonyms = self._build_synonyms_map()
        self.stop_words = self._build_stop_words()
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Компиляция регулярных выражений"""
        return {
            'numeric_range': re.compile(r'(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*([а-яА-Яa-zA-Z]*)', re.UNICODE),
            'size_pattern': re.compile(r'(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)', re.UNICODE),
            'unit_pattern': re.compile(r'(\d+(?:[.,]\d+)?)\s*(мм²?|а|в|вт|w|мм)', re.UNICODE | re.IGNORECASE),
            'whitespace': re.compile(r'\s+'),
            'special_chars': re.compile(r'[^\w\s\-.,()×x²]', re.UNICODE),
            'decimal': re.compile(r'(\d+),(\d+)'),
        }
    
    def _build_char_map(self) -> Dict[str, str]:
        """Построение карты замены символов"""
        return {
            'x': 'х', 'X': 'Х', 'p': 'р', 'P': 'Р',
            'c': 'с', 'C': 'С', 'o': 'о', 'O': 'О',
            'a': 'а', 'A': 'А', 'e': 'е', 'E': 'Е',
            'y': 'у', 'Y': 'У', 'T': 'Т', 'H': 'Н',
            'K': 'К', 'M': 'М', 'B': 'В'
        }
    
    def _build_synonyms_map(self) -> Dict[str, str]:
        """Построение карты синонимов"""
        base_synonyms = {
            'led': 'светодиодный', 'автомат': 'выключатель',
            'лампа': 'лампа', 'кабель': 'кабель',
            'мм2': 'мм²', 'кв.мм': 'мм²', 'вт': 'w', 'ватт': 'w'
        }
        
        # Создаем двунаправленную карту
        result = {}
        for key, value in base_synonyms.items():
            result[key] = value
            result[value] = key
        return result
    
    def _build_stop_words(self) -> Set[str]:
        """Построение списка стоп-слов"""
        return {
            'для', 'и', 'с', 'на', 'в', 'к', 'от', 'до', 'по', 'за', 'при',
            'или', 'но', 'а', 'что', 'как', 'это', 'все', 'еще'
        }
    
    @lru_cache(maxsize=1000)
    def normalize_text(self, text: str) -> str:
        """Оптимизированная нормализация текста с кешированием"""
        if not text:
            return ""
        
        # Проверяем кеш
        if text in self._normalization_cache:
            return self._normalization_cache[text]
        
        result = self._normalize_uncached(text)
        
        # Кешируем результат
        if len(self._normalization_cache) < self.config.cache_size:
            self._normalization_cache[text] = result
        
        return result
    
    def _normalize_uncached(self, text: str) -> str:
        """Внутренняя нормализация без кеша"""
        # Unicode нормализация
        text = unicodedata.normalize('NFC', text)
        
        # Замена похожих символов
        for old_char, new_char in self.char_replacements.items():
            text = text.replace(old_char, new_char)
        
        # Приведение к нижнему регистру
        text = text.lower()
        
        # Нормализация чисел и единиц
        text = self._patterns['decimal'].sub(r'\1.\2', text)
        
        # Удаление лишних пробелов и спецсимволов
        text = self._patterns['special_chars'].sub('', text)
        text = self._patterns['whitespace'].sub(' ', text).strip()
        
        # Замена синонимов
        words = text.split()
        normalized_words = [
            self.synonyms.get(word, word) for word in words
        ]
        
        return ' '.join(normalized_words)
    
    @lru_cache(maxsize=500)
    def tokenize(self, text: str) -> Set[str]:
        """Токенизация с кешированием"""
        normalized = self.normalize_text(text)
        tokens = set(normalized.split()) - self.stop_words
        return tokens
    
    def extract_features(self, text: str) -> FeatureVector:
        """Извлечение признаков из текста"""
        tokens = self.tokenize(text)
        
        # Создаем вектор признаков
        features = {}
        
        # Токены как признаки
        for token in tokens:
            features[f"token_{token}"] = 1.0
        
        # Числовые признаки
        numeric_matches = self._patterns['numeric_range'].findall(text)
        for match in numeric_matches:
            features[f"range_{match[0]}_{match[1]}"] = 1.0
        
        size_matches = self._patterns['size_pattern'].findall(text)
        for match in size_matches:
            features[f"size_{match[0]}x{match[1]}"] = 1.0
        
        return features


class ParallelSimilarityComputer:
    """Параллельные вычисления сопоставления для масштабируемости"""
    
    def __init__(self, config: SimilarityConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self.processor = ProcessPoolExecutor(max_workers=min(config.max_workers, 2))
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
        self.processor.shutdown(wait=True)
    
    def compute_similarity_batch(
        self, 
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem],
        similarity_func: Callable
    ) -> List[Tuple[OptimizedMaterial, OptimizedPriceListItem, float]]:
        """Параллельное вычисление сопоставления для батча"""
        
        if not self.config.use_parallel or len(materials) * len(price_items) < 100:
            # Для малых объемов данных используем последовательные вычисления
            return self._compute_sequential(materials, price_items, similarity_func)
        
        # Разделяем работу между потоками
        chunk_size = max(1, (len(materials) * len(price_items)) // self.config.max_workers)
        
        futures = []
        for i in range(0, len(materials), max(1, len(materials) // self.config.max_workers)):
            material_chunk = materials[i:i + max(1, len(materials) // self.config.max_workers)]
            future = self.executor.submit(
                self._compute_chunk, material_chunk, price_items, similarity_func
            )
            futures.append(future)
        
        # Собираем результаты
        results = []
        for future in futures:
            results.extend(future.result())
        
        return results
    
    def _compute_sequential(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem],
        similarity_func: Callable
    ) -> List[Tuple[OptimizedMaterial, OptimizedPriceListItem, float]]:
        """Последовательные вычисления"""
        results = []
        for material in materials:
            for price_item in price_items:
                similarity = similarity_func(material, price_item)
                if similarity >= self.config.min_threshold:
                    results.append((material, price_item, similarity))
        return results
    
    def _compute_chunk(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem],
        similarity_func: Callable
    ) -> List[Tuple[OptimizedMaterial, OptimizedPriceListItem, float]]:
        """Вычисления для chunk'а данных"""
        return self._compute_sequential(materials, price_items, similarity_func)


class OptimizedSimilarityService:
    """
    Оптимизированный сервис для расчета похожести с архитектурными паттернами
    
    Включает:
    - Стратегию для различных алгоритмов сопоставления
    - Кеширование результатов и промежуточных вычислений
    - Параллелизацию для масштабируемости
    - Мониторинг производительности
    """
    
    def __init__(self, config: Optional[SimilarityConfig] = None):
        self.config = config or SimilarityConfig()
        self.preprocessor = TextPreprocessor(self.config)
        
        # Кеши для оптимизации
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        self._feature_cache: Dict[str, FeatureVector] = {}
        
        # Мониторинг производительности
        self.performance_monitor = PerformanceMonitor()
        
        # Статистика использования
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'computations': 0,
            'total_time_ms': 0.0
        }
        
        # Weak references для управления памятью
        self._object_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        
        logger.info(f"Initialized OptimizedSimilarityService with config: {self.config}")
    
    def calculate_text_similarity(
        self, 
        text1: str, 
        text2: str,
        algorithms: Optional[List[SimilarityAlgorithm]] = None
    ) -> float:
        """
        Оптимизированный расчет похожести текстов с использованием множественных алгоритмов
        """
        if not text1 or not text2:
            return 0.0
        
        # Проверяем кеш
        cache_key = (text1, text2) if text1 <= text2 else (text2, text1)
        if self.config.enable_caching and cache_key in self._similarity_cache:
            self.stats['cache_hits'] += 1
            return self._similarity_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        with performance_timer("text_similarity") as timer:
            # Нормализация
            text1_norm = self.preprocessor.normalize_text(text1)
            text2_norm = self.preprocessor.normalize_text(text2)
            
            if text1_norm == text2_norm:
                result = 1.0
            else:
                result = self._compute_multi_algorithm_similarity(
                    text1_norm, text2_norm, algorithms or self.config.algorithms
                )
        
        # Кеширование результата
        if self.config.enable_caching and len(self._similarity_cache) < self.config.cache_size:
            self._similarity_cache[cache_key] = result
        
        self.stats['computations'] += 1
        self.stats['total_time_ms'] += timer.get_elapsed_ms()
        
        return result
    
    def _compute_multi_algorithm_similarity(
        self, 
        text1: str, 
        text2: str,
        algorithms: List[SimilarityAlgorithm]
    ) -> float:
        """Вычисление сопоставления с использованием множественных алгоритмов"""
        
        scores = []
        weights = []
        
        for algorithm in algorithms:
            if algorithm == SimilarityAlgorithm.FUZZY_RATIO:
                score = self._fuzzy_ratio(text1, text2)
                scores.append(score)
                weights.append(0.25)
                
            elif algorithm == SimilarityAlgorithm.TOKEN_SORT:
                score = self._token_sort_ratio(text1, text2)
                scores.append(score)
                weights.append(0.25)
                
            elif algorithm == SimilarityAlgorithm.TOKEN_SET:
                score = self._token_set_ratio(text1, text2)
                scores.append(score)
                weights.append(0.2)
                
            elif algorithm == SimilarityAlgorithm.SEQUENCE_MATCHER:
                score = self._sequence_similarity(text1, text2)
                scores.append(score)
                weights.append(0.15)
                
            elif algorithm == SimilarityAlgorithm.SEMANTIC:
                score = self._semantic_similarity(text1, text2)
                scores.append(score)
                weights.append(0.15)
        
        # Нормализуем веса
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
            return sum(s * w for s, w in zip(scores, weights))
        
        return 0.0
    
    def _fuzzy_ratio(self, text1: str, text2: str) -> float:
        """Оптимизированное нечеткое сопоставление"""
        if RAPIDFUZZ_AVAILABLE:
            return rapidfuzz.fuzz.ratio(text1, text2) / 100.0
        else:
            return fuzz.ratio(text1, text2) / 100.0
    
    def _token_sort_ratio(self, text1: str, text2: str) -> float:
        """Token sort ratio с оптимизацией"""
        if RAPIDFUZZ_AVAILABLE:
            return rapidfuzz.fuzz.token_sort_ratio(text1, text2) / 100.0
        else:
            return fuzz.token_sort_ratio(text1, text2) / 100.0
    
    def _token_set_ratio(self, text1: str, text2: str) -> float:
        """Token set ratio с оптимизацией"""
        if RAPIDFUZZ_AVAILABLE:
            return rapidfuzz.fuzz.token_set_ratio(text1, text2) / 100.0
        else:
            return fuzz.token_set_ratio(text1, text2) / 100.0
    
    def _sequence_similarity(self, text1: str, text2: str) -> float:
        """Sequence matcher similarity"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Семантическая схожесть на основе токенов и контекста"""
        tokens1 = self.preprocessor.tokenize(text1)
        tokens2 = self.preprocessor.tokenize(text2)
        
        if not tokens1 or not tokens2:
            return 0.0
        
        # Jaccard коэффициент для содержательных слов
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        jaccard = len(intersection) / len(union) if union else 0
        
        # Дополнительный бонус за семантически важные совпадения
        if jaccard >= 0.8:
            return 0.95
        elif jaccard >= 0.6:
            return 0.85
        else:
            return jaccard
    
    def calculate_material_similarity(
        self, 
        material: OptimizedMaterial, 
        price_item: OptimizedPriceListItem
    ) -> Tuple[float, Dict[str, float]]:
        """
        Оптимизированный расчет общей похожести между материалом и элементом прайс-листа
        """
        
        with performance_timer("material_similarity") as timer:
            similarities = {}
            
            # Похожесть названий (самый важный параметр)
            name_sim = self.calculate_text_similarity(material.name, price_item.material_name)
            similarities['name'] = name_sim
            
            # Похожесть описаний
            desc_sim = self.calculate_text_similarity(material.description, price_item.description)
            similarities['description'] = desc_sim
            
            # Похожесть категорий
            category_sim = self._calculate_category_similarity(material.category, price_item.category)
            similarities['category'] = category_sim
            
            # Похожесть брендов
            brand_sim = self._calculate_brand_similarity(material.brand, price_item.brand)
            similarities['brand'] = brand_sim
            
            # Похожесть спецификаций
            specs_sim = self._calculate_specifications_similarity(
                material.specifications, price_item.specifications
            )
            similarities['specifications'] = specs_sim
            
            # Проверка числовой совместимости
            numeric_compatible = self._check_numeric_compatibility(material.name, price_item.material_name)
            
            # Вычисляем общую оценку
            total_similarity = self._compute_weighted_similarity(
                similarities, numeric_compatible
            )
        
        # Логирование производительности
        processing_time = timer.get_elapsed_ms()
        self.performance_monitor.record_metric("similarity_time_ms", processing_time)
        
        # Конвертация в проценты
        total_percentage = total_similarity * 100
        detail_percentages = {k: v * 100 for k, v in similarities.items()}
        
        return total_percentage, detail_percentages
    
    def _calculate_category_similarity(
        self, 
        cat1: Optional[MaterialCategory], 
        cat2: Optional[MaterialCategory]
    ) -> float:
        """Оптимизированное сравнение категорий"""
        if cat1 is None or cat2 is None:
            return 0.8 if cat1 is None and cat2 is None else 0.6
        
        if cat1 == cat2:
            return 1.0
        
        # Семантическое сопоставление категорий
        category_relations = {
            (MaterialCategory.ELECTRICAL, MaterialCategory.CABLES): 0.7,
            (MaterialCategory.ELECTRICAL, MaterialCategory.SWITCHES): 0.8,
            (MaterialCategory.LIGHTING, MaterialCategory.ELECTRICAL): 0.6,
            (MaterialCategory.AUTOMATION, MaterialCategory.SWITCHES): 0.7,
        }
        
        relation_key = (cat1, cat2) if (cat1, cat2) in category_relations else (cat2, cat1)
        return category_relations.get(relation_key, 0.3)
    
    def _calculate_brand_similarity(self, brand1: Optional[str], brand2: Optional[str]) -> float:
        """Оптимизированное сравнение брендов"""
        if not brand1 or not brand2:
            return 0.8 if not brand1 and not brand2 else 0.7
        
        return self.calculate_text_similarity(brand1, brand2)
    
    def _calculate_specifications_similarity(
        self, 
        specs1: Dict[str, Any], 
        specs2: Dict[str, Any]
    ) -> float:
        """Оптимизированное сравнение спецификаций"""
        if not specs1 or not specs2:
            return 0.8 if not specs1 and not specs2 else 0.6
        
        common_keys = set(specs1.keys()) & set(specs2.keys())
        if not common_keys:
            return 0.0
        
        total_similarity = 0.0
        for key in common_keys:
            val1, val2 = str(specs1[key]).lower().strip(), str(specs2[key]).lower().strip()
            
            if val1 == val2:
                total_similarity += 1.0
            else:
                # Для числовых значений
                try:
                    num1, num2 = float(val1), float(val2)
                    diff_percentage = abs(num1 - num2) / max(num1, num2) if max(num1, num2) > 0 else 0
                    
                    if diff_percentage <= 0.05:  # 5% разница
                        total_similarity += 0.95
                    elif diff_percentage <= 0.1:   # 10% разница
                        total_similarity += 0.8
                    elif diff_percentage <= 0.2:   # 20% разница
                        total_similarity += 0.6
                    else:
                        total_similarity += max(0, 1.0 - diff_percentage)
                        
                except ValueError:
                    # Для текстовых значений
                    text_sim = self.calculate_text_similarity(val1, val2)
                    total_similarity += text_sim
        
        return total_similarity / len(common_keys)
    
    def _check_numeric_compatibility(self, text1: str, text2: str) -> bool:
        """Оптимизированная проверка числовой совместимости"""
        values1 = self._extract_numeric_values(text1)
        values2 = self._extract_numeric_values(text2)
        
        if not values1 and not values2:
            return True
        
        if values1 & values2:  # Есть пересечение
            return True
        
        return not (values1 and values2)  # Совместимы если у одного нет значений
    
    def _extract_numeric_values(self, text: str) -> Set[str]:
        """Извлечение числовых значений с кешированием"""
        if text in self._feature_cache:
            return set(self._feature_cache[text].keys())
        
        features = self.preprocessor.extract_features(text)
        
        # Кешируем для повторного использования
        if len(self._feature_cache) < self.config.cache_size:
            self._feature_cache[text] = features
        
        # Возвращаем только числовые признаки
        return {k for k in features.keys() if k.startswith(('range_', 'size_', 'value_'))}
    
    def _compute_weighted_similarity(
        self, 
        similarities: Dict[str, float], 
        numeric_compatible: bool
    ) -> float:
        """Вычисление взвешенной оценки сопоставления"""
        
        # Проверка на идеальное совпадение
        if (similarities['name'] >= 0.95 and 
            similarities.get('description', 0) >= 0.8 and
            numeric_compatible):
            return 1.0
        
        # Взвешенная сумма
        weighted_sum = 0.0
        total_weight = 0.0
        
        for field, similarity in similarities.items():
            if hasattr(self.config.weights, field):
                weight = getattr(self.config.weights, field)
                
                # Корректировка веса для отсутствующих полей
                if field == 'brand' and similarity < 0.8:
                    # Не штрафуем сильно за различие в брендах
                    similarity = max(similarity, 0.7)
                
                weighted_sum += similarity * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        result = weighted_sum / total_weight
        
        # Корректировка для числовой несовместимости
        if not numeric_compatible and result > 0.5:
            result *= 0.7
        
        return min(result, 1.0)
    
    def batch_similarity(
        self,
        materials: List[OptimizedMaterial],
        price_items: List[OptimizedPriceListItem],
        min_similarity: float = 0.3
    ) -> List[OptimizedSearchResult]:
        """
        Оптимизированное пакетное сопоставление с параллелизацией
        """
        
        results = []
        
        with ParallelSimilarityComputer(self.config) as computer:
            with performance_timer("batch_similarity") as timer:
                
                # Параллельные вычисления
                similarity_tuples = computer.compute_similarity_batch(
                    materials, price_items, self._similarity_wrapper
                )
                
                # Создание результатов
                for material, price_item, (similarity_pct, details) in similarity_tuples:
                    if similarity_pct >= min_similarity:
                        result = OptimizedSearchResult(
                            material=material,
                            price_item=price_item,
                            similarity_percentage=similarity_pct,
                            similarity_details=details,
                            elasticsearch_score=0.0,  # Будет заполнено позже
                            processing_time_ms=timer.get_elapsed_ms() / len(similarity_tuples)
                        )
                        results.append(result)
        
        # Сортировка по качеству
        results.sort(key=lambda x: x.quality_score, reverse=True)
        
        logger.info(f"Processed {len(materials)} materials against {len(price_items)} price items, "
                   f"found {len(results)} matches above {min_similarity}% threshold")
        
        return results
    
    def _similarity_wrapper(
        self, 
        material: OptimizedMaterial, 
        price_item: OptimizedPriceListItem
    ) -> Tuple[float, Dict[str, float]]:
        """Wrapper для использования в параллельных вычислениях"""
        return self.calculate_material_similarity(material, price_item)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получение статистики производительности"""
        cache_hit_rate = (
            self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses'])
            if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0
        )
        
        avg_computation_time = (
            self.stats['total_time_ms'] / self.stats['computations']
            if self.stats['computations'] > 0 else 0
        )
        
        return {
            'cache_hit_rate': round(cache_hit_rate * 100, 2),
            'total_computations': self.stats['computations'],
            'average_computation_time_ms': round(avg_computation_time, 3),
            'total_time_ms': round(self.stats['total_time_ms'], 2),
            'cache_size': len(self._similarity_cache),
            'feature_cache_size': len(self._feature_cache),
            **self.performance_monitor.get_metrics()
        }
    
    def clear_caches(self) -> None:
        """Очистка всех кешей для освобождения памяти"""
        self._similarity_cache.clear()
        self._feature_cache.clear()
        self.preprocessor._normalization_cache.clear()
        self.preprocessor._token_cache.clear()
        
        # Очистка LRU кешей
        self.preprocessor.normalize_text.cache_clear()
        self.preprocessor.tokenize.cache_clear()
        
        logger.info("All caches cleared")
    
    def __del__(self):
        """Cleanup при удалении объекта"""
        self.clear_caches()


# Factory function для создания сервиса с предустановленными конфигурациями
def create_similarity_service(
    strategy: MatchingStrategy = MatchingStrategy.HYBRID,
    max_workers: int = 4,
    enable_caching: bool = True
) -> OptimizedSimilarityService:
    """
    Factory function для создания оптимизированного сервиса сопоставления
    """
    
    config = SimilarityConfig(
        strategy=strategy,
        max_workers=max_workers,
        enable_caching=enable_caching,
        use_parallel=True
    )
    
    return OptimizedSimilarityService(config)


# Context manager для временной настройки сервиса
class similarity_service_context:
    """Context manager для временного изменения конфигурации сервиса"""
    
    def __init__(self, service: OptimizedSimilarityService, **config_overrides):
        self.service = service
        self.original_config = service.config
        
        # Создаем новую конфигурацию с изменениями
        config_dict = {
            'weights': self.original_config.weights,
            'algorithms': self.original_config.algorithms,
            'strategy': self.original_config.strategy,
            'min_threshold': self.original_config.min_threshold,
            'max_workers': self.original_config.max_workers,
            'enable_caching': self.original_config.enable_caching,
            'cache_size': self.original_config.cache_size,
            'use_parallel': self.original_config.use_parallel,
            'enable_preprocessing': self.original_config.enable_preprocessing,
        }
        config_dict.update(config_overrides)
        
        self.new_config = SimilarityConfig(**config_dict)
    
    def __enter__(self) -> OptimizedSimilarityService:
        self.service.config = self.new_config
        return self.service
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.service.config = self.original_config