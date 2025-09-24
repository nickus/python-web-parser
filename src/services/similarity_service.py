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
        # 1. Наименования vs name - основной критерий
        # 2. Код обор. vs article - важный, но не критичный
        # 3. Завод изг. vs brand - дополнительный критерий
        self.new_weights = {
            'name_similarity': 0.70,  # Повышаем важность названия
            'article_similarity': 0.20,  # Снижаем важность артикула
            'brand_similarity': 0.10,  # Снижаем важность бренда
        }
        
        # Паттерны для извлечения числовых диапазонов и размеров
        self.numeric_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*([а-яА-Я]*)',  # диапазоны: 40-95А
            r'(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)',  # размеры: 16x16
            r'(\d+(?:[.,]\d+)?)\s*(мм²?|а|в|вт|w)',  # единицы: 2.5мм²
        ]
        
        # Инициализируем отладочный логгер
        self.debug_logger = get_debug_logger()
        
        # Словарь замен для визуально похожих символов
        self.char_replacements = {
            # Латинские символы на кириллические (только базовые)
            'x': 'х', 'X': 'Х',  # Основная проблема с символом x в размерах кабелей
            'p': 'р', 'P': 'Р',
            'c': 'с', 'C': 'С',
            'o': 'о', 'O': 'О',
            'a': 'а', 'A': 'А', 
            'e': 'е', 'E': 'Е',
            'y': 'у', 'Y': 'У',
            'T': 'Т', 'H': 'Н', 'K': 'К', 'M': 'М', 'B': 'В'
        }
        
        # Словарь синонимов для материалов (двунаправленный)
        base_synonyms = {
            'led': 'светодиодный',
            'автомат': 'выключатель',
            'автоматический': 'автоматический',  # Оставляем как есть
            'выключатель': 'автомат',  # Обратная связь 
            'лампа': 'лампа',  # Убираем замену на светильник 
            'кабель': 'кабель',  # Убираем замену на провод
            'мм2': 'мм²',
            'кв.мм': 'мм²',
            'квадратных': 'мм²',
            'вт': 'w',
            'ватт': 'w'
        }
        
        # Словарь синонимичных конструкций для нормализации порядка слов
        self.word_order_patterns = {
            # канал кабельный <-> кабельный канал
            ('канал', 'кабельный'): 'кабельный канал',
            ('кабельный', 'канал'): 'кабельный канал',
            # выключатель автоматический <-> автоматический выключатель  
            ('выключатель', 'автоматический'): 'автоматический выключатель',
            ('автоматический', 'выключатель'): 'автоматический выключатель',
            # лампа светодиодная <-> светодиодная лампа
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
            # Нормализация размеров кабелей
            (r'(\d+)\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*(?:мм2?|мм²|кв\.?мм)', r'\1x\2мм²'),
            (r'(\d+(?:[.,]\d+)?)\s*(?:мм2?|мм²|кв\.?мм)', r'\1мм²'),
            # Нормализация мощности
            (r'(\d+(?:[.,]\d+)?)\s*(?:вт|ватт|w)', r'\1вт'),
            # Нормализация тока и напряжения
            (r'(\d+(?:[.,]\d+)?)\s*(?:а|ампер)', r'\1а'),
            (r'(\d+(?:[.,]\d+)?)\s*(?:в|вольт)', r'\1в'),
            # Характеристика автоматов
            (r'с(\d+)', r'c\1'),  # с16 -> c16
        ]
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет похожести между двумя текстами
        Использует комбинацию различных метрик + семантическую схожесть
        """
        if not text1 or not text2:
            return 0.0
        
        # Нормализация текстов
        text1_clean = self._normalize_text(text1)
        text2_clean = self._normalize_text(text2)
        
        # Комментируем логирование для производительности
        
        if text1_clean == text2_clean:
            return 100.0
        
        # Семантическая схожесть (новое)
        semantic_sim = self._calculate_semantic_similarity(text1, text2)
        
        # Различные метрики похожести
        ratio = fuzz.ratio(text1_clean, text2_clean) / 100.0
        partial_ratio = fuzz.partial_ratio(text1_clean, text2_clean) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(text1_clean, text2_clean) / 100.0
        token_set_ratio = fuzz.token_set_ratio(text1_clean, text2_clean) / 100.0
        
        # Sequence matcher для дополнительной точности
        sequence_ratio = SequenceMatcher(None, text1_clean, text2_clean).ratio()
        
        # Взвешенное среднее с учетом семантической схожести
        # Увеличиваем вес token_set_ratio для лучшего сравнения разного порядка слов
        combined_score = (
            ratio * 0.15 +
            partial_ratio * 0.15 +
            token_sort_ratio * 0.25 +  # Увеличиваем для сортированного сравнения
            token_set_ratio * 0.25 +   # Увеличиваем для множественного сравнения
            sequence_ratio * 0.05 +
            semantic_sim * 0.15  # Семантическая составляющая
        )
        
        result = min(combined_score * 100, 100.0)
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
            return 85.0  # Увеличиваем оценку для частичного совпадения категорий
        
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
            ratio = max(ratio, 0.75)  # Увеличиваем бонус для частичного совпадения брендов
        
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
        
        # Детальное логирование с помощью отладочного логгера
        # Подготовка дополнительных деталей для логирования
        # Проверяем высокую схожесть основных полей для идентичных материалов
        # Используем более мягкие пороги для учета небольших различий в форматировании
        name_very_similar = similarities['name'] >= 0.90  # Понижаем порог
        description_similar = similarities['description'] >= 0.75 or not material.description or not price_item.description
        category_similar = similarities['category'] >= 0.85 or not material.category or not price_item.category
        
        # Дополнительная проверка на точное совпадение после нормализации
        normalized_material_name = self._normalize_text(material.name)
        normalized_price_name = self._normalize_text(price_item.material_name)
        exact_match = normalized_material_name == normalized_price_name
        
        # Дополнительная проверка на высокую схожесть основных слов
        material_words = set(normalized_material_name.split())
        price_words = set(normalized_price_name.split())
        words_intersection = material_words & price_words
        words_union = material_words | price_words
        jaccard_similarity = len(words_intersection) / len(words_union) if words_union else 0
        high_word_overlap = jaccard_similarity >= 0.7
        
        # КРИТИЧНО: Проверка числовой совместимости для предотвращения ложных 100%
        numeric_compatible = self._check_numeric_compatibility(
            material.name, price_item.material_name
        )
        
        debug_details = {
            'exact_match': exact_match,
            'name_very_similar': name_very_similar,
            'description_similar': description_similar,
            'category_similar': category_similar,
            'high_word_overlap': high_word_overlap,
            'jaccard_similarity': jaccard_similarity,
            'numeric_compatible': numeric_compatible,
            'normalized_material_name': normalized_material_name,
            'normalized_price_name': normalized_price_name,
            'material_brand': material.brand,
            'price_brand': price_item.brand,
            'material_category': material.category,
            'price_category': price_item.category,
            'material_numeric_values': self._extract_numeric_values(material.name),
            'price_numeric_values': self._extract_numeric_values(price_item.material_name)
        }
        
        # ИСПРАВЛЕНО: Более строгие условия для 100% совпадения
        # Точное совпадение дает 100% только если числовые значения совместимы
        if exact_match and numeric_compatible:
            total_similarity = 1.0
            reason = 'exact_match_with_numeric_compatibility'
        # Высокое пересечение слов дает 100% только при числовой совместимости И высокой схожести названия
        elif high_word_overlap and numeric_compatible and name_very_similar:
            total_similarity = 1.0
            reason = 'high_similarity_with_numeric_compatibility'
        # Традиционная очень высокая схожесть всех полей
        elif name_very_similar and description_similar and category_similar and numeric_compatible:
            total_similarity = 1.0
            reason = 'very_high_field_similarity_with_numeric_compatibility'
        else:
            reason = 'weighted_calculation'
        
        # Логирование только для 100% совпадений (опционально)
        # if reason != 'weighted_calculation':
        #     self.debug_logger.log_matching_process(
        #         material.name,
        #         price_item.material_name,
        #         similarities,
        #         100.0,
        #         {**debug_details, 'reason': reason}
        #     )
        
        # Стандартный расчет с учетом весов (если не 100%)
        if reason == 'weighted_calculation':
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
                
                # ДОПОЛНИТЕЛЬНАЯ КОРРЕКТИРОВКА: Снижаем оценку если числовые значения не совместимы
                if not numeric_compatible:
                    total_similarity *= 0.6  # Существенное снижение за несовместимость чисел
        
        # Конвертация в проценты
        total_percentage = total_similarity * 100
        detail_percentages = {k: v * 100 for k, v in similarities.items()}
        
        # Логирование отключено для производительности
        # if total_percentage < 100.0:  # Избегаем дублирования логов для 100% совпадений
        #     self.debug_logger.log_matching_process(
        #         material.name,
        #         price_item.material_name,
        #         similarities,
        #         total_percentage,
        #         {**debug_details, 'reason': 'weighted_calculation'}
        #     )
        
        return total_percentage, detail_percentages
    
    def calculate_new_material_similarity(self, material: Material, price_item: PriceListItem) -> Tuple[float, Dict[str, float]]:
        """
        Новый алгоритм расчета похожести по приоритетам:
        1. Наименования (материал) vs name (прайс)
        2. Код обор. (материал) vs article (прайс)
        3. Завод изг. (материал) vs brand (прайс)
        
        ИСПРАВЛЕНО: Теперь название может давать 100% при отсутствии других полей
        
        Returns:
            Tuple[float, Dict[str, float]]: Общий процент похожести и детали по каждому параметру
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
        
        # ИСПРАВЛЕНО: Динамическое перераспределение весов
        # Если артикул или бренд отсутствуют, их вес добавляется к названию
        base_name_weight = self.new_weights['name_similarity']
        base_article_weight = self.new_weights['article_similarity']
        base_brand_weight = self.new_weights['brand_similarity']
        
        # Проверяем наличие данных для артикула и бренда
        has_article = bool(material_code.strip() and price_article.strip())
        has_brand = bool(material_manufacturer.strip() and price_brand.strip())
        
        # Перераспределяем веса
        if not has_article and not has_brand:
            # Если нет ни артикула, ни бренда - название получает 100%
            name_weight = 1.0
            article_weight = 0.0
            brand_weight = 0.0
        elif not has_article:
            # Если нет артикула - его вес переходит к названию
            name_weight = base_name_weight + base_article_weight
            article_weight = 0.0
            brand_weight = base_brand_weight
        elif not has_brand:
            # Если нет бренда - его вес переходит к названию
            name_weight = base_name_weight + base_brand_weight
            article_weight = base_article_weight
            brand_weight = 0.0
        else:
            # Есть все данные - используем базовые веса
            name_weight = base_name_weight
            article_weight = base_article_weight
            brand_weight = base_brand_weight
        
        # Расчет общей похожести с динамическими весами
        total_percentage = (
            similarities['name_similarity'] * name_weight +
            similarities['article_similarity'] * article_weight +
            similarities['brand_similarity'] * brand_weight
        )
        
        # Упрощенное логирование только для высоких совпадений (>50%)
        if total_percentage > 50.0:
            logger.info(f"[SIMILARITY] '{material_name[:50]}...' vs '{price_name[:50]}...' = {total_percentage:.1f}%")
        
        return total_percentage, similarities
    
    def calculate_code_similarity(self, code1: str, code2: str) -> float:
        """
        Специальный метод для сравнения кодов/артикулов
        Применяет более строгие критерии для кодов
        """
        if not code1 or not code2:
            return 0.0
        
        # Нормализация кодов (убрать пробелы, привести к верхнему регистру)
        norm_code1 = re.sub(r'\s+', '', code1.upper())
        norm_code2 = re.sub(r'\s+', '', code2.upper())
        
        # Точное совпадение
        if norm_code1 == norm_code2:
            return 100.0
        
        # Проверка на вхождение одного кода в другой
        if norm_code1 in norm_code2 or norm_code2 in norm_code1:
            return 85.0
        
        # Используем стандартное текстовое сравнение для остальных случаев
        return self.calculate_text_similarity(norm_code1, norm_code2)
    
    def _normalize_text(self, text: str) -> str:
        """Расширенная нормализация текста для сравнения"""
        if not text:
            return ""
        
        # Сохраняем оригинальный текст для логирования
        original_text = text
        
        # Unicode нормализация (NFC - каноническая композиция)
        text = unicodedata.normalize('NFC', text)
        
        # Замена визуально похожих символов
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
        
        # Удаление специальных символов (кроме букв, цифр, пробелов и некоторых знаков)
        text = re.sub(r'[^\w\s\-.,()×x²]', '', text, flags=re.UNICODE)
        
        # Нормализация порядка слов для синонимичных конструкций
        text = self._normalize_word_order(text)
        
        # Замена синонимов
        words = text.split()
        normalized_words = []
        for word in words:
            # Проверяем синонимы (как в нижнем регистре, так и исходный)
            normalized_word = self.synonyms_dict.get(word, self.synonyms_dict.get(word.lower(), word))
            normalized_words.append(normalized_word)
        
        result = ' '.join(normalized_words)
        # self.debug_logger.log_normalization(original_text, result)  # Логирование отключено
        
        return result
    
    def _normalize_word_order(self, text: str) -> str:
        """
        Нормализация порядка слов для синонимичных конструкций
        Например: "канал кабельный" -> "кабельный канал"
        """
        words = text.split()
        normalized_words = words.copy()
        
        # Проходим по всем парам слов и проверяем на синонимичные конструкции
        for i in range(len(words) - 1):
            word1 = words[i].lower()
            word2 = words[i + 1].lower()
            
            # Проверяем есть ли такая пара в нашем словаре
            if (word1, word2) in self.word_order_patterns:
                normalized_phrase = self.word_order_patterns[(word1, word2)]
                # Заменяем оригинальные слова на нормализованную фразу
                normalized_words[i:i+2] = normalized_phrase.split()
                break  # Выходим после первой замены чтобы избежать конфликтов
        
        return ' '.join(normalized_words)
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет семантической схожести с учетом порядка слов и синонимов
        Дает бонус за семантически эквивалентные фразы даже при разном порядке слов
        """
        # Нормализуем тексты
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        # Если после нормализации тексты совпадают - это высокая семантическая схожесть
        if norm1 == norm2:
            return 1.0
        
        # Проверяем схожесть ключевых слов (существительных и прилагательных)
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
        Извлечение числовых значений, диапазонов и размеров из текста
        
        Returns:
            set: Множество извлеченных числовых значений и диапазонов
        """
        import re
        
        numeric_values = set()
        normalized_text = self._normalize_text(text)
        
        # Извлекаем диапазоны (40-95А)
        range_pattern = r'(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*([а-яА-Яa-zA-Z]*)'
        for match in re.finditer(range_pattern, normalized_text):
            start_val = float(match.group(1).replace(',', '.'))
            end_val = float(match.group(2).replace(',', '.'))
            unit = match.group(3).lower()
            # Создаем уникальный идентификатор диапазона
            range_key = f"range_{start_val}_{end_val}_{unit}"
            numeric_values.add(range_key)
        
        # Извлекаем размеры (16x16)
        size_pattern = r'(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)'
        for match in re.finditer(size_pattern, normalized_text):
            width = float(match.group(1).replace(',', '.'))
            height = float(match.group(2).replace(',', '.'))
            # Создаем нормализованное обозначение размера
            size_key = f"size_{min(width,height)}x{max(width,height)}"
            numeric_values.add(size_key)
        
        # Извлекаем отдельные числовые значения с единицами
        value_pattern = r'(\d+(?:[.,]\d+)?)\s*(мм²?|а|в|вт|w|мм)'
        for match in re.finditer(value_pattern, normalized_text):
            value = float(match.group(1).replace(',', '.'))
            unit = match.group(2).lower()
            value_key = f"value_{value}_{unit}"
            numeric_values.add(value_key)
        
        return numeric_values
    
    def _check_numeric_compatibility(self, text1: str, text2: str) -> bool:
        """
        Проверка совместимости числовых значений в текстах
        
        Returns:
            bool: True если числовые значения совместимы (одинаковые диапазоны/размеры)
        """
        values1 = self._extract_numeric_values(text1)
        values2 = self._extract_numeric_values(text2)
        
        # Если нет числовых значений, считаем совместимыми
        if not values1 and not values2:
            return True
        
        # Если есть хотя бы одно пересечение в ключевых числовых значениях
        if values1 & values2:
            return True
        
        # Если множества не пересекаются, но есть числовые значения - несовместимы
        if values1 and values2:
            return False
        
        # В остальных случаях считаем совместимыми
        return True
    
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