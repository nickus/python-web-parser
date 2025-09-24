#!/usr/bin/env python3
"""
Тесты для оптимизированной системы сопоставления материалов.
Проверяет корректность работы всех компонентов и производительность.
"""

import pytest
import asyncio
import time
import sys
import os
from typing import List
from decimal import Decimal

# Добавляем src в путь Python  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models.optimized_material import (
    OptimizedMaterial, OptimizedPriceListItem, OptimizedSearchResult,
    MaterialCategory, Currency, create_optimized_material
)

from src.services.optimized_similarity_service import (
    OptimizedSimilarityService, SimilarityConfig, 
    create_similarity_service, MatchingStrategy
)

from src.architecture.scalable_patterns import (
    InMemoryRepository, MaterialFactory, PriceListItemFactory,
    ExactMatchingStrategy, FuzzyMatchingStrategy
)


class TestOptimizedModels:
    """Тесты для оптимизированных моделей данных"""
    
    def test_optimized_material_creation(self):
        """Тест создания оптимизированного материала"""
        material = OptimizedMaterial(
            id="test_001",
            name="Тестовый материал",
            description="Описание тестового материала",
            category=MaterialCategory.ELECTRICAL,
            brand="TestBrand",
            specifications={"param1": "value1", "param2": 123}
        )
        
        assert material.id == "test_001"
        assert material.name == "Тестовый материал"
        assert material.category == MaterialCategory.ELECTRICAL
        assert material.brand == "TestBrand"
        assert isinstance(material.specifications, dict)
        
    def test_material_validation(self):
        """Тест валидации материала"""
        # Проверяем валидацию пустых полей
        with pytest.raises(ValueError, match="Material ID cannot be empty"):
            OptimizedMaterial(
                id="",
                name="Test",
                description="Test",
                category=MaterialCategory.GENERAL
            )
        
        with pytest.raises(ValueError, match="Material name cannot be empty"):
            OptimizedMaterial(
                id="test_001",
                name="",
                description="Test",
                category=MaterialCategory.GENERAL
            )
    
    def test_material_caching(self):
        """Тест кеширования в материалах"""
        material = OptimizedMaterial(
            id="cache_test",
            name="Кабель ВВГ 3x2.5",
            description="Силовой кабель",
            category=MaterialCategory.CABLES,
            brand="ТЭЛЗ"
        )
        
        # Первый вызов должен вычислить и закешировать
        full_text1 = material.get_full_text()
        
        # Второй вызов должен вернуть кешированное значение
        full_text2 = material.get_full_text()
        
        assert full_text1 == full_text2
        assert "Кабель ВВГ 3x2.5" in full_text1
        assert "Силовой кабель" in full_text1
        assert "ТЭЛЗ" in full_text1
        assert "cables" in full_text1
    
    def test_price_item_creation(self):
        """Тест создания элемента прайс-листа"""
        price_item = OptimizedPriceListItem(
            id="price_001",
            material_name="Тестовый материал",
            description="Описание",
            price=Decimal("100.50"),
            currency=Currency.RUB,
            supplier="ТестПоставщик",
            category=MaterialCategory.ELECTRICAL
        )
        
        assert price_item.id == "price_001"
        assert price_item.price == Decimal("100.50")
        assert price_item.currency == Currency.RUB
        assert price_item.formatted_price() == "100.50 RUB"
    
    def test_price_item_validation(self):
        """Тест валидации прайс-листа"""
        with pytest.raises(ValueError, match="Price cannot be negative"):
            OptimizedPriceListItem(
                id="test",
                material_name="Test",
                description="Test",
                price=Decimal("-10.00"),
                currency=Currency.RUB,
                supplier="Test"
            )
    
    def test_search_result_creation(self):
        """Тест создания результата поиска"""
        material = OptimizedMaterial(
            id="mat_001",
            name="Тест",
            description="Тест",
            category=MaterialCategory.GENERAL
        )
        
        price_item = OptimizedPriceListItem(
            id="price_001",
            material_name="Тест",
            description="Тест",
            price=Decimal("100"),
            currency=Currency.RUB,
            supplier="Тест"
        )
        
        result = OptimizedSearchResult(
            material=material,
            price_item=price_item,
            similarity_percentage=85.5,
            similarity_details={"name": 95.0, "description": 76.0},
            elasticsearch_score=1.25
        )
        
        assert result.similarity_percentage == 85.5
        assert result.is_high_confidence_match is False  # < 85% threshold
        assert result.match_confidence > 0
        assert result.quality_score > 0


class TestOptimizedSimilarityService:
    """Тесты для оптимизированного сервиса сопоставления"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.config = SimilarityConfig(
            max_workers=2,
            enable_caching=True,
            use_parallel=False  # Для детерминированных тестов
        )
        self.service = OptimizedSimilarityService(self.config)
    
    def test_text_similarity_basic(self):
        """Тест базового сопоставления текстов"""
        # Идентичные тексты
        sim1 = self.service.calculate_text_similarity("тест", "тест")
        assert sim1 == 1.0
        
        # Близкие тексты
        sim2 = self.service.calculate_text_similarity("кабель", "кабел")
        assert 0.8 < sim2 < 1.0
        
        # Разные тексты
        sim3 = self.service.calculate_text_similarity("кабель", "лампа")
        assert sim3 < 0.5
        
        # Пустые тексты
        sim4 = self.service.calculate_text_similarity("", "тест")
        assert sim4 == 0.0
    
    def test_material_similarity_calculation(self):
        """Тест расчета сопоставления материалов"""
        material = OptimizedMaterial(
            id="mat_001",
            name="Кабель ВВГ 3x2.5",
            description="Силовой кабель ВВГ",
            category=MaterialCategory.CABLES,
            brand="ТЭЛЗ"
        )
        
        price_item = OptimizedPriceListItem(
            id="price_001",
            material_name="Кабель ВВГ 3x2,5",  # Небольшая разница в написании
            description="Силовой кабель ВВГ 3x2.5",
            price=Decimal("100"),
            currency=Currency.RUB,
            supplier="ЭлектроТорг",
            category=MaterialCategory.CABLES,
            brand="ТЭЛЗ"
        )
        
        similarity_pct, details = self.service.calculate_material_similarity(material, price_item)
        
        assert similarity_pct > 85.0  # Высокая схожесть
        assert "name" in details
        assert "description" in details
        assert "category" in details
        assert "brand" in details
        assert details["name"] > 80.0  # Название очень похоже
        assert details["category"] == 100.0  # Категория идентична
        assert details["brand"] == 100.0  # Бренд идентичен
    
    def test_batch_similarity(self):
        """Тест пакетного сопоставления"""
        materials = [
            OptimizedMaterial(
                id=f"mat_{i}",
                name=f"Материал {i}",
                description=f"Описание {i}",
                category=MaterialCategory.GENERAL
            )
            for i in range(3)
        ]
        
        price_items = [
            OptimizedPriceListItem(
                id=f"price_{i}",
                material_name=f"Материал {i}",
                description=f"Описание {i}",
                price=Decimal("100"),
                currency=Currency.RUB,
                supplier="Тест"
            )
            for i in range(3)
        ]
        
        results = self.service.batch_similarity(
            materials=materials,
            price_items=price_items,
            min_similarity=50.0
        )
        
        assert len(results) == 3  # Должно найти точные совпадения
        
        # Проверяем, что результаты отсортированы по качеству
        for i in range(len(results) - 1):
            assert results[i].quality_score >= results[i + 1].quality_score
    
    def test_caching_performance(self):
        """Тест производительности кеширования"""
        text1 = "Тестовый текст для проверки кеширования"
        text2 = "Тестовый текст для проверки кешированя"  # Небольшая опечатка
        
        # Первые вызовы (без кеша)
        start_time = time.time()
        for _ in range(10):
            self.service.calculate_text_similarity(text1, text2)
        first_time = time.time() - start_time
        
        # Повторные вызовы (с кешем)
        start_time = time.time()
        for _ in range(10):
            self.service.calculate_text_similarity(text1, text2)
        cached_time = time.time() - start_time
        
        # Кешированные вызовы должны быть быстрее
        assert cached_time < first_time
        
        # Проверяем статистику кеша
        stats = self.service.get_performance_stats()
        assert stats['cache_hit_rate'] > 0
    
    def test_performance_stats(self):
        """Тест сбора статистики производительности"""
        # Выполняем несколько операций
        for i in range(5):
            self.service.calculate_text_similarity(f"тест {i}", f"test {i}")
        
        stats = self.service.get_performance_stats()
        
        # Проверяем наличие ключевых метрик
        required_keys = [
            'cache_hit_rate', 'total_computations', 
            'average_computation_time_ms', 'cache_size'
        ]
        
        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], (int, float))
        
        assert stats['total_computations'] >= 5


class TestArchitecturalPatterns:
    """Тесты для архитектурных паттернов"""
    
    def test_in_memory_repository(self):
        """Тест репозитория в памяти"""
        repo = InMemoryRepository(lambda m: m.id)
        
        # Создаем материал
        material = OptimizedMaterial(
            id="repo_test",
            name="Тест репозитория",
            description="Тест",
            category=MaterialCategory.GENERAL
        )
        
        # Сохраняем
        asyncio.run(repo.save(material))
        
        # Извлекаем
        retrieved = asyncio.run(repo.get_by_id("repo_test"))
        
        assert retrieved is not None
        assert retrieved.id == material.id
        assert retrieved.name == material.name
    
    def test_material_factory(self):
        """Тест фабрики материалов"""
        factory = MaterialFactory()
        
        material = factory.create(
            name="Тестовый материал",
            description="Тест фабрики",
            category="cables",
            brand="TestBrand"
        )
        
        assert isinstance(material, OptimizedMaterial)
        assert material.category == MaterialCategory.CABLES
        assert material.brand == "TestBrand"
        assert len(material.id) > 0  # ID должен быть сгенерирован
    
    def test_price_list_item_factory(self):
        """Тест фабрики элементов прайс-листа"""
        factory = PriceListItemFactory()
        
        item = factory.create(
            material_name="Тестовый материал",
            description="Тест",
            price=100.0,
            currency="RUB",
            supplier="Тест"
        )
        
        assert isinstance(item, OptimizedPriceListItem)
        assert item.currency == Currency.RUB
        assert item.price == Decimal("100.0")
        assert len(item.id) > 0
    
    @pytest.mark.asyncio
    async def test_matching_strategies(self):
        """Тест стратегий сопоставления"""
        # Создаем данные для тестирования
        materials = [
            OptimizedMaterial(
                id="strategy_mat",
                name="Точное совпадение",
                description="Тест",
                category=MaterialCategory.GENERAL
            )
        ]
        
        price_items = [
            OptimizedPriceListItem(
                id="strategy_price_exact",
                material_name="Точное совпадение",  # Точное совпадение
                description="Тест",
                price=Decimal("100"),
                currency=Currency.RUB,
                supplier="Тест"
            ),
            OptimizedPriceListItem(
                id="strategy_price_fuzzy",
                material_name="Точное совпаденіе",  # С опечаткой
                description="Тест",
                price=Decimal("110"),
                currency=Currency.RUB,
                supplier="Тест"
            )
        ]
        
        service = create_similarity_service()
        
        # Тестируем стратегию точного совпадения
        exact_strategy = ExactMatchingStrategy(service)
        exact_results = await exact_strategy.match(materials, price_items)
        
        assert len(exact_results) >= 1
        # Проверяем, что найдено точное совпадение с высоким процентом
        best_exact = max(exact_results, key=lambda r: r.similarity_percentage)
        assert best_exact.similarity_percentage >= 95.0
        
        # Тестируем стратегию нечеткого сопоставления
        fuzzy_strategy = FuzzyMatchingStrategy(service, threshold=50.0)
        fuzzy_results = await fuzzy_strategy.match(materials, price_items)
        
        assert len(fuzzy_results) >= 2  # Должно найти оба элемента


class TestPerformanceOptimizations:
    """Тесты оптимизации производительности"""
    
    def test_memory_usage_optimization(self):
        """Тест оптимизации использования памяти"""
        import sys
        
        # Создаем обычный объект без slots
        class RegularClass:
            def __init__(self, id, name, description):
                self.id = id
                self.name = name
                self.description = description
        
        regular_obj = RegularClass("test", "Test Name", "Test Description")
        regular_size = sys.getsizeof(regular_obj) + sys.getsizeof(regular_obj.__dict__)
        
        # Создаем оптимизированный объект с slots
        optimized_obj = OptimizedMaterial(
            id="test",
            name="Test Name", 
            description="Test Description",
            category=MaterialCategory.GENERAL
        )
        optimized_size = sys.getsizeof(optimized_obj)
        
        # Оптимизированный объект должен использовать меньше памяти
        memory_saving = (regular_size - optimized_size) / regular_size
        print(f"Memory saving: {memory_saving:.1%}")
        assert memory_saving > 0.1  # Ожидаем экономию минимум 10%
    
    def test_parallel_processing_benefit(self):
        """Тест преимущества параллельной обработки"""
        # Создаем больше данных для заметной разницы
        materials = [
            OptimizedMaterial(
                id=f"perf_mat_{i}",
                name=f"Material {i}",
                description="Test material",
                category=MaterialCategory.GENERAL
            )
            for i in range(20)
        ]
        
        price_items = [
            OptimizedPriceListItem(
                id=f"perf_price_{i}",
                material_name=f"Material {i}",
                description="Test item",
                price=Decimal("100"),
                currency=Currency.RUB,
                supplier="Test"
            )
            for i in range(20)
        ]
        
        # Последовательная обработка
        sequential_config = SimilarityConfig(
            max_workers=1,
            use_parallel=False,
            enable_caching=False
        )
        sequential_service = OptimizedSimilarityService(sequential_config)
        
        start_time = time.time()
        sequential_results = sequential_service.batch_similarity(
            materials, price_items, min_similarity=30.0
        )
        sequential_time = time.time() - start_time
        
        # Параллельная обработка
        parallel_config = SimilarityConfig(
            max_workers=4,
            use_parallel=True,
            enable_caching=True
        )
        parallel_service = OptimizedSimilarityService(parallel_config)
        
        start_time = time.time()
        parallel_results = parallel_service.batch_similarity(
            materials, price_items, min_similarity=30.0
        )
        parallel_time = time.time() - start_time
        
        # Результаты должны быть идентичными
        assert len(sequential_results) == len(parallel_results)
        
        # Параллельная версия должна быть быстрее (или хотя бы не медленнее)
        speedup = sequential_time / parallel_time if parallel_time > 0 else 1
        print(f"Parallel speedup: {speedup:.2f}x")
        assert speedup >= 0.8  # Допускаем небольшие накладные расходы


def run_comprehensive_test():
    """Запуск всестороннего тестирования"""
    print("🧪 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ ОПТИМИЗАЦИЙ")
    print("=" * 60)
    
    # Запускаем pytest программно
    import pytest
    
    # Настраиваем pytest для подробного вывода
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "-x"  # Останавливаться на первой ошибке
    ]
    
    # Выполняем тесты
    result = pytest.main(pytest_args)
    
    if result == 0:
        print("\n✅ Все тесты пройдены успешно!")
        print("🎉 Оптимизации работают корректно!")
    else:
        print("\n❌ Некоторые тесты провалились")
        print("🔧 Необходимо исправить найденные проблемы")
    
    return result


if __name__ == "__main__":
    run_comprehensive_test()