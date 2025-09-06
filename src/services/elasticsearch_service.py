from elasticsearch import Elasticsearch
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..models.material import Material, PriceListItem


logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Сервис для работы с Elasticsearch"""
    
    def __init__(self, host: str = 'localhost', port: int = 9200, username: str = None, password: str = None):
        """
        Инициализация подключения к Elasticsearch
        
        Args:
            host: Хост Elasticsearch
            port: Порт Elasticsearch
            username: Имя пользователя (опционально)
            password: Пароль (опционально)
        """
        self.host = host
        self.port = port
        
        # Настройка подключения с короткими таймаутами
        if username and password:
            self.es = Elasticsearch(
                [f"http://{host}:{port}"],
                basic_auth=(username, password),
                verify_certs=False,
                request_timeout=3,
                max_retries=1,
                retry_on_timeout=False
            )
        else:
            self.es = Elasticsearch(
                [f"http://{host}:{port}"],
                request_timeout=3,
                max_retries=1,
                retry_on_timeout=False
            )
        
        # Названия индексов
        self.materials_index = 'materials'
        self.price_list_index = 'price_list'
        
        logger.info(f"Initialized Elasticsearch connection to {host}:{port}")
    
    def check_connection(self) -> bool:
        """Проверка подключения к Elasticsearch"""
        try:
            return self.es.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            return False
    
    def create_materials_index(self) -> bool:
        """Создание индекса для материалов"""
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "suggest": {"type": "completion"}
                        }
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "category": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "brand": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "model": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "specifications": {"type": "object"},
                    "unit": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "full_text": {
                        "type": "text",
                        "analyzer": "standard"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "russian": {
                            "tokenizer": "standard",
                            "filter": ["lowercase", "russian_stop"]
                        }
                    },
                    "filter": {
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": ["и", "в", "на", "с", "для", "по", "от", "к", "о", "а", "но", "что", "как", "это", "все", "еще", "ее", "их", "чем", "же"]
                        }
                    }
                }
            }
        }
        
        try:
            if self.es.indices.exists(index=self.materials_index):
                self.es.indices.delete(index=self.materials_index)
                logger.info(f"Deleted existing index: {self.materials_index}")
            
            self.es.indices.create(index=self.materials_index, body=mapping)
            logger.info(f"Created materials index: {self.materials_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to create materials index: {e}")
            return False
    
    def create_price_list_index(self) -> bool:
        """Создание индекса для прайс-листа"""
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "material_name": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "suggest": {"type": "completion"}
                        }
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "price": {"type": "float"},
                    "currency": {"type": "keyword"},
                    "supplier": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "category": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "brand": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },
                    "unit": {"type": "keyword"},
                    "specifications": {"type": "object"},
                    "updated_at": {"type": "date"},
                    "full_text": {
                        "type": "text",
                        "analyzer": "standard"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }
        
        try:
            if self.es.indices.exists(index=self.price_list_index):
                self.es.indices.delete(index=self.price_list_index)
                logger.info(f"Deleted existing index: {self.price_list_index}")
            
            self.es.indices.create(index=self.price_list_index, body=mapping)
            logger.info(f"Created price list index: {self.price_list_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to create price list index: {e}")
            return False
    
    def index_materials(self, materials: List[Material]) -> bool:
        """Индексация материалов"""
        try:
            for material in materials:
                doc = material.to_dict()
                self.es.index(
                    index=self.materials_index,
                    id=material.id,
                    body=doc
                )
            
            # Обновление индекса
            self.es.indices.refresh(index=self.materials_index)
            logger.info(f"Indexed {len(materials)} materials")
            return True
        except Exception as e:
            logger.error(f"Failed to index materials: {e}")
            return False
    
    def index_price_list(self, price_items: List[PriceListItem]) -> bool:
        """Индексация прайс-листа"""
        try:
            for item in price_items:
                doc = item.to_dict()
                self.es.index(
                    index=self.price_list_index,
                    id=item.id,
                    body=doc
                )
            
            # Обновление индекса
            self.es.indices.refresh(index=self.price_list_index)
            logger.info(f"Indexed {len(price_items)} price list items")
            return True
        except Exception as e:
            logger.error(f"Failed to index price list: {e}")
            return False
    
    def search_materials(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """Поиск материалов"""
        search_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description^2", "full_text", "brand^2", "category"],
                    "fuzziness": "AUTO",
                    "type": "best_fields"
                }
            },
            "size": size
        }
        
        try:
            response = self.es.search(index=self.materials_index, body=search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Failed to search materials: {e}")
            return []
    
    def search_price_list(self, query: str, size: int = 50) -> List[Dict[str, Any]]:
        """Поиск в прайс-листе"""
        search_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["material_name^3", "description^2", "full_text", "brand^2", "category"],
                    "fuzziness": "AUTO",
                    "type": "best_fields"
                }
            },
            "size": size
        }
        
        try:
            response = self.es.search(index=self.price_list_index, body=search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Failed to search price list: {e}")
            return []
    
    def search_materials_by_name(self, material_name: str, size: int = 10) -> List[Dict[str, Any]]:
        """Поиск материалов по названию с акцентом на точное совпадение"""
        search_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match_phrase": {
                                "name": {
                                    "query": material_name,
                                    "boost": 3.0
                                }
                            }
                        },
                        {
                            "match": {
                                "name": {
                                    "query": material_name,
                                    "fuzziness": "AUTO",
                                    "boost": 2.0
                                }
                            }
                        },
                        {
                            "multi_match": {
                                "query": material_name,
                                "fields": ["name^2", "description", "full_text"],
                                "fuzziness": "AUTO",
                                "type": "best_fields"
                            }
                        }
                    ]
                }
            },
            "size": size
        }
        
        try:
            response = self.es.search(index=self.materials_index, body=search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Failed to search materials by name '{material_name}': {e}")
            return []
    
    def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """Получение материала по ID"""
        try:
            response = self.es.get(index=self.materials_index, id=material_id)
            return response
        except Exception as e:
            logger.error(f"Failed to get material {material_id}: {e}")
            return None
    
    def get_all_materials(self, size: int = 1000) -> List[Dict[str, Any]]:
        """Получение всех материалов"""
        search_query = {
            "query": {"match_all": {}},
            "size": size
        }
        
        try:
            response = self.es.search(index=self.materials_index, body=search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Failed to get all materials: {e}")
            return []
    
    def delete_index(self, index_name: str) -> bool:
        """Удаление индекса"""
        try:
            if self.es.indices.exists(index=index_name):
                self.es.indices.delete(index=index_name)
                logger.info(f"Deleted index: {index_name}")
                return True
            else:
                logger.info(f"Index {index_name} does not exist")
                return True
        except Exception as e:
            logger.error(f"Failed to delete index {index_name}: {e}")
            return False