from typing import List, Dict, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from ..models.material import Material, PriceListItem, SearchResult
from ..services.elasticsearch_service import ElasticsearchService
from ..services.similarity_service import SimilarityService


logger = logging.getLogger(__name__)


class MaterialMatchingService:
    """Сервис для сопоставления материалов с прайс-листом"""
    
    def __init__(self, elasticsearch_service: ElasticsearchService, similarity_service: SimilarityService):
        self.es_service = elasticsearch_service
        self.similarity_service = similarity_service
        self.lock = Lock()
        
    def match_material_with_price_list(self, 
                                       material: Material,
                                       similarity_threshold: float = 20.0,
                                       max_results: int = 10) -> List[SearchResult]:
        """
        Поиск соответствий для одного материала в прайс-листе
        
        Args:
            material: Материал для поиска
            similarity_threshold: Минимальный процент похожести
            max_results: Максимальное количество результатов
            
        Returns:
            Список результатов поиска с процентом похожести
        """
        results = []
        
        # Формируем поисковый запрос из данных материала
        query_parts = []
        if material.name:
            query_parts.append(material.name)
        if material.brand:
            query_parts.append(material.brand)
        if material.category:
            query_parts.append(material.category)
        
        query = " ".join(query_parts)
        
        if not query.strip():
            logger.warning(f"Empty query for material {material.id}")
            return results
        
        try:
            # Поиск в Elasticsearch
            es_results = self.es_service.search_price_list(query, size=50)
            
            for es_result in es_results:
                try:
                    # Создаем объект PriceListItem из результата
                    price_item_data = es_result['_source']
                    price_item = PriceListItem.from_dict(price_item_data)
                    
                    # Рассчитываем похожесть
                    similarity_percentage, similarity_details = self.similarity_service.calculate_material_similarity(
                        material, price_item
                    )
                    
                    # Фильтруем по порогу похожести
                    if similarity_percentage >= similarity_threshold:
                        search_result = SearchResult(
                            material=material,
                            price_item=price_item,
                            similarity_percentage=similarity_percentage,
                            similarity_details=similarity_details,
                            elasticsearch_score=es_result['_score']
                        )
                        results.append(search_result)
                        
                except Exception as e:
                    logger.error(f"Error processing price list item: {e}")
                    continue
            
            # Сортируем по проценту похожести
            results = self.similarity_service.sort_by_similarity(results)
            
            # Ограничиваем количество результатов
            results = results[:max_results]
            
        except Exception as e:
            logger.error(f"Error matching material {material.id}: {e}")
        
        return results
    
    def match_materials_batch(self,
                              materials: List[Material],
                              similarity_threshold: float = 20.0,
                              max_results_per_material: int = 10,
                              max_workers: int = 4,
                              progress_callback=None) -> Dict[str, List[SearchResult]]:
        """
        Пакетное сопоставление материалов с прайс-листом
        
        Args:
            materials: Список материалов для поиска
            similarity_threshold: Минимальный процент похожести
            max_results_per_material: Максимальное количество результатов на материал
            max_workers: Количество потоков для параллельной обработки
            progress_callback: Функция обратного вызова для отслеживания прогресса (processed, total, current_material)
            
        Returns:
            Словарь где ключ - ID материала, значение - список результатов поиска
        """
        results = {}
        completed_count = 0
        total_count = len(materials)
        
        logger.info(f"Starting batch matching for {total_count} materials")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Запускаем задачи
            future_to_material = {
                executor.submit(
                    self.match_material_with_price_list,
                    material,
                    similarity_threshold,
                    max_results_per_material
                ): material for material in materials
            }
            
            # Собираем результаты
            for future in as_completed(future_to_material):
                material = future_to_material[future]
                try:
                    material_results = future.result()
                    results[material.id] = material_results
                    
                    with self.lock:
                        completed_count += 1
                        
                        # Вызов прогресс callback если предоставлен
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total_count, material.name)
                            except Exception as e:
                                logger.warning(f"Progress callback error: {e}")
                        
                        if completed_count % 10 == 0:
                            logger.info(f"Completed matching for {completed_count}/{total_count} materials")
                            
                except Exception as e:
                    logger.error(f"Error matching material {material.id}: {e}")
                    results[material.id] = []
                    
                    # Все равно обновляем прогресс даже при ошибке
                    with self.lock:
                        completed_count += 1
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total_count, material.name if material else "Unknown")
                            except Exception as e:
                                logger.warning(f"Progress callback error: {e}")
        
        logger.info(f"Batch matching completed. Processed {completed_count} materials")
        return results
    
    def find_best_matches_for_material(self,
                                       material: Material,
                                       top_n: int = 5) -> List[SearchResult]:
        """
        Поиск лучших соответствий для материала
        
        Args:
            material: Материал для поиска
            top_n: Количество лучших результатов
            
        Returns:
            Список лучших результатов поиска
        """
        all_results = self.match_material_with_price_list(
            material, 
            similarity_threshold=0.0,  # Без фильтрации по порогу
            max_results=100
        )
        
        return self.similarity_service.get_top_matches(all_results, top_n)
    
    def find_exact_matches(self,
                           materials: List[Material],
                           exact_threshold: float = 90.0) -> Dict[str, List[SearchResult]]:
        """
        Поиск точных соответствий (с высоким процентом похожести)
        
        Args:
            materials: Список материалов для поиска
            exact_threshold: Минимальный процент для считания совпадения точным
            
        Returns:
            Словарь с точными соответствиями
        """
        all_results = self.match_materials_batch(materials, similarity_threshold=exact_threshold)
        
        # Фильтруем только результаты с высоким процентом похожести
        exact_matches = {}
        for material_id, results in all_results.items():
            exact_results = [r for r in results if r.similarity_percentage >= exact_threshold]
            if exact_results:
                exact_matches[material_id] = exact_results
        
        return exact_matches
    
    def get_matching_statistics(self, results: Dict[str, List[SearchResult]]) -> Dict[str, Any]:
        """
        Получение статистики по результатам сопоставления
        
        Args:
            results: Результаты сопоставления материалов
            
        Returns:
            Словарь со статистикой
        """
        total_materials = len(results)
        materials_with_matches = sum(1 for matches in results.values() if matches)
        total_matches = sum(len(matches) for matches in results.values())
        
        # Статистика по процентам похожести
        all_percentages = []
        for matches in results.values():
            all_percentages.extend([match.similarity_percentage for match in matches])
        
        statistics = {
            'total_materials': total_materials,
            'materials_with_matches': materials_with_matches,
            'materials_without_matches': total_materials - materials_with_matches,
            'match_rate': (materials_with_matches / total_materials * 100) if total_materials > 0 else 0,
            'total_matches': total_matches,
            'average_matches_per_material': total_matches / total_materials if total_materials > 0 else 0
        }
        
        if all_percentages:
            statistics.update({
                'average_similarity': sum(all_percentages) / len(all_percentages),
                'max_similarity': max(all_percentages),
                'min_similarity': min(all_percentages)
            })
        
        return statistics
    
    def export_results_summary(self, results: Dict[str, List[SearchResult]]) -> List[Dict[str, Any]]:
        """
        Экспорт сводки результатов для отчетности
        
        Args:
            results: Результаты сопоставления
            
        Returns:
            Список словарей с сводной информацией
        """
        summary = []
        
        for material_id, matches in results.items():
            if matches:
                # Берем лучший результат
                best_match = max(matches, key=lambda x: x.similarity_percentage)
                
                summary_item = {
                    'material_id': material_id,
                    'material_name': best_match.material.name,
                    'material_category': best_match.material.category,
                    'best_match_found': True,
                    'best_match_similarity': best_match.similarity_percentage,
                    'best_match_price_item_name': best_match.price_item.material_name,
                    'best_match_supplier': best_match.price_item.supplier,
                    'best_match_price': best_match.price_item.price,
                    'best_match_currency': best_match.price_item.currency,
                    'total_matches_found': len(matches)
                }
            else:
                # Получаем информацию о материале
                try:
                    material_data = self.es_service.get_material_by_id(material_id)
                    if material_data:
                        material = Material.from_dict(material_data['_source'])
                        material_name = material.name
                        material_category = material.category
                    else:
                        material_name = "Unknown"
                        material_category = "Unknown"
                except:
                    material_name = "Unknown"
                    material_category = "Unknown"
                
                summary_item = {
                    'material_id': material_id,
                    'material_name': material_name,
                    'material_category': material_category,
                    'best_match_found': False,
                    'best_match_similarity': 0,
                    'best_match_price_item_name': None,
                    'best_match_supplier': None,
                    'best_match_price': None,
                    'best_match_currency': None,
                    'total_matches_found': 0
                }
            
            summary.append(summary_item)
        
        return summary