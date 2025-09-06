#!/usr/bin/env python3
"""
Приложение для поиска материалов с процентом похожести
Основной интерфейс для работы с системой сопоставления материалов и прайс-листов
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
import time

from .models.material import Material, PriceListItem
from .services.elasticsearch_service import ElasticsearchService
from .services.similarity_service import SimilarityService
from .services.matching_service import MaterialMatchingService
from .utils.data_loader import MaterialLoader, PriceListLoader, DataExporter


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('material_matcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Подавляем избыточные логи от Elasticsearch
logging.getLogger('elastic_transport').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class MaterialMatcherApp:
    """Главный класс приложения для сопоставления материалов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация приложения
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config or self._get_default_config()
        
        # Инициализация сервисов
        self.es_service = ElasticsearchService(
            host=self.config.get('elasticsearch', {}).get('host', 'localhost'),
            port=self.config.get('elasticsearch', {}).get('port', 9200),
            username=self.config.get('elasticsearch', {}).get('username'),
            password=self.config.get('elasticsearch', {}).get('password')
        )
        
        self.similarity_service = SimilarityService()
        self.matching_service = MaterialMatchingService(self.es_service, self.similarity_service)
        
        logger.info("MaterialMatcher application initialized successfully")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Получение конфигурации по умолчанию"""
        return {
            'elasticsearch': {
                'host': 'localhost',
                'port': 9200
            },
            'matching': {
                'similarity_threshold': 20.0,
                'max_results_per_material': 10,
                'max_workers': 4
            }
        }
    
    def setup_indices(self) -> bool:
        """Создание индексов в Elasticsearch"""
        logger.info("Setting up Elasticsearch indices...")
        
        materials_success = self.es_service.create_materials_index()
        price_list_success = self.es_service.create_price_list_index()
        
        if materials_success and price_list_success:
            logger.info("Indices created successfully")
            return True
        else:
            logger.error("Failed to create indices")
            return False
    
    def load_materials(self, file_path: str, file_format: str = 'auto') -> List[Material]:
        """
        Загрузка материалов из файла
        
        Args:
            file_path: Путь к файлу с материалами
            file_format: Формат файла ('csv', 'excel', 'json', 'auto')
            
        Returns:
            Список загруженных материалов
        """
        logger.info(f"Loading materials from {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Автоопределение формата
        if file_format == 'auto':
            extension = path.suffix.lower()
            if extension in ['.csv']:
                file_format = 'csv'
            elif extension in ['.xlsx', '.xls']:
                file_format = 'excel'
            elif extension in ['.json']:
                file_format = 'json'
            else:
                logger.error(f"Unsupported file format: {extension}")
                return []
        
        try:
            if file_format == 'csv':
                materials = MaterialLoader.load_from_csv(str(path))
            elif file_format == 'excel':
                materials = MaterialLoader.load_from_excel(str(path))
            elif file_format == 'json':
                materials = MaterialLoader.load_from_json(str(path))
            else:
                logger.error(f"Unsupported format: {file_format}")
                return []
            
            logger.info(f"Loaded {len(materials)} materials")
            return materials
            
        except Exception as e:
            logger.error(f"Error loading materials: {e}")
            return []
    
    def load_price_list(self, file_path: str, file_format: str = 'auto') -> List[PriceListItem]:
        """
        Загрузка прайс-листа из файла
        
        Args:
            file_path: Путь к файлу с прайс-листом
            file_format: Формат файла ('csv', 'excel', 'json', 'auto')
            
        Returns:
            Список загруженных элементов прайс-листа
        """
        logger.info(f"Loading price list from {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Автоопределение формата
        if file_format == 'auto':
            extension = path.suffix.lower()
            if extension in ['.csv']:
                file_format = 'csv'
            elif extension in ['.xlsx', '.xls']:
                file_format = 'excel'
            elif extension in ['.json']:
                file_format = 'json'
            else:
                logger.error(f"Unsupported file format: {extension}")
                return []
        
        try:
            if file_format == 'csv':
                price_items = PriceListLoader.load_from_csv(str(path))
            elif file_format == 'excel':
                price_items = PriceListLoader.load_from_excel(str(path))
            elif file_format == 'json':
                price_items = PriceListLoader.load_from_json(str(path))
            else:
                logger.error(f"Unsupported format: {file_format}")
                return []
            
            logger.info(f"Loaded {len(price_items)} price list items")
            return price_items
            
        except Exception as e:
            logger.error(f"Error loading price list: {e}")
            return []
    
    def index_data(self, materials: List[Material] = None, price_items: List[PriceListItem] = None) -> bool:
        """
        Индексация данных в Elasticsearch
        
        Args:
            materials: Список материалов для индексации
            price_items: Список элементов прайс-листа для индексации
            
        Returns:
            True если индексация прошла успешно
        """
        success = True
        
        if materials:
            logger.info(f"Indexing {len(materials)} materials...")
            if not self.es_service.index_materials(materials):
                success = False
        
        if price_items:
            logger.info(f"Indexing {len(price_items)} price list items...")
            if not self.es_service.index_price_list(price_items):
                success = False
        
        return success
    
    def run_matching(self, materials: List[Material] = None) -> Dict[str, List]:
        """
        Запуск процесса сопоставления материалов с прайс-листом
        
        Args:
            materials: Список материалов для сопоставления (если None, загружаются все из индекса)
            
        Returns:
            Результаты сопоставления
        """
        if materials is None:
            logger.info("Loading all materials from index...")
            es_materials = self.es_service.get_all_materials()
            materials = [Material.from_dict(item['_source']) for item in es_materials]
        
        if not materials:
            logger.warning("No materials found for matching")
            return {}
        
        logger.info(f"Starting matching process for {len(materials)} materials...")
        start_time = time.time()
        
        # Получение параметров из конфигурации
        similarity_threshold = self.config.get('matching', {}).get('similarity_threshold', 20.0)
        max_results = self.config.get('matching', {}).get('max_results_per_material', 10)
        max_workers = self.config.get('matching', {}).get('max_workers', 4)
        
        results = self.matching_service.match_materials_batch(
            materials,
            similarity_threshold=similarity_threshold,
            max_results_per_material=max_results,
            max_workers=max_workers
        )
        
        end_time = time.time()
        logger.info(f"Matching completed in {end_time - start_time:.2f} seconds")
        
        # Получение статистики
        stats = self.matching_service.get_matching_statistics(results)
        logger.info(f"Matching statistics: {stats}")
        
        return results
    
    def export_results(self, results: Dict[str, List], output_path: str, export_format: str = 'json'):
        """
        Экспорт результатов в файл
        
        Args:
            results: Результаты сопоставления
            output_path: Путь для сохранения результатов
            export_format: Формат экспорта ('json', 'csv')
        """
        logger.info(f"Exporting results to {output_path}")
        
        # Преобразуем результаты в словари
        export_data = []
        for material_id, matches in results.items():
            for match in matches:
                export_data.append(match.to_dict())
        
        try:
            if export_format == 'json':
                DataExporter.export_results_to_json(export_data, output_path)
            elif export_format == 'csv':
                DataExporter.export_results_to_csv(export_data, output_path)
            elif export_format == 'xlsx':
                DataExporter.export_results_to_xlsx(export_data, output_path)
            else:
                logger.error(f"Unsupported export format: {export_format}")
                return
            
            logger.info(f"Results exported successfully to {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
    
    def get_material_matches(self, material_id: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Получение соответствий для конкретного материала
        
        Args:
            material_id: ID материала
            top_n: Количество лучших результатов
            
        Returns:
            Список соответствий
        """
        material_data = self.es_service.get_material_by_id(material_id)
        if not material_data:
            logger.error(f"Material with ID {material_id} not found")
            return []
        
        material = Material.from_dict(material_data['_source'])
        matches = self.matching_service.find_best_matches_for_material(material, top_n)
        
        return [match.to_dict() for match in matches]
    
    def search_material_by_name(self, material_name: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск соответствий для материала по названию
        
        Args:
            material_name: Название материала для поиска
            top_n: Количество лучших результатов
            
        Returns:
            Список соответствий
        """
        # Поиск материала по названию в индексе
        try:
            search_results = self.es_service.search_materials_by_name(material_name)
            if not search_results:
                logger.warning(f"Material '{material_name}' not found in index")
                return []
            
            # Берем первый (наиболее релевантный) результат
            material_data = search_results[0]
            material = Material.from_dict(material_data['_source'])
            
            # Ищем соответствия для этого материала
            matches = self.matching_service.find_best_matches_for_material(material, top_n)
            
            return [match.to_dict() for match in matches]
            
        except Exception as e:
            logger.error(f"Error searching material by name '{material_name}': {e}")
            return []


def create_sample_config() -> Dict[str, Any]:
    """Создание примера конфигурации"""
    return {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "username": None,
            "password": None
        },
        "matching": {
            "similarity_threshold": 20.0,
            "max_results_per_material": 10,
            "max_workers": 4
        }
    }


def main():
    """Главная функция для запуска приложения из командной строки"""
    parser = argparse.ArgumentParser(description="Material Matching Application")
    
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--materials', type=str, help='Path to materials file')
    parser.add_argument('--price-list', type=str, help='Path to price list file')
    parser.add_argument('--output', type=str, default='results.json', help='Output file path')
    parser.add_argument('--format', type=str, choices=['json', 'csv', 'xlsx'], default='json', help='Output format')
    parser.add_argument('--setup', action='store_true', help='Setup Elasticsearch indices')
    parser.add_argument('--threshold', type=float, default=20.0, help='Similarity threshold (0-100)')
    
    args = parser.parse_args()
    
    # Загрузка конфигурации
    config = None
    if args.config and Path(args.config).exists():
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # Обновление конфигурации из аргументов командной строки
    if config is None:
        config = create_sample_config()
    
    if args.threshold:
        config['matching']['similarity_threshold'] = args.threshold
    
    # Инициализация приложения
    app = MaterialMatcherApp(config)
    
    # Создание индексов если требуется
    if args.setup:
        if not app.setup_indices():
            sys.exit(1)
    
    # Загрузка и индексация данных
    materials = []
    price_items = []
    
    if args.materials:
        materials = app.load_materials(args.materials)
        if not materials:
            sys.exit(1)
    
    if args.price_list:
        price_items = app.load_price_list(args.price_list)
        if not price_items:
            sys.exit(1)
    
    if materials or price_items:
        if not app.index_data(materials, price_items):
            logger.error("Failed to index data")
            sys.exit(1)
    
    # Запуск сопоставления
    if materials:
        results = app.run_matching(materials)
        
        if results:
            app.export_results(results, args.output, args.format)
            logger.info(f"Process completed. Results saved to {args.output}")
        else:
            logger.warning("No results to export")
    else:
        logger.info("No materials provided for matching")


if __name__ == '__main__':
    main()