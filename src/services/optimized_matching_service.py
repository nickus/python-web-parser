"""
Оптимизированный сервис сопоставления материалов
Правильно использует Elasticsearch для поиска и ранжирования
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.material import Material, PriceListItem, SearchResult
from ..services.elasticsearch_service import ElasticsearchService
from ..services.similarity_service import SimilarityService


logger = logging.getLogger(__name__)


class OptimizedMatchingService:
    """
    Оптимизированный сервис для сопоставления материалов

    Ключевые улучшения:
    1. НЕТ bypass mode - всегда используем Elasticsearch
    2. Elasticsearch делает предварительную фильтрацию и ранжирование
    3. Детальный расчет similarity только для топ-N результатов
    4. Кеширование результатов нормализации текста
    """

    def __init__(self,
                 elasticsearch_service: ElasticsearchService,
                 similarity_service: SimilarityService):
        """
        Инициализация сервиса

        Args:
            elasticsearch_service: Сервис Elasticsearch
            similarity_service: Сервис расчета похожести
        """
        self.es_service = elasticsearch_service
        self.similarity_service = similarity_service

        # Кеш для нормализованных текстов (ускоряет повторные расчеты)
        self._normalized_text_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info("OptimizedMatchingService initialized")

    def match_material_with_price_list(self,
                                       material: Material,
                                       similarity_threshold: float = 20.0,
                                       max_results: int = 10,
                                       es_top_n: int = 20) -> List[SearchResult]:
        """
        ОПТИМИЗИРОВАННЫЙ поиск соответствий для материала в прайс-листе

        Алгоритм:
        1. Elasticsearch возвращает топ-N релевантных результатов (es_top_n)
        2. Для этих результатов вычисляется детальная similarity
        3. Фильтрация по threshold и сортировка по similarity
        4. Возврат max_results лучших результатов

        Args:
            material: Материал для поиска
            similarity_threshold: Минимальный процент похожести
            max_results: Максимальное количество результатов
            es_top_n: Количество результатов из Elasticsearch для детального анализа

        Returns:
            Список результатов поиска с процентом похожести
        """
        start_time = time.time()
        results = []

        # Отладка: проверяем description материала в самом начале
        logger.info(f"match_material_with_price_list called with material.description: {material.description}")

        # Формируем оптимальный поисковый запрос
        query = self._build_optimized_query(material)

        if not query.strip():
            logger.warning(f"Empty query for material {material.id}")
            return results

        try:
            # ШАГ 1: Быстрый поиск в Elasticsearch
            # Запрашиваем больше результатов чем нужно для последующей фильтрации
            es_start = time.time()
            # Используем правильный метод в зависимости от типа сервиса
            if hasattr(self.es_service, 'search_price_list_optimized'):
                es_results = self.es_service.search_price_list_optimized(query, size=es_top_n)
            else:
                es_results = self.es_service.search_price_list(query, size=es_top_n)
            es_time = time.time() - es_start

            logger.info(f"Elasticsearch returned {len(es_results)} results in {es_time:.3f}s")

            if not es_results:
                return results

            # ШАГ 2: Детальный расчет similarity только для топ результатов
            sim_start = time.time()

            for es_result in es_results:
                try:
                    # Создаем объект PriceListItem
                    price_item_data = es_result['_source']
                    price_item = PriceListItem.from_dict(price_item_data)

                    # Рассчитываем детальную похожесть
                    similarity_percentage, similarity_details = self._calculate_similarity_cached(
                        material, price_item
                    )

                    # Фильтруем по порогу
                    if similarity_percentage >= similarity_threshold:
                        # Комбинируем ES score и similarity для лучшего ранжирования
                        es_score = es_result.get('_score', 0)

                        # Временная отладка перед созданием SearchResult
                        if not hasattr(material, 'description'):
                            logger.error(f"Material has no description attribute!")
                        elif material.description is None:
                            logger.warning(f"Material description is None for: {material.name}")
                        else:
                            logger.debug(f"Material has description: {material.description[:50]}")

                        search_result = SearchResult(
                            material=material,
                            price_item=price_item,
                            similarity_percentage=similarity_percentage,
                            similarity_details=similarity_details,
                            elasticsearch_score=es_score
                        )
                        results.append(search_result)

                except Exception as e:
                    logger.error(f"Error processing price list item: {e}")
                    continue

            sim_time = time.time() - sim_start
            logger.info(f"Similarity calculation for {len(es_results)} items in {sim_time:.3f}s")

            # ШАГ 3: Сортировка по комбинированному score
            results = self._sort_by_combined_score(results)

            # ШАГ 4: Ограничение количества результатов
            results = results[:max_results]

            total_time = time.time() - start_time
            logger.info(
                f"Total matching time: {total_time:.3f}s "
                f"(ES: {es_time:.3f}s, Similarity: {sim_time:.3f}s) "
                f"Cache hits: {self._cache_hits}, misses: {self._cache_misses}"
            )

        except Exception as e:
            logger.error(f"Error matching material {material.id}: {e}")

        return results

    def _build_optimized_query(self, material: Material) -> str:
        """
        Построение оптимизированного запроса для Elasticsearch

        Учитывает:
        - Название материала (высший приоритет)
        - Код оборудования
        - Производителя
        - Тип/марку
        """
        query_parts = []

        # Название - самый важный элемент
        if material.name:
            query_parts.append(material.name)

        # Добавляем код оборудования если есть и он отличается от названия
        if material.equipment_code and material.equipment_code not in (material.name or ''):
            query_parts.append(material.equipment_code)

        # Добавляем производителя для точности
        if material.manufacturer:
            # Но не дублируем если уже есть в названии
            if material.manufacturer not in (material.name or ''):
                query_parts.append(material.manufacturer)

        return ' '.join(query_parts)

    def _calculate_similarity_cached(self,
                                     material: Material,
                                     price_item: PriceListItem) -> Tuple[float, Dict[str, float]]:
        """
        Расчет similarity с кешированием промежуточных результатов
        """
        # Создаем ключи для кеша
        material_key = f"mat_{material.id}_{material.name}"
        price_key = f"price_{price_item.id}_{price_item.name}"

        # Проверяем кеш для пары
        cache_key = f"{material_key}_{price_key}"
        if cache_key in self._normalized_text_cache:
            self._cache_hits += 1
            return self._normalized_text_cache[cache_key]

        self._cache_misses += 1

        # Вычисляем similarity с правильным методом
        if hasattr(self.similarity_service, 'calculate_fast_similarity'):
            similarity, details = self.similarity_service.calculate_fast_similarity(
                material, price_item, True
            )
        else:
            similarity, details = self.similarity_service.calculate_new_material_similarity(
                material, price_item
            )

        # Кешируем результат (ограничиваем размер кеша)
        if len(self._normalized_text_cache) < 1000:
            self._normalized_text_cache[cache_key] = (similarity, details)

        return similarity, details

    def _sort_by_combined_score(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Сортировка по комбинированному score

        Учитывает:
        - Similarity percentage (70% веса)
        - Elasticsearch score (30% веса)
        """
        def combined_score(result: SearchResult) -> float:
            # Нормализуем ES score (обычно от 0 до ~10)
            normalized_es_score = min(result.elasticsearch_score / 10.0, 1.0) * 100

            # Комбинированный score
            return (result.similarity_percentage * 0.7 + normalized_es_score * 0.3)

        return sorted(results, key=combined_score, reverse=True)

    def match_materials_batch(self,
                              materials: List[Material],
                              similarity_threshold: float = 20.0,
                              max_results_per_material: int = 5,
                              max_workers: int = 4,
                              progress_callback=None) -> Dict[str, List[SearchResult]]:
        """
        Пакетное сопоставление материалов

        Оптимизировано для параллельной обработки
        """
        results = {}
        completed_count = 0
        total_count = len(materials)

        logger.info(f"Starting batch matching for {total_count} materials")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Запускаем задачи
            future_to_material = {
                executor.submit(
                    self.match_material_with_price_list,
                    material,
                    similarity_threshold,
                    max_results_per_material,
                    20  # es_top_n - берем топ-20 из ES для анализа
                ): material for material in materials
            }

            # Собираем результаты по мере готовности
            for future in as_completed(future_to_material):
                material = future_to_material[future]
                try:
                    material_results = future.result()
                    results[material.id] = material_results
                    completed_count += 1

                    # Обновляем прогресс
                    if progress_callback:
                        progress_callback(completed_count, total_count, material.name)

                    # Логируем прогресс каждые 10%
                    if completed_count % max(1, total_count // 10) == 0:
                        elapsed = time.time() - start_time
                        rate = completed_count / elapsed if elapsed > 0 else 0
                        eta = (total_count - completed_count) / rate if rate > 0 else 0
                        logger.info(
                            f"Progress: {completed_count}/{total_count} "
                            f"({completed_count/total_count*100:.1f}%) "
                            f"Rate: {rate:.1f} materials/sec, ETA: {eta:.1f}s"
                        )

                except Exception as e:
                    logger.error(f"Error processing material {material.id}: {e}")
                    results[material.id] = []

        total_time = time.time() - start_time
        logger.info(
            f"Batch matching completed in {total_time:.2f}s "
            f"({total_count/total_time:.1f} materials/sec)"
        )

        return results

    def search_material_by_name(self,
                                material_name: str,
                                top_n: int = 5,
                                similarity_threshold: float = 10.0) -> List[Dict[str, Any]]:
        """
        Быстрый поиск материала по названию

        Оптимизирован для интерактивного использования
        """
        # Создаем временный материал для поиска
        temp_material = Material(
            id="search_temp",
            name=material_name,
            description=None,  # Не дублируем название - description должен браться из прайс-листа
            # Пытаемся извлечь дополнительную информацию из названия
            manufacturer=None,
            equipment_code=None
        )

        # Используем оптимизированный поиск
        matches = self.match_material_with_price_list(
            temp_material,
            similarity_threshold=similarity_threshold,
            max_results=top_n,
            es_top_n=top_n * 2  # Берем в 2 раза больше из ES для лучшей фильтрации
        )

        # Конвертируем в словари для API
        return [match.to_dict() for match in matches]

    def clear_cache(self):
        """Очистка кеша нормализованных текстов"""
        self._normalized_text_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Получение статистики кеша"""
        return {
            'cache_size': len(self._normalized_text_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': (self._cache_hits / (self._cache_hits + self._cache_misses) * 100)
                        if (self._cache_hits + self._cache_misses) > 0 else 0
        }