#!/usr/bin/env python3
"""
Модуль для форматирования результатов сопоставления в структурированный JSON
"""

import json
from typing import List, Dict, Any, Optional
from ..models.material import Material, PriceListItem, SearchResult


class MatchingResultFormatter:
    """Класс для форматирования результатов сопоставления"""
    
    def __init__(self, max_matches: int = 7):
        """
        Инициализация форматтера
        
        Args:
            max_matches: Максимальное количество вариантов для каждого материала (по умолчанию 7)
        """
        self.max_matches = max_matches
        self.results_data = []
        self.selected_matches = {}
    
    def format_matching_results(
        self,
        matching_results: Dict[str, List[SearchResult]],
        materials_order: List[str] = None,
        materials_list: List = None
    ) -> List[Dict[str, Any]]:
        """
        Форматирование результатов сопоставления в структурированный JSON
        
        Args:
            matching_results: Словарь с результатами сопоставления
            materials_order: Список ID материалов в желаемом порядке
            
        Returns:
            Список словарей в требуемом формате
        """
        formatted_results = []
        
        # Если задан порядок материалов, используем его
        if materials_order:
            material_ids_to_process = materials_order
        else:
            material_ids_to_process = list(matching_results.keys())
        
        for material_id in material_ids_to_process:
            search_results = matching_results.get(material_id, [])
            if not search_results:
                # Если нет результатов для материала, ищем его название из списка материалов
                material_name = "Unknown"
                if materials_list:
                    for material in materials_list:
                        if material.id == material_id:
                            material_name = material.name or "Unknown"
                            break

                formatted_results.append({
                    "material_id": material_id,
                    "material_name": material_name,
                    "matches": []
                })
                continue
            
            # Берем информацию о материале из первого результата
            first_result = search_results[0]
            material_name = first_result.material.name if first_result.material else "Unknown"
            
            # Сортируем по релевантности (similarity_percentage) и берем топ N
            sorted_results = sorted(
                search_results, 
                key=lambda x: x.similarity_percentage, 
                reverse=True
            )[:self.max_matches]
            
            # Форматируем каждый вариант
            matches = []
            for result in sorted_results:
                match = {
                    "variant_id": result.price_item.id,
                    "variant_name": result.price_item.material_name,
                    "price": result.price_item.price,
                    "relevance": round(result.similarity_percentage / 100, 4),  # Переводим в диапазон 0-1
                    "supplier": result.price_item.supplier,
                    "brand": result.price_item.brand or "",
                    "article": result.price_item.article or "",
                    "class_code": result.price_item.class_code or "",
                    "similarity_details": {
                        "name": result.similarity_details.get("name", 0),
                        "description": result.similarity_details.get("description", 0),
                        "category": result.similarity_details.get("category", 0),
                        "brand": result.similarity_details.get("brand", 0)
                    }
                }
                matches.append(match)
            
            formatted_result = {
                "material_id": material_id,
                "material_name": material_name,
                "matches": matches
            }
            
            formatted_results.append(formatted_result)
            
        self.results_data = formatted_results
        return formatted_results
    
    def select_variant(self, material_id: str, variant_id: str) -> Dict[str, Any]:
        """
        Выбор варианта для конкретного материала
        
        Args:
            material_id: ID материала
            variant_id: ID выбранного варианта
            
        Returns:
            Обновленная запись материала или сообщение об ошибке
        """
        # Находим материал в результатах
        material_data = None
        selected_variant = None
        
        for result in self.results_data:
            if str(result["material_id"]) == str(material_id):
                material_data = result
                # Ищем вариант среди matches
                for match in result.get("matches", []):
                    if str(match["variant_id"]) == str(variant_id):
                        selected_variant = match
                        break
                break
        
        if not material_data:
            return {"error": "Material not found"}
        
        if not selected_variant:
            return {"error": "Variant not found"}
        
        # Сохраняем выбор
        self.selected_matches[material_id] = selected_variant
        
        # Возвращаем обновленную структуру
        return {
            "material_id": material_id,
            "material_name": material_data["material_name"],
            "selected_match": selected_variant
        }
    
    def get_final_selection(self) -> List[Dict[str, Any]]:
        """
        Получение финального списка с выбранными вариантами
        
        Returns:
            Список материалов с выбранными вариантами
        """
        final_results = []
        
        for result in self.results_data:
            material_id = result["material_id"]
            
            if material_id in self.selected_matches:
                # Если для материала выбран вариант
                final_results.append({
                    "material_id": material_id,
                    "material_name": result["material_name"],
                    "selected_match": self.selected_matches[material_id]
                })
            else:
                # Если вариант не выбран, включаем все matches
                final_results.append(result)
        
        return final_results
    
    def export_to_json(
        self, 
        output_path: str, 
        include_unselected: bool = True,
        pretty: bool = True
    ) -> bool:
        """
        Экспорт результатов в JSON файл
        
        Args:
            output_path: Путь к выходному файлу
            include_unselected: Включать ли материалы без выбранных вариантов
            pretty: Форматировать ли JSON для читаемости
            
        Returns:
            True при успешном сохранении
        """
        try:
            if include_unselected:
                data_to_export = self.get_final_selection()
            else:
                # Только материалы с выбранными вариантами
                data_to_export = [
                    {
                        "material_id": material_id,
                        "material_name": self._get_material_name(material_id),
                        "selected_match": match
                    }
                    for material_id, match in self.selected_matches.items()
                ]
            
            with open(output_path, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data_to_export, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(data_to_export, f, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False
    
    def _get_material_name(self, material_id: str) -> str:
        """Получение имени материала по ID"""
        for result in self.results_data:
            if str(result["material_id"]) == str(material_id):
                return result["material_name"]
        return "Unknown"
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по результатам
        
        Returns:
            Словарь со статистикой
        """
        total_materials = len(self.results_data)
        materials_with_matches = sum(
            1 for r in self.results_data if r.get("matches")
        )
        total_variants = sum(
            len(r.get("matches", [])) for r in self.results_data
        )
        selected_count = len(self.selected_matches)
        
        avg_relevance = 0
        if total_variants > 0:
            all_relevances = []
            for result in self.results_data:
                for match in result.get("matches", []):
                    all_relevances.append(match["relevance"])
            avg_relevance = sum(all_relevances) / len(all_relevances) if all_relevances else 0
        
        return {
            "total_materials": total_materials,
            "materials_with_matches": materials_with_matches,
            "materials_without_matches": total_materials - materials_with_matches,
            "total_variants_found": total_variants,
            "variants_selected": selected_count,
            "average_relevance": round(avg_relevance, 4),
            "selection_rate": round(selected_count / total_materials * 100, 2) if total_materials > 0 else 0
        }