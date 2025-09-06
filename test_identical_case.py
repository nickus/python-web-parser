#!/usr/bin/env python3
"""
Тест конкретного случая с подшипником LM25-OPUU
"""

from src.services.similarity_service import SimilarityService
from src.models.material import Material, PriceListItem
from datetime import datetime

def test_identical_core_fields():
    """Тест расчета схожести для элементов с идентичными основными полями"""
    print("=== Тест элементов с идентичными основными полями ===")
    
    service = SimilarityService()
    
    # Воссоздаем точный случай из ваших данных
    material = Material(
        id="4",
        name="Подшипник LM25-OPUU",
        description="Подшипник LM25-OPUU",
        category="Общая",
        brand=None,  # Отсутствует в материале
        model=None,
        specifications={},  # Пустые спецификации в материале
        unit="шт",
        created_at=datetime.now()
    )
    
    price_item = PriceListItem(
        id="916001",
        material_name="Подшипник LM25-OPUU",
        description="Подшипник LM25-OPUU",
        price=0.0,
        currency="RUB",
        supplier="Не указан",
        category="Общая",
        brand="DINROLL",  # Есть в прайс-листе
        unit="шт",
        specifications={"Артикул": "В0066805", "Код НСП": "840220"},  # Есть спецификации
        updated_at=datetime.now()
    )
    
    # Рассчитываем схожесть
    similarity_percentage, details = service.calculate_material_similarity(material, price_item)
    
    print(f"Материал: {material.name}")
    print(f"Прайс-позиция: {price_item.material_name}")
    print(f"Общая схожесть: {similarity_percentage:.2f}%")
    print("Детали:")
    for field, value in details.items():
        print(f"  {field}: {value:.2f}%")
    
    print(f"\nОсновные поля:")
    print(f"  Название: '{material.name}' vs '{price_item.material_name}' = {details['name']:.1f}%")
    print(f"  Описание: '{material.description}' vs '{price_item.description}' = {details['description']:.1f}%")
    print(f"  Категория: '{material.category}' vs '{price_item.category}' = {details['category']:.1f}%")
    
    print(f"\nДополнительные поля:")
    print(f"  Бренд: {repr(material.brand)} vs {repr(price_item.brand)} = {details['brand']:.1f}%")
    print(f"  Спецификации: {material.specifications} vs {price_item.specifications} = {details['specifications']:.1f}%")
    
    # Ожидаем 100% для идентичных основных полей
    expected_percentage = 100.0
    if abs(similarity_percentage - expected_percentage) < 0.01:
        print(f"\n✅ Схожесть правильно рассчитана: {similarity_percentage:.2f}% (ожидалось {expected_percentage}%)")
        return True
    else:
        print(f"\n❌ Ошибка: ожидалось {expected_percentage}%, получено {similarity_percentage:.2f}%")
        return False

if __name__ == "__main__":
    success = test_identical_core_fields()
    print("\n" + "=" * 60)
    if success:
        print("✅ Тест пройден успешно!")
    else:
        print("❌ Тест не пройден")