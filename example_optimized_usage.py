#!/usr/bin/env python3
"""
Пример использования оптимизированной системы сопоставления материалов.

Демонстрирует:
- Создание оптимизированных моделей данных
- Использование высокопроизводительного сервиса сопоставления
- Архитектурные паттерны для масштабируемости
- Мониторинг производительности
"""

import asyncio
import time
import logging
import sys
import os
from typing import List
from decimal import Decimal

# Добавляем src в путь Python для импорта оптимизированных модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models.optimized_material import (
    OptimizedMaterial, OptimizedPriceListItem, OptimizedSearchResult,
    MaterialCategory, Currency, create_optimized_material, create_optimized_price_list_item
)

from src.services.optimized_similarity_service import (
    OptimizedSimilarityService, SimilarityConfig, SimilarityWeights,
    SimilarityAlgorithm, MatchingStrategy, create_similarity_service
)

from src.architecture.scalable_patterns import (
    MaterialMatchingApplicationService, create_application_service,
    application_service_context, LoggingObserver, MetricsObserver
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_materials() -> List[OptimizedMaterial]:
    """Создание примеров материалов с использованием фабричных функций"""
    
    materials = [
        create_optimized_material(
            id="mat_001",
            name="Кабель ВВГ 3x2.5",
            description="Силовой кабель ВВГ 3x2.5 мм²",
            category="cables",
            brand="ТЭЛЗ",
            unit="м",
            specifications={"voltage": "0.66кВ", "cores": 3, "cross_section": "2.5мм²"}
        ),
        
        create_optimized_material(
            id="mat_002", 
            name="Светодиодная лампа 10Вт E27",
            description="LED лампа 10W цоколь E27 теплый белый",
            category="lighting",
            brand="Philips",
            unit="шт",
            specifications={"power": "10W", "base": "E27", "color_temp": "3000K"}
        ),
        
        create_optimized_material(
            id="mat_003",
            name="Автоматический выключатель С16",
            description="Автоматический выключатель 16А характеристика С",
            category="automation", 
            brand="ABB",
            unit="шт",
            specifications={"current": "16А", "characteristic": "C", "poles": 1}
        ),
        
        create_optimized_material(
            id="mat_004",
            name="Провод ПВС 2x1.5",
            description="Провод соединительный ПВС 2x1.5",
            category="cables",
            brand="Рыбинсккабель",
            unit="м", 
            specifications={"cores": 2, "cross_section": "1.5мм²"}
        ),
        
        create_optimized_material(
            id="mat_005",
            name="Светильник потолочный LED 36Вт",
            description="Потолочный светодиодный светильник 36W",
            category="lighting",
            brand="Gauss",
            unit="шт",
            specifications={"power": "36W", "type": "ceiling", "ip_rating": "IP20"}
        )
    ]
    
    return materials


def create_sample_price_items() -> List[OptimizedPriceListItem]:
    """Создание примеров элементов прайс-листа"""
    
    price_items = [
        create_optimized_price_list_item(
            id="price_001",
            material_name="Кабель силовой ВВГ 3х2,5",
            description="Кабель ВВГ 3x2.5 мм² медный",
            price=Decimal("85.50"),
            currency="RUB",
            supplier="ЭлектроТорг",
            category="cables",
            brand="ТЭЛЗ",
            unit="м",
            specifications={"voltage": "660В", "cores": 3, "section": "2.5"}
        ),
        
        create_optimized_price_list_item(
            id="price_002",
            material_name="Лампа светодиодная 10W E27",
            description="LED лампа 10 Ватт с цоколем E27",
            price=Decimal("120.00"),
            currency="RUB", 
            supplier="СветОптТорг",
            category="lighting",
            brand="Philips",
            unit="шт",
            specifications={"power": "10W", "socket": "E27", "temp": "3000К"}
        ),
        
        create_optimized_price_list_item(
            id="price_003",
            material_name="Выключатель автоматический 16А С",
            description="Автомат 16 Ампер характеристика C однополюсный",
            price=Decimal("450.00"),
            currency="RUB",
            supplier="ЭлектроКомплект",
            category="automation",
            brand="ABB",
            unit="шт",
            specifications={"current": "16А", "char": "C", "pole": "1П"}
        ),
        
        # Дополнительные варианты для демонстрации нечеткого поиска
        create_optimized_price_list_item(
            id="price_004",
            material_name="ВВГ кабель 3*2,5мм2",
            description="Силовой кабель ВВГ сечением 3x2.5",
            price=Decimal("82.00"),
            currency="RUB",
            supplier="КабельПром",
            category="cables",
            unit="м"
        ),
        
        create_optimized_price_list_item(
            id="price_005",
            material_name="Провод ПВС 2х1,5мм2",
            description="ПВС провод 2 жилы по 1.5 кв.мм",
            price=Decimal("45.30"),
            currency="RUB",
            supplier="Электросвязь",
            category="cables",
            brand="Рыбинсккабель",
            unit="м"
        ),
        
        create_optimized_price_list_item(
            id="price_006",
            material_name="Светильник LED потолочный 36Вт",
            description="Потолочный LED светильник мощностью 36W",
            price=Decimal("1250.00"),
            currency="RUB",
            supplier="СветПрофи",
            category="lighting",
            brand="Gauss",
            unit="шт"
        )
    ]
    
    return price_items


async def demonstrate_basic_matching():
    """Демонстрация базового сопоставления с оптимизированным сервисом"""
    
    logger.info("=== Демонстрация базового сопоставления ===")
    
    # Создаем данные
    materials = create_sample_materials()
    price_items = create_sample_price_items()
    
    logger.info(f"Создано {len(materials)} материалов и {len(price_items)} элементов прайс-листа")
    
    # Создаем оптимизированный сервис сопоставления
    similarity_service = create_similarity_service(
        strategy=MatchingStrategy.HYBRID,
        max_workers=4,
        enable_caching=True
    )
    
    # Выполняем сопоставление
    start_time = time.time()
    
    results = similarity_service.batch_similarity(
        materials=materials,
        price_items=price_items,
        min_similarity=30.0
    )
    
    elapsed_time = (time.time() - start_time) * 1000
    
    # Выводим результаты
    logger.info(f"Сопоставление выполнено за {elapsed_time:.1f}мс")
    logger.info(f"Найдено {len(results)} совпадений")
    
    print("\n📊 РЕЗУЛЬТАТЫ СОПОСТАВЛЕНИЯ:")
    print("=" * 80)
    
    for i, result in enumerate(results[:10], 1):  # Показываем топ-10
        print(f"{i:2d}. Материал: {result.material.name}")
        print(f"    Прайс:    {result.price_item.material_name}")
        print(f"    Сходство: {result.similarity_percentage:.1f}% ({result.match_grade})")
        print(f"    Цена:     {result.price_item.formatted_price()}")
        print(f"    Поставщик: {result.price_item.supplier}")
        
        # Детали сопоставления
        details = []
        for field, score in result.similarity_details.items():
            if score > 0:
                details.append(f"{field}:{score:.0f}%")
        print(f"    Детали:   {', '.join(details)}")
        print()
    
    # Статистика производительности
    stats = similarity_service.get_performance_stats()
    print("📈 СТАТИСТИКА ПРОИЗВОДИТЕЛЬНОСТИ:")
    print("=" * 50)
    print(f"Cache hit rate:      {stats['cache_hit_rate']:.1f}%")
    print(f"Вычислений всего:    {stats['total_computations']}")
    print(f"Среднее время:       {stats['average_computation_time_ms']:.2f}мс")
    print(f"Размер кеша:         {stats['cache_size']}")
    print()


async def demonstrate_advanced_patterns():
    """Демонстрация архитектурных паттернов"""
    
    logger.info("=== Демонстрация архитектурных паттернов ===")
    
    # Создаем application service с полным набором паттернов
    async with application_service_context(
        enable_circuit_breaker=True
    ) as app_service:
        
        # Добавляем наблюдателей для мониторинга
        logging_observer = LoggingObserver()
        metrics_observer = MetricsObserver()
        
        app_service.event_emitter.subscribe(logging_observer)
        app_service.event_emitter.subscribe(metrics_observer)
        
        # Добавляем материалы в систему
        materials = create_sample_materials()
        for material in materials:
            await app_service.add_material(material)
        
        # Добавляем элементы прайс-листа
        price_items = create_sample_price_items()
        for item in price_items:
            await app_service.add_price_item(item)
        
        print("✅ Данные загружены в систему")
        
        # Выполняем сопоставление с различными стратегиями
        strategies = ["exact", "fuzzy", "hybrid"]
        
        for strategy_name in strategies:
            print(f"\n🔍 Выполнение сопоставления со стратегией '{strategy_name}'")
            
            start_time = time.time()
            
            results = await app_service.match_materials(
                strategy_name=strategy_name
            )
            
            elapsed_time = (time.time() - start_time) * 1000
            
            print(f"   Найдено {len(results)} совпадений за {elapsed_time:.1f}мс")
            
            # Показываем лучшие результаты
            if results:
                best_match = max(results, key=lambda r: r.similarity_percentage)
                print(f"   Лучшее совпадение: {best_match.similarity_percentage:.1f}%")
                print(f"   '{best_match.material.name}' -> '{best_match.price_item.material_name}'")
        
        # Получаем статистику событий
        print("\n📊 СОБРАННЫЕ МЕТРИКИ:")
        print("=" * 40)
        
        metrics = metrics_observer.get_metrics()
        for event_type, events in metrics.items():
            print(f"{event_type}: {len(events)} событий")
            if events and isinstance(events[0], dict):
                # Показываем последнее событие
                latest = events[-1]
                for key, value in latest.items():
                    print(f"  {key}: {value}")
        
        # История команд
        print(f"\n📜 История операций: {len(app_service.get_command_history())} команд")
        for i, command_desc in enumerate(app_service.get_command_history(), 1):
            print(f"  {i}. {command_desc}")


async def demonstrate_performance_comparison():
    """Демонстрация сравнения производительности"""
    
    logger.info("=== Сравнение производительности ===")
    
    # Создаем больше данных для тестирования
    materials = []
    for i in range(50):  # 50 материалов
        materials.append(create_optimized_material(
            id=f"perf_mat_{i:03d}",
            name=f"Тестовый материал {i}",
            description=f"Описание тестового материала номер {i}",
            category=MaterialCategory.GENERAL,
            specifications={"test_param": i, "category_id": i % 5}
        ))
    
    price_items = []
    for i in range(200):  # 200 позиций прайс-листа  
        price_items.append(create_optimized_price_list_item(
            id=f"perf_price_{i:03d}",
            material_name=f"Прайс позиция {i}",
            description=f"Описание позиции {i}",
            price=Decimal(str(100 + i * 5)),
            currency=Currency.RUB,
            supplier=f"Поставщик {i % 10}"
        ))
    
    print(f"🧪 Тест производительности: {len(materials)} материалов × {len(price_items)} прайс-позиций")
    print(f"   Всего сравнений: {len(materials) * len(price_items):,}")
    
    # Конфигурации для сравнения
    configs = {
        "Базовая": SimilarityConfig(
            max_workers=1,
            enable_caching=False,
            use_parallel=False
        ),
        "С кешированием": SimilarityConfig(
            max_workers=1,
            enable_caching=True,
            use_parallel=False
        ),
        "Параллельная": SimilarityConfig(
            max_workers=4,
            enable_caching=True,
            use_parallel=True
        )
    }
    
    results = {}
    
    for config_name, config in configs.items():
        print(f"\n⚙️  Тестирование конфигурации: {config_name}")
        
        # Создаем сервис с конкретной конфигурацией
        service = OptimizedSimilarityService(config)
        
        start_time = time.time()
        
        # Выполняем сопоставление
        matches = service.batch_similarity(
            materials=materials,
            price_items=price_items,
            min_similarity=20.0
        )
        
        elapsed_time = (time.time() - start_time) * 1000
        
        # Получаем статистику
        stats = service.get_performance_stats()
        
        results[config_name] = {
            'time_ms': elapsed_time,
            'matches': len(matches),
            'stats': stats
        }
        
        print(f"   ⏱️  Время: {elapsed_time:.1f}мс")
        print(f"   🎯 Совпадений: {len(matches)}")
        print(f"   💾 Cache hit rate: {stats['cache_hit_rate']:.1f}%")
    
    # Сравнительная таблица
    print(f"\n📊 СРАВНИТЕЛЬНАЯ ТАБЛИЦА ПРОИЗВОДИТЕЛЬНОСТИ:")
    print("=" * 70)
    print(f"{'Конфигурация':<15} {'Время (мс)':<12} {'Совпадения':<12} {'Cache Hit %':<12}")
    print("-" * 70)
    
    baseline_time = results["Базовая"]["time_ms"]
    
    for config_name, result in results.items():
        speedup = baseline_time / result["time_ms"] if result["time_ms"] > 0 else 0
        speedup_text = f"({speedup:.1f}x)" if speedup > 1 else ""
        
        print(f"{config_name:<15} {result['time_ms']:<12.1f} {result['matches']:<12} "
              f"{result['stats']['cache_hit_rate']:<12.1f} {speedup_text}")


async def main():
    """Основная демонстрационная функция"""
    
    print("🚀 ДЕМОНСТРАЦИЯ ОПТИМИЗИРОВАННОЙ СИСТЕМЫ СОПОСТАВЛЕНИЯ МАТЕРИАЛОВ")
    print("=" * 80)
    print()
    
    try:
        # 1. Базовое сопоставление
        await demonstrate_basic_matching()
        
        print("\n" + "="*80 + "\n")
        
        # 2. Архитектурные паттерны
        await demonstrate_advanced_patterns()
        
        print("\n" + "="*80 + "\n")
        
        # 3. Тест производительности
        await demonstrate_performance_comparison()
        
        print("\n✅ Все демонстрации выполнены успешно!")
        
    except Exception as e:
        logger.error(f"Ошибка во время демонстрации: {e}", exc_info=True)
        print(f"\n❌ Произошла ошибка: {e}")


if __name__ == "__main__":
    # Запуск демонстрации
    asyncio.run(main())