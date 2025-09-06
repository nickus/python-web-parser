#!/usr/bin/env python3
"""
Тест расчета схожести с отсутствующими полями
"""

from src.services.similarity_service import SimilarityService
from src.models.material import Material, PriceListItem
from datetime import datetime

def test_missing_fields_similarity():
    """Тест расчета схожести с отсутствующими полями"""
    print("=== Тест схожести с отсутствующими полями ===")
    
    service = SimilarityService()
    
    # Создаем материал и элемент прайс-листа с отсутствующими бредом и спецификациями
    material = Material(
        id="1",
        name="Подшипник LM25-OPUU",
        description="Подшипник LM25-OPUU",
        category="Общая",
        brand=None,  # Отсутствует
        model=None,
        specifications={},  # Пустые спецификации
        unit="шт",
        created_at=datetime.now()
    )
    
    price_item = PriceListItem(
        id="1",
        material_name="Подшипник LM25-OPUU",
        description="Подшипник LM25-OPUU",
        price=100.0,
        currency="RUB",
        supplier="Поставщик",
        category="Общая",
        brand=None,  # Отсутствует
        unit="шт",
        specifications={},  # Пустые спецификации
        updated_at=datetime.now()
    )
    
    # Рассчитываем схожесть
    similarity_percentage, details = service.calculate_material_similarity(material, price_item)
    
    print(f"Общая схожесть: {similarity_percentage:.2f}%")
    print("Детали:")
    for field, value in details.items():
        print(f"  {field}: {value:.2f}%")
    
    # Ожидается 100%, так как все заполненные поля идентичны
    # Расчет: название (100% * 40%) + описание (100% * 20%) + категория (100% * 15%)
    # Общий вес активных полей: 40% + 20% + 15% = 75%
    # Итого: (100% * 75%) / 75% = 100%
    
    expected_percentage = 100.0
    if abs(similarity_percentage - expected_percentage) < 0.01:
        print("Схожесть правильно рассчитана для отсутствующих полей")
        return True
    else:
        print(f"Ошибка: ожидалось {expected_percentage}%, получено {similarity_percentage:.2f}%")
        return False

if __name__ == "__main__":
    success = test_missing_fields_similarity()
    print("\n" + "=" * 50)
    if success:
        print("Тест пройден успешно!")
    else:
        print("Тест не пройден")