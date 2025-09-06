#!/usr/bin/env python3
"""
Тест расчета схожести с частично заполненными полями
"""

from src.services.similarity_service import SimilarityService
from src.models.material import Material, PriceListItem
from datetime import datetime

def test_partial_fields_similarity():
    """Тест расчета схожести с частично заполненными полями"""
    print("=== Тест схожести с частично заполненными полями ===")
    
    service = SimilarityService()
    
    # Создаем материал без бренда и элемент прайс-листа с брендом
    material = Material(
        id="1",
        name="Подшипник LM25-OPUU",
        description="Подшипник LM25-OPUU",
        category="Общая",
        brand=None,  # Отсутствует в материале
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
        brand="DINROLL",  # Есть в прайс-листе
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
    
    # Ожидается менее 100%, так как бренд есть только у одного
    # Расчет: название (100% * 40%) + описание (100% * 20%) + категория (100% * 15%) + бренд (50% * 15%)
    # Общий вес всех полей: 40% + 20% + 15% + 15% = 90%
    # Итого: (40% + 20% + 15% + 7.5%) / 90% ≈ 91.67%
    
    expected_min = 85.0  # Ожидаем как минимум 85%
    expected_max = 95.0  # Но не более 95%
    
    if expected_min <= similarity_percentage <= expected_max:
        print(f"Схожесть корректно учитывает частичные поля ({expected_min}%-{expected_max}%)")
        return True
    else:
        print(f"Ошибка: ожидалось {expected_min}%-{expected_max}%, получено {similarity_percentage:.2f}%")
        return False

if __name__ == "__main__":
    success = test_partial_fields_similarity()
    print("\n" + "=" * 50)
    if success:
        print("Тест пройден успешно!")
    else:
        print("Тест не пройден")