from typing import List, Dict, Any, Tuple
import re
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz
import logging
import unicodedata

from ..models.material import Material, PriceListItem, SearchResult
from ..utils.debug_logger import get_debug_logger


logger = logging.getLogger(__name__)


class SimilarityService:
    """Сервис для расчета похожести между материалами и элементами прайс-листа"""

    def __init__(self):
        # Старые веса для обратной совместимости
        self.weights = {
            'name': 0.4,
            'description': 0.2,
            'category': 0.15,
            'brand': 0.15,
            'specifications': 0.1
        }

        # Новые веса по приоритетам:
        # ИСПРАВЛЕНО: Уменьшаем вес названия чтобы предотвратить ложные 100%
        self.new_weights = {
            'name_similarity': 0.50,  # Уменьшено с 0.70
            'article_similarity': 0.30,  # Увеличено с 0.20
            'brand_similarity': 0.20,  # Увеличено с 0.10
        }

        # УЛУЧШЕННЫЕ паттерны для извлечения числовых диапазонов и размеров
        self.numeric_patterns = [
            # Размеры кабелей с x/х/× (важно извлечь ДО нормализации)
            r'(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)',  # 3x2.5, 3х1.5
            # Диапазоны
            r'(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*([а-яА-Яa-zA-Z]*)',  # 40-95А
            # Характеристики автоматов
            r'[CСcс]\s*(\d+)',  # C16, С25
            # Единицы с числами
            r'(\d+(?:[.,]\d+)?)\s*(мм²?|а|в|вт|w|кв\.?мм)',  # 2.5мм²
        ]

        # Инициализируем отладочный логгер
        self.debug_logger = get_debug_logger()

        # ИСПРАВЛЕНО: НЕ заменяем x на х глобально!
        # Удаляем замену x->х из словаря, чтобы сохранить различия в размерах
        self.char_replacements = {
            # Убираем замену x -> х (это критично для размеров!)
            # 'x': 'х', 'X': 'Х',  # УДАЛЕНО!
            'p': 'р', 'P': 'Р',
            'c': 'с', 'C': 'С',
            'o': 'о', 'O': 'О',
            'a': 'а', 'A': 'А',
            'e': 'е', 'E': 'Е',
            'y': 'у', 'Y': 'У',
            'T': 'Т', 'H': 'Н', 'K': 'К', 'M': 'М', 'B': 'В'
        }

        # Словарь синонимов для материалов
        base_synonyms = {
            'led': 'светодиодный',
            'автомат': 'выключатель',
            'выключатель': 'автомат',
            'мм2': 'мм²',
            'кв.мм': 'мм²',
            'квадратных': 'мм²',
            'вт': 'w',
            'ватт': 'w'
        }

        # Словарь синонимичных конструкций для нормализации порядка слов
        self.word_order_patterns = {
            ('канал', 'кабельный'): 'кабельный канал',
            ('кабельный', 'канал'): 'кабельный канал',
            ('выключатель', 'автоматический'): 'автоматический выключатель',
            ('автоматический', 'выключатель'): 'автоматический выключатель',
            ('лампа', 'светодиодная'): 'светодиодная лампа',
            ('светодиодная', 'лампа'): 'светодиодная лампа',
        }

        # Создаем двунаправленный словарь синонимов
        self.synonyms_dict = {}
        for key, value in base_synonyms.items():
            self.synonyms_dict[key] = value
            self.synonyms_dict[value] = key

        # Паттерны для нормализации единиц измерения
        self.unit_patterns = [
            # Нормализация размеров кабелей (сохраняем x/х различия)
            (r'(\d+)\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*(?:мм2?|мм²|кв\.?мм)', r'\1x\2мм²'),
            (r'(\d+(?:[.,]\d+)?)\s*(?:мм2|кв\.?мм)', r'\1мм²'),
            # Нормализация мощности
            (r'(\d+(?:[.,]\d+)?)\s*(?:вт|ватт|w)', r'\1вт'),
            # Нормализация тока и напряжения
            (r'(\d+(?:[.,]\d+)?)\s*(?:а|ампер)', r'\1а'),
            (r'(\d+(?:[.,]\d+)?)\s*(?:в|вольт)', r'\1в'),
        ]

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет похожести между двумя текстами
        ИСПРАВЛЕНО: Добавлена проверка числовой совместимости
        """
        if not text1 or not text2:
            return 0.0

        # НОВОЕ: Сначала проверяем числовую совместимость
        numeric_compatible = self._check_numeric_compatibility(text1, text2)

        # Нормализация текстов
        text1_clean = self._normalize_text(text1)
        text2_clean = self._normalize_text(text2)

        if text1_clean == text2_clean:
            # Даже при полном совпадении проверяем числовую совместимость
            if not numeric_compatible:
                return 70.0  # Снижаем оценку если числа не совместимы
            return 100.0

        # Семантическая схожесть
        semantic_sim = self._calculate_semantic_similarity(text1, text2)

        # Различные метрики похожести
        ratio = fuzz.ratio(text1_clean, text2_clean) / 100.0
        partial_ratio = fuzz.partial_ratio(text1_clean, text2_clean) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(text1_clean, text2_clean) / 100.0
        token_set_ratio = fuzz.token_set_ratio(text1_clean, text2_clean) / 100.0

        # Sequence matcher для дополнительной точности
        sequence_ratio = SequenceMatcher(None, text1_clean, text2_clean).ratio()

        # Взвешенное среднее
        combined_score = (
            ratio * 0.15 +
            partial_ratio * 0.15 +
            token_sort_ratio * 0.25 +
            token_set_ratio * 0.25 +
            sequence_ratio * 0.05 +
            semantic_sim * 0.15
        )

        result = min(combined_score * 100, 100.0)

        # НОВОЕ: Применяем штраф за числовую несовместимость
        if not numeric_compatible:
            result = min(result * 0.7, 70.0)  # Максимум 70% при несовместимости

        return result

    def calculate_category_similarity(self, cat1: str, cat2: str) -> float:
        """Расчет похожести категорий"""
        if not cat1 or not cat2:
            return 0.0

        cat1_clean = self._normalize_text(cat1)
        cat2_clean = self._normalize_text(cat2)

        if cat1_clean == cat2_clean:
            return 100.0

        # Проверка на вхождение одной категории в другую
        if cat1_clean in cat2_clean or cat2_clean in cat1_clean:
            return 85.0

        # Обычное сравнение текстов
        return self.calculate_text_similarity(cat1, cat2)

    def calculate_brand_similarity(self, brand1: str, brand2: str) -> float:
        """Расчет похожести брендов"""
        if not brand1 or not brand2:
            return 0.0

        brand1_clean = self._normalize_text(brand1)
        brand2_clean = self._normalize_text(brand2)

        if brand1_clean == brand2_clean:
            return 100.0

        # Бренды должны совпадать более точно
        ratio = fuzz.ratio(brand1_clean, brand2_clean)

        # Дополнительный бонус для частичного совпадения
        if brand1_clean in brand2_clean or brand2_clean in brand1_clean:
            ratio = max(ratio, 75.0)

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
                total_similarity += 100.0
            else:
                # Для числовых значений
                try:
                    num1 = float(val1)
                    num2 = float(val2)
                    # Считаем похожими числа с разницей до 10%
                    diff_percentage = abs(num1 - num2) / max(num1, num2) if max(num1, num2) > 0 else 0
                    if diff_percentage <= 0.1:
                        total_similarity += 90.0
                    elif diff_percentage <= 0.2:
                        total_similarity += 70.0
                    else:
                        total_similarity += max(0, 100.0 * (1.0 - diff_percentage))
                except ValueError:
                    # Для текстовых значений
                    text_sim = self.calculate_text_similarity(val1, val2)
                    total_similarity += text_sim

            compared_count += 1

        return total_similarity / compared_count if compared_count > 0 else 0.0

    def calculate_material_similarity(self, material: Material, price_item: PriceListItem) -> Tuple[float, Dict[str, float]]:
        """
        Расчет общей похожести между материалом и элементом прайс-листа
        ИСПРАВЛЕНО: Более строгая проверка для 100% совпадений
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

        # КРИТИЧНО: Проверка числовой совместимости для предотвращения ложных 100%
        numeric_compatible = self._check_numeric_compatibility(
            material.name, price_item.material_name
        )

        # Проверяем высокую схожесть основных полей
        name_very_similar = similarities['name'] >= 90.0
        description_similar = similarities['description'] >= 75.0 or not material.description or not price_item.description
        category_similar = similarities['category'] >= 85.0 or not material.category or not price_item.category

        # Нормализованные названия
        normalized_material_name = self._normalize_text(material.name)
        normalized_price_name = self._normalize_text(price_item.material_name)
        exact_match = normalized_material_name == normalized_price_name

        # ИСПРАВЛЕНО: Более строгие условия для 100% совпадения
        if exact_match and numeric_compatible and name_very_similar:
            total_similarity = 1.0
        elif name_very_similar and description_similar and category_similar and numeric_compatible:
            total_similarity = 0.95  # Максимум 95% без точного совпадения
        else:
            # Стандартный расчет с учетом весов
            weighted_sum = 0.0
            total_weight = 0.0

            for field, similarity in similarities.items():
                weight = self.weights[field]

                # Пропускаем отсутствующие поля
                if field == 'brand':
                    has_material_brand = material.brand is not None and material.brand.strip()
                    has_price_brand = price_item.brand is not None and price_item.brand.strip()
                    if not has_material_brand and not has_price_brand:
                        continue
                elif field == 'specifications':
                    has_material_specs = material.specifications and len(material.specifications) > 0
                    has_price_specs = price_item.specifications and len(price_item.specifications) > 0
                    if not has_material_specs and not has_price_specs:
                        continue

                weighted_sum += similarity * weight
                total_weight += weight

            if total_weight == 0:
                total_similarity = 0.0
            else:
                total_similarity = weighted_sum / total_weight

                # ДОПОЛНИТЕЛЬНАЯ КОРРЕКТИРОВКА: Снижаем оценку если числовые значения не совместимы
                if not numeric_compatible:
                    total_similarity *= 0.6  # Существенное снижение за несовместимость чисел

        # Конвертация в проценты
        total_percentage = total_similarity * 100
        detail_percentages = {k: v for k, v in similarities.items()}

        return total_percentage, detail_percentages

    def calculate_new_material_similarity(self, material: Material, price_item: PriceListItem) -> Tuple[float, Dict[str, float]]:
        """
        Новый алгоритм расчета похожести по приоритетам
        ИСПРАВЛЕНО: Более точное сопоставление с учетом числовых значений
        """
        similarities = {}

        # 1. Приоритет 1: Наименования vs name
        material_name = material.name or ''
        price_name = price_item.name or ''
        name_sim = self.calculate_text_similarity(material_name, price_name)
        similarities['name_similarity'] = name_sim

        # 2. Приоритет 2: Код обор. vs article
        material_code = material.equipment_code or ''
        price_article = price_item.article or ''
        article_sim = self.calculate_code_similarity(material_code, price_article)
        similarities['article_similarity'] = article_sim

        # 3. Приоритет 3: Завод изг. vs brand
        material_manufacturer = material.manufacturer or ''
        price_brand = price_item.brand or ''
        brand_sim = self.calculate_brand_similarity(material_manufacturer, price_brand)
        similarities['brand_similarity'] = brand_sim

        # ИСПРАВЛЕНО: Проверка числовой совместимости
        numeric_compatible = self._check_numeric_compatibility(material_name, price_name)

        # Проверяем наличие данных
        has_article = bool(material_code.strip() and price_article.strip())
        has_brand = bool(material_manufacturer.strip() and price_brand.strip())

        # ИСПРАВЛЕНО: Более сбалансированное распределение весов
        if not has_article and not has_brand:
            # Только название - но с проверкой чисел
            name_weight = 1.0
            article_weight = 0.0
            brand_weight = 0.0
        elif not has_article:
            # Нет артикула - вес распределяется между названием и брендом
            name_weight = 0.70
            article_weight = 0.0
            brand_weight = 0.30
        elif not has_brand:
            # Нет бренда - вес распределяется между названием и артикулом
            name_weight = 0.60
            article_weight = 0.40
            brand_weight = 0.0
        else:
            # Все данные есть - используем базовые веса
            name_weight = self.new_weights['name_similarity']
            article_weight = self.new_weights['article_similarity']
            brand_weight = self.new_weights['brand_similarity']

        # Расчет общей похожести
        total_percentage = (
            similarities['name_similarity'] * name_weight +
            similarities['article_similarity'] * article_weight +
            similarities['brand_similarity'] * brand_weight
        )

        # КРИТИЧНО: Применяем штраф за числовую несовместимость
        if not numeric_compatible and total_percentage > 50:
            # Если числа не совпадают, но общая похожесть высокая - снижаем
            total_percentage = min(total_percentage * 0.7, 70.0)
            logger.info(f"[PENALTY] Числовая несовместимость: '{material_name}' vs '{price_name}' -> {total_percentage:.1f}%")

        return total_percentage, similarities

    def calculate_code_similarity(self, code1: str, code2: str) -> float:
        """
        Специальный метод для сравнения кодов/артикулов
        """
        if not code1 or not code2:
            return 0.0

        # Нормализация кодов
        norm_code1 = re.sub(r'\s+', '', code1.upper())
        norm_code2 = re.sub(r'\s+', '', code2.upper())

        # Точное совпадение
        if norm_code1 == norm_code2:
            return 100.0

        # Проверка на вхождение одного кода в другой
        if norm_code1 in norm_code2 or norm_code2 in norm_code1:
            return 85.0

        # Используем стандартное текстовое сравнение для остальных случаев
        return fuzz.ratio(norm_code1, norm_code2)

    def _normalize_text(self, text: str) -> str:
        """
        ИСПРАВЛЕННАЯ нормализация текста для сравнения
        КРИТИЧНО: НЕ заменяем x на х для сохранения различий в размерах!
        """
        if not text:
            return ""

        # Unicode нормализация
        text = unicodedata.normalize('NFC', text)

        # ВАЖНО: Сначала извлекаем числовые значения ДО любых замен
        # Это позволит правильно различать 3x1.5 и 3х2.5

        # Замена визуально похожих символов (БЕЗ замены x!)
        for lat_char, cyr_char in self.char_replacements.items():
            text = text.replace(lat_char, cyr_char)

        # Приведение к нижнему регистру
        text = text.lower()

        # Нормализация единиц измерения
        for pattern, replacement in self.unit_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Замена запятых на точки в числах
        text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)

        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text).strip()

        # Удаление специальных символов (сохраняем x и х)
        text = re.sub(r'[^\w\s\-.,()×xх²]', '', text, flags=re.UNICODE)

        # Нормализация порядка слов
        text = self._normalize_word_order(text)

        # Замена синонимов
        words = text.split()
        normalized_words = []
        for word in words:
            normalized_word = self.synonyms_dict.get(word, self.synonyms_dict.get(word.lower(), word))
            normalized_words.append(normalized_word)

        return ' '.join(normalized_words)

    def _normalize_word_order(self, text: str) -> str:
        """
        Нормализация порядка слов для синонимичных конструкций
        """
        words = text.split()
        normalized_words = words.copy()

        for i in range(len(words) - 1):
            word1 = words[i].lower()
            word2 = words[i + 1].lower()

            if (word1, word2) in self.word_order_patterns:
                normalized_phrase = self.word_order_patterns[(word1, word2)]
                normalized_words[i:i+2] = normalized_phrase.split()
                break

        return ' '.join(normalized_words)

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет семантической схожести с учетом порядка слов и синонимов
        """
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)

        if norm1 == norm2:
            return 1.0

        # Проверяем схожесть ключевых слов
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        # Удаляем служебные слова
        stop_words = {'для', 'и', 'с', 'на', 'в', 'к', 'от', 'до', 'по', 'за', 'при'}
        content_words1 = words1 - stop_words
        content_words2 = words2 - stop_words

        if not content_words1 or not content_words2:
            return 0.0

        # Jaccard коэффициент для содержательных слов
        intersection = content_words1 & content_words2
        union = content_words1 | content_words2

        jaccard = len(intersection) / len(union) if union else 0

        # Бонус если большинство ключевых слов совпадает
        if jaccard >= 0.8:
            return 0.95
        elif jaccard >= 0.6:
            return 0.85
        else:
            return jaccard

    def _extract_numeric_values(self, text: str) -> set:
        """
        УЛУЧШЕННОЕ извлечение числовых значений из текста
        Извлекает ПЕРЕД нормализацией для сохранения различий
        """
        numeric_values = set()

        # ВАЖНО: Работаем с оригинальным текстом для точного извлечения
        text_lower = text.lower()

        # Извлекаем размеры кабелей (3x1.5, 3х2.5)
        size_pattern = r'(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)'
        for match in re.finditer(size_pattern, text_lower):
            num1 = float(match.group(1).replace(',', '.'))
            num2 = float(match.group(2).replace(',', '.'))
            # Создаем уникальный идентификатор размера
            size_key = f"cable_{num1}x{num2}"
            numeric_values.add(size_key)

        # Извлекаем характеристики автоматов (C16, С25)
        circuit_pattern = r'[cсCС]\s*(\d+)'
        for match in re.finditer(circuit_pattern, text_lower):
            value = int(match.group(1))
            circuit_key = f"circuit_c{value}"
            numeric_values.add(circuit_key)

        # Извлекаем мощности (10Вт, 15W)
        power_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:вт|w|ватт)'
        for match in re.finditer(power_pattern, text_lower, re.IGNORECASE):
            value = float(match.group(1).replace(',', '.'))
            power_key = f"power_{value}w"
            numeric_values.add(power_key)

        # Извлекаем токи (16А, 25A)
        current_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:а|a|ампер)'
        for match in re.finditer(current_pattern, text_lower, re.IGNORECASE):
            value = float(match.group(1).replace(',', '.'))
            current_key = f"current_{value}a"
            numeric_values.add(current_key)

        # Извлекаем площади сечения (1.5мм², 2.5мм²)
        area_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:мм²?|кв\.?мм)'
        for match in re.finditer(area_pattern, text_lower):
            value = float(match.group(1).replace(',', '.'))
            area_key = f"area_{value}mm2"
            numeric_values.add(area_key)

        return numeric_values

    def _check_numeric_compatibility(self, text1: str, text2: str) -> bool:
        """
        УЛУЧШЕННАЯ проверка совместимости числовых значений
        """
        values1 = self._extract_numeric_values(text1)
        values2 = self._extract_numeric_values(text2)

        # Если нет числовых значений, считаем совместимыми
        if not values1 and not values2:
            return True

        # Если числовые значения есть только в одном тексте - частично совместимы
        if not values1 or not values2:
            return True

        # Проверяем пересечение ключевых числовых значений
        # Если множества полностью совпадают - полная совместимость
        if values1 == values2:
            return True

        # Если есть хотя бы одно общее числовое значение - совместимы
        if values1 & values2:
            # Но проверяем, нет ли конфликтующих значений того же типа
            # Например, cable_3x1.5 и cable_3x2.5 - несовместимы
            for val1 in values1:
                val1_type = val1.split('_')[0]
                for val2 in values2:
                    val2_type = val2.split('_')[0]
                    # Если типы совпадают, но значения разные - несовместимы
                    if val1_type == val2_type and val1 != val2:
                        return False
            return True

        # Если множества не пересекаются и содержат значения одного типа - несовместимы
        types1 = {v.split('_')[0] for v in values1}
        types2 = {v.split('_')[0] for v in values2}

        # Если есть общие типы, но нет общих значений - несовместимы
        if types1 & types2:
            return False

        # В остальных случаях считаем частично совместимыми
        return True

    def filter_by_similarity_threshold(self,
                                       results: List[SearchResult],
                                       threshold: float = 30.0) -> List[SearchResult]:
        """
        Фильтрация результатов по минимальному проценту похожести
        """
        return [result for result in results if result.similarity_percentage >= threshold]

    def sort_by_similarity(self, results: List[SearchResult],
                           reverse: bool = True) -> List[SearchResult]:
        """
        Сортировка результатов по проценту похожести
        """
        return sorted(results, key=lambda x: x.similarity_percentage, reverse=reverse)

    def get_top_matches(self, results: List[SearchResult],
                        top_n: int = 10) -> List[SearchResult]:
        """
        Получение топ N лучших совпадений
        """
        sorted_results = self.sort_by_similarity(results)
        return sorted_results[:top_n]