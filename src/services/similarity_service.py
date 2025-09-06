from typing import List, Dict, Any, Tuple
import re
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz
import logging

from ..models.material import Material, PriceListItem, SearchResult


logger = logging.getLogger(__name__)


class SimilarityService:
    """Сервис для расчета похожести между материалами и элементами прайс-листа"""
    
    def __init__(self):
        self.weights = {
            'name': 0.4,
            'description': 0.2,
            'category': 0.15,
            'brand': 0.15,
            'specifications': 0.1
        }
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет похожести между двумя текстами
        Использует комбинацию различных метрик
        """
        if not text1 or not text2:
            return 0.0
        
        # Нормализация текстов
        text1_clean = self._normalize_text(text1)
        text2_clean = self._normalize_text(text2)
        
        if text1_clean == text2_clean:
            return 1.0
        
        # Различные метрики похожести
        ratio = fuzz.ratio(text1_clean, text2_clean) / 100.0
        partial_ratio = fuzz.partial_ratio(text1_clean, text2_clean) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(text1_clean, text2_clean) / 100.0
        token_set_ratio = fuzz.token_set_ratio(text1_clean, text2_clean) / 100.0
        
        # Sequence matcher для дополнительной точности
        sequence_ratio = SequenceMatcher(None, text1_clean, text2_clean).ratio()
        
        # Взвешенное среднее
        combined_score = (
            ratio * 0.25 +
            partial_ratio * 0.15 +
            token_sort_ratio * 0.25 +
            token_set_ratio * 0.25 +
            sequence_ratio * 0.1
        )
        
        return min(combined_score, 1.0)
    
    def calculate_category_similarity(self, cat1: str, cat2: str) -> float:
        """Расчет похожести категорий"""
        if not cat1 or not cat2:
            return 0.0
        
        cat1_clean = self._normalize_text(cat1)
        cat2_clean = self._normalize_text(cat2)
        
        if cat1_clean == cat2_clean:
            return 1.0
        
        # Проверка на вхождение одной категории в другую
        if cat1_clean in cat2_clean or cat2_clean in cat1_clean:
            return 0.8
        
        # Обычное сравнение текстов
        return self.calculate_text_similarity(cat1, cat2)
    
    def calculate_brand_similarity(self, brand1: str, brand2: str) -> float:
        """Расчет похожести брендов"""
        if not brand1 or not brand2:
            return 0.0
        
        brand1_clean = self._normalize_text(brand1)
        brand2_clean = self._normalize_text(brand2)
        
        if brand1_clean == brand2_clean:
            return 1.0
        
        # Бренды должны совпадать более точно
        ratio = fuzz.ratio(brand1_clean, brand2_clean) / 100.0
        
        # Дополнительный бонус для частичного совпадения
        if brand1_clean in brand2_clean or brand2_clean in brand1_clean:
            ratio = max(ratio, 0.7)
        
        return ratio
    
    def calculate_specifications_similarity(self, specs1: Dict[str, Any], specs2: Dict[str, Any]) -> float:
        """Расчет похожести спецификаций"""
        if not specs1 or not specs2:
            return 0.0
        
        common_keys = set(specs1.keys()) & set(specs2.keys())
        if not common_keys:
            return 0.0
        
        total_similarity = 0.0
        compared_count = 0
        
        for key in common_keys:
            val1 = str(specs1[key]).lower().strip()
            val2 = str(specs2[key]).lower().strip()
            
            if val1 == val2:
                total_similarity += 1.0
            else:
                # Для числовых значений
                try:
                    num1 = float(val1)
                    num2 = float(val2)
                    # Считаем похожими числа с разницей до 10%
                    diff_percentage = abs(num1 - num2) / max(num1, num2) if max(num1, num2) > 0 else 0
                    if diff_percentage <= 0.1:
                        total_similarity += 0.9
                    elif diff_percentage <= 0.2:
                        total_similarity += 0.7
                    else:
                        total_similarity += max(0, 1.0 - diff_percentage)
                except ValueError:
                    # Для текстовых значений
                    text_sim = self.calculate_text_similarity(val1, val2)
                    total_similarity += text_sim
            
            compared_count += 1
        
        return total_similarity / compared_count if compared_count > 0 else 0.0
    
    def calculate_material_similarity(self, material: Material, price_item: PriceListItem) -> Tuple[float, Dict[str, float]]:
        """
        Расчет общей похожести между материалом и элементом прайс-листа
        
        Returns:
            Tuple[float, Dict[str, float]]: Общий процент похожести и детали по каждому параметру
        """
        similarities = {}
        
        # Похожесть названий
        name_sim = self.calculate_text_similarity(material.name, price_item.material_name)
        similarities['name'] = name_sim
        
        # Похожесть описаний
        desc_sim = self.calculate_text_similarity(material.description, price_item.description)
        similarities['description'] = desc_sim
        
        # Похожесть категорий
        category_sim = self.calculate_category_similarity(
            material.category or '', 
            price_item.category or ''
        )
        similarities['category'] = category_sim
        
        # Похожесть брендов
        brand_sim = self.calculate_brand_similarity(
            material.brand or '', 
            price_item.brand or ''
        )
        similarities['brand'] = brand_sim
        
        # Похожесть спецификаций
        specs_sim = self.calculate_specifications_similarity(
            material.specifications or {},
            price_item.specifications or {}
        )
        similarities['specifications'] = specs_sim
        
        # Проверяем, идентичны ли основные поля (название, описание, категория)
        core_fields_identical = (
            similarities['name'] >= 0.99 and
            similarities['description'] >= 0.99 and
            similarities['category'] >= 0.99
        )
        
        # Если основные поля идентичны, считаем это 100% совпадением
        if core_fields_identical:
            total_similarity = 1.0
        else:
            # Стандартный расчет с учетом весов
            weighted_sum = 0.0
            total_weight = 0.0
            
            # Учитываем только поля, которые есть у хотя бы одного из сравниваемых объектов
            for field, similarity in similarities.items():
                weight = self.weights[field]
                
                # Пропускаем поля, которые отсутствуют у обоих объектов
                if field == 'brand':
                    has_material_brand = material.brand is not None and material.brand.strip()
                    has_price_brand = price_item.brand is not None and price_item.brand.strip()
                    if not has_material_brand and not has_price_brand:
                        continue  # Пропускаем поле, если бренды отсутствуют у обоих
                    elif not has_material_brand or not has_price_brand:
                        # Если бренд есть только у одного - не штрафуем сильно
                        similarity = 0.8
                elif field == 'specifications':
                    has_material_specs = material.specifications and len(material.specifications) > 0
                    has_price_specs = price_item.specifications and len(price_item.specifications) > 0
                    if not has_material_specs and not has_price_specs:
                        continue  # Пропускаем поле, если спецификации отсутствуют у обоих
                    elif not has_material_specs or not has_price_specs:
                        # Если спецификации есть только у одного - не штрафуем сильно
                        similarity = 0.8
                
                weighted_sum += similarity * weight
                total_weight += weight
            
            # Если нет веса, возвращаем 0
            if total_weight == 0:
                total_similarity = 0.0
            else:
                # Нормализуем на общий вес используемых полей
                total_similarity = weighted_sum / total_weight
        
        # Конвертация в проценты
        total_percentage = total_similarity * 100
        detail_percentages = {k: v * 100 for k, v in similarities.items()}
        
        return total_percentage, detail_percentages
    
    def _normalize_text(self, text: str) -> str:
        """Нормализация текста для сравнения"""
        if not text:
            return ""
        
        # Приведение к нижнему регистру
        text = text.lower()
        
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Удаление специальных символов (кроме букв, цифр, пробелов и некоторых знаков)
        text = re.sub(r'[^\w\s\-.,()]', '', text)
        
        return text
    
    def filter_by_similarity_threshold(self, 
                                       results: List[SearchResult], 
                                       threshold: float = 30.0) -> List[SearchResult]:
        """
        Фильтрация результатов по минимальному проценту похожести
        
        Args:
            results: Список результатов поиска
            threshold: Минимальный процент похожести (по умолчанию 30%)
        
        Returns:
            Отфильтрованный список результатов
        """
        return [result for result in results if result.similarity_percentage >= threshold]
    
    def sort_by_similarity(self, results: List[SearchResult], 
                           reverse: bool = True) -> List[SearchResult]:
        """
        Сортировка результатов по проценту похожести
        
        Args:
            results: Список результатов поиска
            reverse: True для сортировки по убыванию (лучшие результаты первыми)
        
        Returns:
            Отсортированный список результатов
        """
        return sorted(results, key=lambda x: x.similarity_percentage, reverse=reverse)
    
    def get_top_matches(self, results: List[SearchResult], 
                        top_n: int = 10) -> List[SearchResult]:
        """
        Получение топ N лучших совпадений
        
        Args:
            results: Список результатов поиска
            top_n: Количество лучших результатов для возврата
        
        Returns:
            Топ N результатов
        """
        sorted_results = self.sort_by_similarity(results)
        return sorted_results[:top_n]