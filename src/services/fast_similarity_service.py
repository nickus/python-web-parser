"""
Быстрый сервис расчета похожести с кешированием и оптимизациями
"""

from typing import Dict, Any, Tuple, Optional, List
import re
import hashlib
from functools import lru_cache
from fuzzywuzzy import fuzz
import logging

from ..models.material import Material, PriceListItem

logger = logging.getLogger(__name__)


class FastSimilarityService:
    """
    Оптимизированный сервис для расчета похожести

    Ключевые оптимизации:
    1. Кеширование нормализованных текстов
    2. Упрощенные regex паттерны
    3. Ленивые вычисления
    4. Быстрый путь для очевидных случаев
    """

    def __init__(self):
        # Веса для расчета похожести
        self.weights = {
            'name': 0.60,
            'code': 0.25,
            'brand': 0.15
        }

        # Кеш для нормализованных текстов
        self._normalization_cache = {}
        self._max_cache_size = 10000

        # Счетчики для статистики
        self._cache_hits = 0
        self._cache_misses = 0

    def calculate_fast_similarity(self,
                                  material: Material,
                                  price_item: PriceListItem,
                                  use_cache: bool = True) -> Tuple[float, Dict[str, float]]:
        """
        Быстрый расчет похожести между материалом и элементом прайс-листа

        Оптимизации:
        - Быстрый путь для идентичных названий
        - Кеширование нормализации
        - Упрощенные алгоритмы сравнения
        """
        similarities = {}

        # Извлекаем и нормализуем тексты с кешированием
        material_name = self._get_normalized_cached(material.name or '', use_cache)
        price_name = self._get_normalized_cached(price_item.name or '', use_cache)

        # БЫСТРЫЙ ПУТЬ: Если нормализованные названия идентичны
        if material_name == price_name and material_name:
            return 100.0, {'name': 100.0, 'description': 100.0, 'brand': 100.0}

        # Расчет похожести названий (основной критерий)
        if material_name and price_name:
            name_sim = self._calculate_text_similarity_fast(material_name, price_name)
        else:
            name_sim = 0.0
        similarities['name'] = name_sim

        # Расчет похожести описаний - ВАЖНОЕ поле для технических характеристик
        # Временная отладка
        raw_mat_desc = material.description or ''
        raw_price_desc = price_item.description or ''

        material_desc = self._get_normalized_cached(raw_mat_desc, use_cache)
        price_desc = self._get_normalized_cached(raw_price_desc, use_cache)

        if material_desc and price_desc:
            desc_sim = self._calculate_text_similarity_fast(material_desc, price_desc)
        else:
            # Если нет description у одного из элементов - используем 0
            desc_sim = 0.0
            # Логирование для отладки
            if not material_desc and not price_desc:
                pass  # Оба пустые
            elif not material_desc:
                pass  # Нет description у материала
            elif not price_desc:
                pass  # Нет description у прайс-листа
        similarities['description'] = desc_sim

        # Расчет похожести брендов/производителей
        material_brand = material.manufacturer or material.brand or ''
        price_brand = price_item.brand or ''

        if material_brand and price_brand:
            brand_sim = self._calculate_brand_similarity_fast(material_brand, price_brand)
        else:
            brand_sim = 0.0
        similarities['brand'] = brand_sim

        # Динамическое перераспределение весов с учетом description
        weights = self._calculate_dynamic_weights_with_description(
            has_name=bool(material_name and price_name),
            has_description=bool(material_desc and price_desc),
            has_brand=bool(material_brand and price_brand)
        )

        # Общий процент похожести
        total_percentage = (
            similarities['name'] * weights['name'] +
            similarities['description'] * weights['description'] +
            similarities['brand'] * weights['brand']
        )

        return total_percentage, similarities

    def _get_normalized_cached(self, text: str, use_cache: bool) -> str:
        """Получение нормализованного текста с кешированием"""
        if not text:
            return ""

        # Создаем ключ для кеша
        cache_key = hashlib.md5(text.encode()).hexdigest()

        if use_cache and cache_key in self._normalization_cache:
            self._cache_hits += 1
            return self._normalization_cache[cache_key]

        self._cache_misses += 1

        # Нормализация
        normalized = self._normalize_text_fast(text)

        # Сохраняем в кеш если не превышен лимит
        if use_cache and len(self._normalization_cache) < self._max_cache_size:
            self._normalization_cache[cache_key] = normalized

        return normalized

    @lru_cache(maxsize=1024)
    def _normalize_text_fast(self, text: str) -> str:
        """
        Быстрая нормализация текста

        Упрощенная версия без сложных regex
        """
        if not text:
            return ""

        # Приводим к нижнему регистру
        text = text.lower()

        # Простая замена распространенных паттернов
        text = text.replace(',', '.')
        text = text.replace('х', 'x')  # Унификация размеров
        text = text.replace('×', 'x')
        text = text.replace('мм2', 'мм²')
        text = text.replace('кв.мм', 'мм²')

        # Удаляем лишние пробелы (простой подход)
        text = ' '.join(text.split())

        return text

    def _calculate_text_similarity_fast(self, text1: str, text2: str) -> float:
        """
        Быстрый расчет похожести текстов

        Использует только самые эффективные метрики
        """
        if not text1 or not text2:
            return 0.0

        if text1 == text2:
            return 100.0

        # Используем только два самых быстрых алгоритма
        ratio = fuzz.ratio(text1, text2)
        token_sort = fuzz.token_sort_ratio(text1, text2)

        # Простое усреднение
        return (ratio * 0.6 + token_sort * 0.4)

    def _calculate_code_similarity_fast(self, code1: str, code2: str) -> float:
        """Быстрое сравнение кодов"""
        if not code1 or not code2:
            return 0.0

        # Простая нормализация
        code1 = code1.upper().replace(' ', '')
        code2 = code2.upper().replace(' ', '')

        if code1 == code2:
            return 100.0

        # Проверка вхождения
        if code1 in code2 or code2 in code1:
            return 85.0

        # Простое fuzzy сравнение
        return fuzz.ratio(code1, code2)

    def _calculate_brand_similarity_fast(self, brand1: str, brand2: str) -> float:
        """Быстрое сравнение брендов"""
        if not brand1 or not brand2:
            return 0.0

        brand1 = brand1.lower().strip()
        brand2 = brand2.lower().strip()

        if brand1 == brand2:
            return 100.0

        # Частичное совпадение
        if brand1 in brand2 or brand2 in brand1:
            return 75.0

        return fuzz.ratio(brand1, brand2)

    def _calculate_dynamic_weights(self,
                                   has_name: bool,
                                   has_code: bool,
                                   has_brand: bool) -> Dict[str, float]:
        """
        Динамическое перераспределение весов

        Если какое-то поле отсутствует, его вес распределяется между остальными
        """
        weights = self.weights.copy()

        # Подсчет активных полей
        active_fields = sum([has_name, has_code, has_brand])

        if active_fields == 0:
            return {'name': 0, 'code': 0, 'brand': 0}

        if active_fields == 1:
            # Все 100% на единственное поле
            if has_name:
                return {'name': 1.0, 'code': 0, 'brand': 0}
            elif has_code:
                return {'name': 0, 'code': 1.0, 'brand': 0}
            else:
                return {'name': 0, 'code': 0, 'brand': 1.0}

        # Перераспределение весов
        if not has_name:
            weights['code'] += weights['name'] * 0.6
            weights['brand'] += weights['name'] * 0.4
            weights['name'] = 0

        if not has_code:
            weights['name'] += weights['code'] * 0.7
            weights['brand'] += weights['code'] * 0.3
            weights['code'] = 0

        if not has_brand:
            weights['name'] += weights['brand'] * 0.7
            weights['code'] += weights['brand'] * 0.3
            weights['brand'] = 0

        return weights

    def _calculate_dynamic_weights_with_description(self,
                                                    has_name: bool,
                                                    has_description: bool,
                                                    has_brand: bool) -> Dict[str, float]:
        """
        Динамический расчет весов с учетом description

        Адаптивная стратегия:
        - Название - основной критерий (40-60%)
        - Описание - важно для технических деталей (20-40%)
        - Бренд - дополнительный критерий (10-20%)
        """
        if has_name and has_description and has_brand:
            # Все поля доступны - оптимальное распределение
            return {
                'name': 0.50,           # Основной критерий
                'description': 0.30,    # Технические характеристики
                'brand': 0.20           # Производитель
            }
        elif has_name and has_description:
            # Нет бренда
            return {'name': 0.60, 'description': 0.40, 'brand': 0.0}
        elif has_name and has_brand:
            # Нет описания
            return {'name': 0.70, 'description': 0.0, 'brand': 0.30}
        elif has_description and has_brand:
            # Нет названия (редкий случай)
            return {'name': 0.0, 'description': 0.70, 'brand': 0.30}
        elif has_name:
            # Только название
            return {'name': 1.0, 'description': 0.0, 'brand': 0.0}
        elif has_description:
            # Только описание
            return {'name': 0.0, 'description': 1.0, 'brand': 0.0}
        elif has_brand:
            # Только бренд
            return {'name': 0.0, 'description': 0.0, 'brand': 1.0}
        else:
            # Нет полей для сравнения - равное распределение
            return {'name': 0.34, 'description': 0.33, 'brand': 0.33}

    def batch_calculate_similarities(self,
                                     material: Material,
                                     price_items: List[PriceListItem],
                                     threshold: float = 0.0) -> List[Tuple[PriceListItem, float, Dict]]:
        """
        Пакетный расчет похожести для списка элементов

        Оптимизирован для обработки множества элементов
        """
        results = []

        # Предварительно нормализуем материал (один раз)
        material_name_norm = self._get_normalized_cached(material.name or '', True)
        material_code = material.equipment_code or ''
        material_brand = material.manufacturer or material.brand or ''

        for price_item in price_items:
            # Быстрая проверка на минимальное совпадение
            price_name_norm = self._get_normalized_cached(price_item.name or '', True)

            # Пропускаем если нет минимального совпадения
            if material_name_norm and price_name_norm:
                # Быстрая проверка на наличие общих слов
                material_words = set(material_name_norm.split())
                price_words = set(price_name_norm.split())

                if not material_words & price_words:
                    # Нет общих слов - пропускаем
                    continue

            # Полный расчет similarity
            similarity, details = self.calculate_fast_similarity(material, price_item, True)

            if similarity >= threshold:
                results.append((price_item, similarity, details))

        # Сортируем по убыванию похожести
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def clear_cache(self):
        """Очистка кеша"""
        self._normalization_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кеша"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cache_size': len(self._normalization_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate,
            'max_cache_size': self._max_cache_size
        }