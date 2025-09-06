#!/usr/bin/env python3
"""
Тест расчета схожести
"""

from src.services.similarity_service import SimilarityService
from src.models.material import Material, PriceListItem
from datetime import datetime

def test_100_percent_similarity():
    """Тест расчета 100% схожести"""
    print("=== Тест расчета 100% схожести ===")
    
    service = SimilarityService()
    
    # Создаем идентичный материал и элемент прайс-листа
    material = Material(
        id="1",
        name="Тестовый материал",
        description="Тестовое описание материала",
        category="Тестовая категория",
        brand="Тестовый бренд",
        model="Модель-123",
        specifications={"voltage": "220V", "power": "100W"},
        unit="шт",
        created_at=datetime.now()
    )
    
    price_item = PriceListItem(
        id="1",
        material_name="Тестовый материал",
        description="Тестовое описание материала",
        price=100.0,
        currency="RUB",
        supplier="Поставщик",
        category="Тестовая категория",
        brand="Тестовый бренд",
        unit="шт",
        specifications={"voltage": "220V", "power": "100W"},
        updated_at=datetime.now()
    )
    
    # Рассчитываем схожесть
    similarity_percentage, details = service.calculate_material_similarity(material, price_item)
    
    print(f"Общая схожесть: {similarity_percentage:.2f}%")
    print("Детали:")
    for field, value in details.items():
        print(f"  {field}: {value:.2f}%")
    
    print(f"\nВеса параметров:")
    for field, weight in service.weights.items():
        print(f"  {field}: {weight * 100:.1f}%")
    
    # Проверяем отдельные компоненты
    print(f"\nПроверка отдельных компонентов:")
    name_sim = service.calculate_text_similarity(material.name, price_item.material_name)
    print(f"  Название: {name_sim:.4f}")
    
    desc_sim = service.calculate_text_similarity(material.description, price_item.description)
    print(f"  Описание: {desc_sim:.4f}")
    
    cat_sim = service.calculate_category_similarity(material.category, price_item.category)
    print(f"  Категория: {cat_sim:.4f}")
    
    brand_sim = service.calculate_brand_similarity(material.brand, price_item.brand)
    print(f"  Бренд: {brand_sim:.4f}")
    
    specs_sim = service.calculate_specifications_similarity(material.specifications, price_item.specifications)
    print(f"  Спецификации: {specs_sim:.4f}")
    
    # Проверяем расчет вручную
    manual_calc = (
        name_sim * service.weights['name'] +
        desc_sim * service.weights['description'] +
        cat_sim * service.weights['category'] +
        brand_sim * service.weights['brand'] +
        specs_sim * service.weights['specifications']
    ) * 100
    
    print(f"\nРучной расчет: {manual_calc:.2f}%")
    
    if similarity_percentage >= 95.0:
        print("✅ Схожесть достаточно высокая для идентичных элементов")
    else:
        print("❌ Схожесть слишком низкая для идентичных элементов")
        print("   Необходимо исправить алгоритм")
    
    return similarity_percentage >= 95.0

def test_edge_cases():
    """Тест граничных случаев"""
    print("\n=== Тест граничных случаев ===")
    
    service = SimilarityService()
    
    # Тест с пустыми полями
    material_empty = Material(
        id="2",
        name="Тестовый материал",
        description="",
        category="",
        brand=None,
        model=None,
        specifications={},
        unit="шт",
        created_at=datetime.now()
    )
    
    price_item_empty = PriceListItem(
        id="2",
        material_name="Тестовый материал",
        description="",
        price=100.0,
        currency="RUB",
        supplier="Поставщик",
        category="",
        brand=None,
        unit="шт",
        specifications={},
        updated_at=datetime.now()
    )
    
    similarity_percentage, _ = service.calculate_material_similarity(material_empty, price_item_empty)
    print(f"Схожесть с пустыми полями: {similarity_percentage:.2f}%")
    
    return True

if __name__ == "__main__":
    print("Тестирование системы расчета схожести...")
    print("=" * 50)
    
    success1 = test_100_percent_similarity()
    success2 = test_edge_cases()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✅ Все тесты прошли успешно!")
    else:
        print("❌ Некоторые тесты не прошли")