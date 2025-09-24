from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
import threading
import json
import hashlib
from functools import lru_cache
from collections import defaultdict

from ..models.material import Material, PriceListItem


logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Сервис для работы с Elasticsearch"""
    
    def __init__(self, host: str = 'localhost', port: int = 9200, username: str = None, password: str = None,
                 bulk_size: int = 1000, max_workers: int = 6):
        """
        Инициализация подключения к Elasticsearch с оптимизацией производительности
        
        Args:
            host: Хост Elasticsearch
            port: Порт Elasticsearch
            username: Имя пользователя (опционально)
            password: Пароль (опционально)
            bulk_size: Размер пакета для bulk операций (оптимально 500-1000)
            max_workers: Количество потоков для параллельной обработки
        """
        self.host = host
        self.port = port
        self.bulk_size = bulk_size
        self.max_workers = max_workers
        
        # ИСПРАВЛЕНИЕ: Конфигурация подключения для исправления ошибки с NoneType
        connection_config = {
            "request_timeout": 120,     # Увеличено до 2 минут для больших batch операций
            "max_retries": 3,          # Уменьшаем количество повторов для стабильности
            "retry_on_timeout": True,   # Включены повторы при таймауте
            "retry_on_status": [429, 502, 503, 504],  # Повторы для серверных ошибок
            "verify_certs": False,
            # ИСПРАВЛЕНИЕ: Полностью отключаем sniffing для single-node
            "sniff_on_start": False,     # Отключаем sniffing при старте
            "sniff_on_connection_fail": False,  # Отключаем sniffing при ошибках
            "sniff_timeout": None,       # Отключаем timeout для sniffing
            "min_delay_between_sniffing": 60,  # Минимальная задержка между sniffing (исправление для NoneType)
            # Дополнительные настройки для стабильности
            "http_compress": False,      # Отключаем сжатие для упрощения
            "maxsize": 10,              # Уменьшенный connection pool
        }
        
        if username and password:
            self.es = Elasticsearch(
                [f"http://{host}:{port}"],
                basic_auth=(username, password),
                **connection_config
            )
        else:
            self.es = Elasticsearch(
                [f"http://{host}:{port}"],
                **connection_config
            )
        
        # Названия индексов
        self.materials_index = 'materials'
        self.price_list_index = 'price_list'
        
        # ОПТИМИЗАЦИЯ 3: Добавляем thread-local storage для статистики
        self._stats = threading.local()
        self._init_stats()
        
        # ОПТИМИЗАЦИЯ 28: Добавляем кеширование запросов и мониторинг производительности
        self._query_cache = {}
        self._cache_ttl = 300  # 5 минут TTL для кеша
        self._cache_lock = threading.RLock()
        self._performance_metrics = defaultdict(list)
        self._total_queries = 0
        self._cache_hits = 0
        
        logger.info(f"Initialized optimized Elasticsearch connection to {host}:{port}")
        logger.info(f"Performance settings: bulk_size={bulk_size}, max_workers={max_workers}")
        logger.info("Advanced performance monitoring and caching enabled")
    
    def _init_stats(self):
        """Инициализация статистики производительности"""
        if not hasattr(self._stats, 'indexed_docs'):
            self._stats.indexed_docs = 0
            self._stats.indexing_time = 0.0
            self._stats.bulk_operations = 0
    
    def check_connection(self) -> bool:
        """Проверка подключения к Elasticsearch"""
        try:
            # Проверяем доступность через прямой HTTP запрос
            import requests
            response = requests.get('http://localhost:9200', timeout=5)
            return response.status_code == 200
        except ImportError:
            logger.error("requests library not available")
            return False
        except Exception as e:
            logger.error(f"Elasticsearch HTTP connection error: {e}")
            return False
    
    def create_materials_index(self) -> bool:
        """Создание индекса для материалов"""
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized",
                        "fields": {
                            "keyword": {"type": "keyword", "normalizer": "lowercase"},
                            "suggest": {"type": "completion", "analyzer": "simple"},
                            "raw": {"type": "text", "analyzer": "keyword"}
                        }
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized"
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
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized",
                        # ОПТИМИЗАЦИЯ 8: Отключаем norms для экономии памяти
                        "norms": False,
                        # ОПТИМИЗАЦИЯ 24: Отключаем позиционную информацию для экономии места
                        "index_options": "freqs"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,  # Отключаем реплики для single-node setup
                # ОПТИМИЗАЦИЯ 21: Настройки для максимальной производительности индексации
                "refresh_interval": "30s",  # Увеличиваем интервал refresh
                "index.translog.durability": "async",  # Асинхронная запись translog
                "index.translog.sync_interval": "30s",  # Реже синхронизируем translog
                "index.translog.flush_threshold_size": "1gb",  # Больший threshold для flush
                "index.max_result_window": 50000,  # Увеличиваем лимит результатов
                # ОПТИМИЗАЦИЯ 22: Оптимизация памяти и сегментов
                "index.merge.scheduler.max_thread_count": 1,  # Один поток для merge в single-node
                "index.merge.policy.max_merge_at_once": 10,
                "index.merge.policy.segments_per_tier": 10,
                # ОПТИМИЗАЦИЯ 23: Расширенный анализ для русского текста
                "analysis": {
                    "analyzer": {
                        "russian_optimized": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "russian_stop",
                                "russian_keywords",
                                "russian_stemmer",
                                "unique"
                            ]
                        },
                        "search_analyzer": {
                            "type": "custom",
                            "tokenizer": "keyword",
                            "filter": ["lowercase", "trim"]
                        }
                    },
                    "filter": {
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": ["и", "в", "на", "с", "для", "по", "от", "к", "о", "а", "но", "что", "как", "это", "все", "еще", "ее", "их", "чем", "же"]
                        },
                        "russian_keywords": {
                            "type": "keyword_marker",
                            "keywords": ["led", "лед", "автомат", "кабель", "провод"]
                        },
                        "russian_stemmer": {
                            "type": "stemmer",
                            "language": "russian"
                        }
                    }
                }
            }
        }
        
        try:
            if self.es.indices.exists(index=self.materials_index):
                self.es.indices.delete(index=self.materials_index)
                logger.info(f"Deleted existing index: {self.materials_index}")
            
            self.es.indices.create(index=self.materials_index, **mapping)
            logger.info(f"Created materials index: {self.materials_index}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания индекса материалов: {e}")
            # Дополнительная диагностика
            try:
                health_response = self.es.cluster.health()
                health = dict(health_response) if hasattr(health_response, 'keys') else health_response
                status = health.get('status', 'unknown') if isinstance(health, dict) else 'unknown'
                logger.debug(f"Статус кластера: {status}")
            except Exception as health_error:
                logger.debug(f"Не удалось получить статус кластера: {health_error}")
            return False
    
    def create_price_list_index(self) -> bool:
        """Создание индекса для прайс-листа"""
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "material_name": {
                        "type": "text",
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized",
                        "fields": {
                            "keyword": {"type": "keyword", "normalizer": "lowercase"},
                            "suggest": {"type": "completion", "analyzer": "simple"},
                            "raw": {"type": "text", "analyzer": "keyword"}
                        }
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized"
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
                        "analyzer": "russian_optimized",
                        "search_analyzer": "russian_optimized",
                        "norms": False,
                        "index_options": "freqs"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                # Применяем те же оптимизации производительности
                "refresh_interval": "30s",
                "index.translog.durability": "async",
                "index.translog.sync_interval": "30s",
                "index.translog.flush_threshold_size": "1gb",
                "index.max_result_window": 50000,
                "index.merge.scheduler.max_thread_count": 1,
                "index.merge.policy.max_merge_at_once": 10,
                "index.merge.policy.segments_per_tier": 10,
                # Используем ту же конфигурацию анализа
                "analysis": {
                    "analyzer": {
                        "russian_optimized": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "russian_stop",
                                "russian_keywords",
                                "russian_stemmer",
                                "unique"
                            ]
                        }
                    },
                    "filter": {
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": ["и", "в", "на", "с", "для", "по", "от", "к", "о", "а", "но", "что", "как", "это", "все", "еще", "ее", "их", "чем", "же"]
                        },
                        "russian_keywords": {
                            "type": "keyword_marker",
                            "keywords": ["led", "лед", "автомат", "кабель", "провод"]
                        },
                        "russian_stemmer": {
                            "type": "stemmer",
                            "language": "russian"
                        }
                    }
                }
            }
        }
        
        try:
            if self.es.indices.exists(index=self.price_list_index):
                self.es.indices.delete(index=self.price_list_index)
                logger.info(f"Deleted existing index: {self.price_list_index}")
            
            self.es.indices.create(index=self.price_list_index, **mapping)
            logger.info(f"Created price list index: {self.price_list_index}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания индекса прайс-листа: {e}")
            # Дополнительная диагностика
            try:
                health_response = self.es.cluster.health()
                health = dict(health_response) if hasattr(health_response, 'keys') else health_response
                status = health.get('status', 'unknown') if isinstance(health, dict) else 'unknown'
                logger.debug(f"Статус кластера: {status}")
            except Exception as health_error:
                logger.debug(f"Не удалось получить статус кластера: {health_error}")
            return False
    
    def index_materials(self, materials: List[Material]) -> bool:
        """
        ОПТИМИЗИРОВАННАЯ индексация материалов с bulk операциями
        ОПТИМИЗАЦИЯ 10: Bulk indexing вместо последовательной индексации
        """
        if not materials:
            logger.warning("No materials to index")
            return True
        
        start_time = time.time()
        self._init_stats()
        
        try:
            # ОПТИМИЗАЦИЯ 11: Отключаем refresh на время индексации
            self._disable_refresh(self.materials_index)
            
            # Подготовка документов для bulk операции
            actions = []
            for material in materials:
                doc = material.to_dict()
                action = {
                    "_index": self.materials_index,
                    "_id": material.id,
                    "_source": doc
                }
                actions.append(action)
            
            # ОПТИМИЗАЦИЯ 12: Используем parallel_bulk для параллельной обработки
            success_count = 0
            error_count = 0
            
            # ИСПРАВЛЕНИЕ: Упрощенная конфигурация parallel_bulk без проблемных параметров
            for success, info in parallel_bulk(
                self.es,
                actions,
                chunk_size=self.bulk_size,
                thread_count=min(self.max_workers, 4),  # Уменьшаем количество потоков для стабильности
                max_chunk_bytes=104857600,  # 100MB максимум на chunk (уменьшено для стабильности)
                request_timeout=60          # Стандартный timeout
            ):
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    logger.warning(f"Failed to index document: {info}")
            
            # Восстанавливаем refresh и принудительно обновляем
            self._enable_refresh(self.materials_index)
            self.es.indices.refresh(index=self.materials_index)
            
            elapsed_time = time.time() - start_time
            
            # ОПТИМИЗАЦИЯ 13: Логирование производительности
            docs_per_sec = len(materials) / elapsed_time if elapsed_time and elapsed_time > 0 else 0
            logger.info(
                f"Bulk indexed {success_count} materials in {elapsed_time:.2f}s "
                f"({docs_per_sec:.1f} docs/sec) - {error_count} errors"
            )
            
            # Обновляем статистику
            self._stats.indexed_docs += success_count
            self._stats.indexing_time += elapsed_time
            self._stats.bulk_operations += 1
            
            return error_count == 0
            
        except Exception as e:
            # Восстанавливаем refresh в случае ошибки
            try:
                self._enable_refresh(self.materials_index)
            except:
                pass
            logger.error(f"Ошибка массовой индексации материалов: {e}")
            logger.debug(f"Детали ошибки: {type(e).__name__}")
            return False
    
    def index_price_list(self, price_items: List[PriceListItem]) -> bool:
        """
        ОПТИМИЗИРОВАННАЯ индексация прайс-листа с bulk операциями
        ОПТИМИЗАЦИЯ 14: Аналогичные улучшения для прайс-листа
        """
        if not price_items:
            logger.warning("No price list items to index")
            return True
        
        start_time = time.time()
        self._init_stats()
        
        try:
            # Отключаем refresh на время индексации
            self._disable_refresh(self.price_list_index)
            
            # Подготовка документов для bulk операции
            actions = []
            for item in price_items:
                doc = item.to_dict()
                action = {
                    "_index": self.price_list_index,
                    "_id": item.id,
                    "_source": doc
                }
                actions.append(action)
            
            # Параллельная bulk индексация
            success_count = 0
            error_count = 0
            
            # ИСПРАВЛЕНИЕ: Аналогичная упрощенная конфигурация для прайс-листа
            for success, info in parallel_bulk(
                self.es,
                actions,
                chunk_size=self.bulk_size,
                thread_count=min(self.max_workers, 4),  # Уменьшаем количество потоков
                max_chunk_bytes=104857600,  # 100MB максимум на chunk (уменьшено)
                request_timeout=60          # Стандартный timeout
            ):
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    logger.warning(f"Failed to index price list item: {info}")
            
            # Восстанавливаем refresh и принудительно обновляем
            self._enable_refresh(self.price_list_index)
            self.es.indices.refresh(index=self.price_list_index)
            
            elapsed_time = time.time() - start_time
            
            # Логирование производительности
            docs_per_sec = len(price_items) / elapsed_time if elapsed_time and elapsed_time > 0 else 0
            logger.info(
                f"Bulk indexed {success_count} price list items in {elapsed_time:.2f}s "
                f"({docs_per_sec:.1f} docs/sec) - {error_count} errors"
            )
            
            # Обновляем статистику
            self._stats.indexed_docs += success_count
            self._stats.indexing_time += elapsed_time
            self._stats.bulk_operations += 1
            
            return error_count == 0
            
        except Exception as e:
            # Восстанавливаем refresh в случае ошибки
            try:
                self._enable_refresh(self.price_list_index)
            except:
                pass
            logger.error(f"Ошибка массовой индексации прайс-листа: {e}")
            logger.debug(f"Детали ошибки: {type(e).__name__}")
            return False
    
    def search_materials(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """Поиск материалов"""
        # ОПТИМИЗАЦИЯ 26: Улучшенный search query с boost и caching
        search_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name^4", "name.raw^3", "description^2", "full_text"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 2.0
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["brand^2", "category"],
                                "type": "phrase",
                                "boost": 1.5
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            # ОПТИМИЗАЦИЯ 27: Включаем кеширование запросов
            "request_cache": True,
            # Оптимизация: возвращаем только нужные поля для экономии bandwidth
            "_source": ["name", "description", "category", "brand", "specifications"]
        }
        
        try:
            response = self.es.search(index=self.materials_index, **search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Ошибка поиска материалов: {e}")
            logger.debug(f"Поисковый запрос: '{query}'")
            return []
    
    def search_price_list(self, query: str, size: int = 50) -> List[Dict[str, Any]]:
        """Поиск в прайс-листе"""
        # Аналогичная оптимизация для поиска в прайс-листе
        search_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["material_name^4", "material_name.raw^3", "description^2", "full_text"],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 2.0
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["brand^2", "category", "supplier"],
                                "type": "phrase",
                                "boost": 1.5
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "request_cache": True,
            "_source": ["material_name", "description", "price", "currency", "supplier", "category", "brand", "article", "class_code"]
        }
        
        try:
            response = self.es.search(index=self.price_list_index, **search_query)
            return response['hits']['hits']
        except Exception as e:
            logger.error(f"Ошибка поиска в прайс-листе: {e}")
            logger.debug(f"Поисковый запрос: '{query}'")
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
            response = self.es.search(index=self.materials_index, **search_query)
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
            response = self.es.search(index=self.materials_index, **search_query)
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
    
    def _disable_refresh(self, index_name: str):
        """
        ОПТИМИЗАЦИЯ 15: Отключение refresh интервала для быстрой индексации
        """
        try:
            self.es.indices.put_settings(
                index=index_name,
                settings={"refresh_interval": -1}
            )
            logger.debug(f"Disabled refresh for index {index_name}")
        except Exception as e:
            logger.warning(f"Failed to disable refresh for {index_name}: {e}")
    
    def _enable_refresh(self, index_name: str):
        """
        ОПТИМИЗАЦИЯ 16: Восстановление refresh интервала после индексации
        """
        try:
            self.es.indices.put_settings(
                index=index_name,
                settings={"refresh_interval": "30s"}  # Возвращаем к оптимизированному значению
            )
            logger.debug(f"Enabled refresh for index {index_name}")
        except Exception as e:
            logger.warning(f"Failed to enable refresh for {index_name}: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        ОПТИМИЗАЦИЯ 17: Получение статистики производительности индексации
        """
        self._init_stats()
        
        avg_time_per_doc = (self._stats.indexing_time / self._stats.indexed_docs 
                           if self._stats.indexed_docs and self._stats.indexed_docs > 0 else 0)
        
        return {
            "total_indexed_documents": self._stats.indexed_docs,
            "total_indexing_time_seconds": round(self._stats.indexing_time, 2),
            "bulk_operations_count": self._stats.bulk_operations,
            "average_time_per_document_ms": round(avg_time_per_doc * 1000, 3),
            "average_documents_per_second": round(
                self._stats.indexed_docs / self._stats.indexing_time if self._stats.indexing_time and self._stats.indexing_time > 0 else 0, 1
            ),
            "bulk_size": self.bulk_size,
            "max_workers": self.max_workers
        }
    
    def optimize_indices_for_search(self):
        """
        ОПТИМИЗАЦИЯ 18: Оптимизация индексов после массовой индексации для улучшения поиска
        """
        try:
            logger.info("Optimizing indices for search performance...")
            
            # Force merge для уменьшения количества сегментов
            for index_name in [self.materials_index, self.price_list_index]:
                if self.es.indices.exists(index=index_name):
                    self.es.indices.forcemerge(
                        index=index_name,
                        max_num_segments=1,  # Объединяем в один сегмент для максимальной производительности поиска
                        wait_for_completion=True
                    )
                    logger.info(f"Force merged index {index_name}")
            
            logger.info("Index optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize indices: {e}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        ОПТИМИЗАЦИЯ 19: Получение статистики индексов для мониторинга
        """
        try:
            stats = {}
            
            for index_name in [self.materials_index, self.price_list_index]:
                if self.es.indices.exists(index=index_name):
                    index_stats = self.es.indices.stats(index=index_name)
                    index_data = index_stats['indices'][index_name]
                    
                    stats[index_name] = {
                        "document_count": index_data['total']['docs']['count'],
                        "store_size_mb": round(index_data['total']['store']['size_in_bytes'] / 1024 / 1024, 2) if index_data['total']['store']['size_in_bytes'] is not None else 0,
                        "segments_count": index_data['total']['segments']['count'],
                        "indexing_time_ms": index_data['total']['indexing']['index_time_in_millis'],
                        "search_time_ms": index_data['total']['search']['query_time_in_millis'],
                        "search_count": index_data['total']['search']['query_total']
                    }
                else:
                    stats[index_name] = {"status": "index_not_exists"}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """
        ОПТИМИЗАЦИЯ 20: Расширенная проверка здоровья кластера с рекомендациями
        """
        try:
            # Сначала проверяем базовое подключение
            if not self.check_connection():
                return {
                    "connection_healthy": False,
                    "error": "Нет подключения к Elasticsearch",
                    "recommendations": ["Запустите сервер Elasticsearch", "Проверьте настройки подключения"]
                }
            
            # Получаем информацию о здоровье кластера
            health_response = self.es.cluster.health()
            health = dict(health_response) if hasattr(health_response, 'keys') else health_response

            # Получаем статистику кластера
            cluster_stats_response = self.es.cluster.stats()
            cluster_stats = dict(cluster_stats_response) if hasattr(cluster_stats_response, 'keys') else cluster_stats_response
            
            # Анализ производительности
            recommendations = []
            
            # Безопасная проверка pending tasks
            pending_tasks = health.get('number_of_pending_tasks', 0)
            if pending_tasks and isinstance(pending_tasks, (int, float)) and pending_tasks > 10:
                recommendations.append("Большое количество отложенных задач - рассмотрите снижение нагрузки индексации")
            
            # Безопасная проверка active shards
            active_shards_percent = health.get('active_shards_percent_as_number', 100)
            if (active_shards_percent is not None and
                isinstance(active_shards_percent, (int, float)) and
                active_shards_percent < 100):
                recommendations.append("Не все шарды активны - проверьте здоровье кластера")
            
            # Проверка использования памяти с защитой от отсутствующих ключей
            heap_used_bytes = 0
            heap_max_bytes = 1
            
            try:
                jvm_mem = cluster_stats.get('nodes', {}).get('jvm', {}).get('mem', {})
                heap_used_bytes = jvm_mem.get('heap_used_in_bytes', 0)
                heap_max_bytes = jvm_mem.get('heap_max_in_bytes', 1)
            except (KeyError, TypeError, AttributeError) as mem_error:
                logger.warning(f"Could not retrieve memory stats: {mem_error}")
                heap_used_bytes = 0
                heap_max_bytes = 1
            
            # Защита от деления на ноль и None значений
            if (heap_max_bytes is not None and heap_used_bytes is not None and 
                heap_max_bytes > 0 and isinstance(heap_max_bytes, (int, float)) and 
                isinstance(heap_used_bytes, (int, float))):
                heap_used_percent = (heap_used_bytes / heap_max_bytes) * 100
            else:
                heap_used_percent = 0.0
            
            if (heap_used_percent is not None and
                isinstance(heap_used_percent, (int, float)) and
                not isinstance(heap_used_percent, type(None)) and
                heap_used_percent > 80):
                recommendations.append(f"Высокое использование heap памяти ({heap_used_percent:.1f}%) - рассмотрите увеличение размера heap")
            
            return {
                "cluster_status": health.get('status', 'unknown'),
                "active_shards": health.get('active_shards', 0),
                "nodes_count": health.get('number_of_nodes', 0),
                "heap_used_percent": round(heap_used_percent, 1) if heap_used_percent is not None else 0,
                "pending_tasks": pending_tasks,
                "recommendations": recommendations,
                "connection_healthy": True
            }
            
        except TypeError as te:
            # Специальная обработка для ошибок типов
            logger.error(f"Type error in health check: {te}")
            return {
                "connection_healthy": False,
                "error": f"Ошибка типов данных: {str(te)}",
                "recommendations": ["Проверьте совместимость версии Elasticsearch", "Обновите клиент Elasticsearch"]
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "connection_healthy": False,
                "error": f"Ошибка проверки здоровья: {str(e)}",
                "recommendations": ["Проверьте подключение к Elasticsearch и статус кластера"]
            }
    
    # ОПТИМИЗАЦИЯ 29: Система кеширования запросов для повышения производительности поиска
    def _get_cache_key(self, query: str, index: str, size: int = 10) -> str:
        """Генерация ключа кеша для запроса"""
        query_data = f"{index}:{query}:{size}"
        return hashlib.md5(query_data.encode()).hexdigest()
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Проверка актуальности кеша"""
        return (time.time() - timestamp) < self._cache_ttl
    
    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Получение результата из кеша"""
        with self._cache_lock:
            if cache_key in self._query_cache:
                result, timestamp = self._query_cache[cache_key]
                if self._is_cache_valid(timestamp):
                    self._cache_hits += 1
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return result
                else:
                    # Удаляем устаревший результат
                    del self._query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: List[Dict[str, Any]]):
        """Сохранение результата в кеш"""
        with self._cache_lock:
            # Ограничиваем размер кеша
            if len(self._query_cache) > 1000:
                # Удаляем самые старые записи (простая LRU реализация)
                oldest_keys = sorted(self._query_cache.keys(), 
                                   key=lambda k: self._query_cache[k][1])[:100]
                for key in oldest_keys:
                    del self._query_cache[key]
            
            self._query_cache[cache_key] = (result, time.time())
            logger.debug(f"Cached result for key: {cache_key}")
    
    def clear_cache(self):
        """Очистка кеша запросов"""
        with self._cache_lock:
            self._query_cache.clear()
            logger.info("Query cache cleared")
    
    # ОПТИМИЗАЦИЯ 30: Расширенный мониторинг производительности поиска
    def _record_search_performance(self, operation: str, duration: float, result_count: int = 0):
        """Записываем метрики производительности поиска"""
        self._performance_metrics[operation].append({
            'duration': duration,
            'result_count': result_count,
            'timestamp': time.time()
        })
        
        # Ограничиваем количество записей метрик
        if len(self._performance_metrics[operation]) > 1000:
            self._performance_metrics[operation] = self._performance_metrics[operation][-500:]
    
    def get_search_performance_report(self) -> Dict[str, Any]:
        """Получение подробного отчета о производительности поиска"""
        report = {
            'total_queries': self._total_queries,
            'cache_hits': self._cache_hits,
            'cache_hit_ratio': (self._cache_hits / max(self._total_queries, 1)) * 100,
            'cache_size': len(self._query_cache),
            'operations': {}
        }
        
        for operation, metrics in self._performance_metrics.items():
            if metrics:
                durations = [m['duration'] for m in metrics]
                result_counts = [m['result_count'] for m in metrics]
                
                report['operations'][operation] = {
                    'total_calls': len(metrics),
                    'avg_duration_ms': round(sum(durations) / len(durations) * 1000, 2) if durations and len(durations) > 0 else 0,
                    'min_duration_ms': round(min(durations) * 1000, 2) if durations else 0,
                    'max_duration_ms': round(max(durations) * 1000, 2) if durations else 0,
                    'avg_results': round(sum(result_counts) / len(result_counts), 1) if result_counts and len(result_counts) > 0 else 0,
                    'total_results': sum(result_counts)
                }
        
        return report
    
    # ОПТИМИЗАЦИЯ 31: Улучшенные методы поиска с кешированием
    def search_materials_cached(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """Поиск материалов с кешированием результатов"""
        start_time = time.time()
        self._total_queries += 1
        
        cache_key = self._get_cache_key(query, self.materials_index, size)
        
        # Проверяем кеш
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            self._record_search_performance('search_materials_cached', time.time() - start_time, len(cached_result))
            return cached_result
        
        # Выполняем поиск
        try:
            result = self.search_materials(query, size)
            self._cache_result(cache_key, result)
            self._record_search_performance('search_materials_cached', time.time() - start_time, len(result))
            return result
        except Exception as e:
            logger.error(f"Failed to search materials with caching: {e}")
            return []
    
    def search_price_list_cached(self, query: str, size: int = 50) -> List[Dict[str, Any]]:
        """Поиск в прайс-листе с кешированием результатов"""
        start_time = time.time()
        self._total_queries += 1
        
        cache_key = self._get_cache_key(query, self.price_list_index, size)
        
        # Проверяем кеш
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            self._record_search_performance('search_price_list_cached', time.time() - start_time, len(cached_result))
            return cached_result
        
        # Выполняем поиск
        try:
            result = self.search_price_list(query, size)
            self._cache_result(cache_key, result)
            self._record_search_performance('search_price_list_cached', time.time() - start_time, len(result))
            return result
        except Exception as e:
            logger.error(f"Failed to search price list with caching: {e}")
            return []
    
    # ОПТИМИЗАЦИЯ 32: Пакетная оптимизация индексов после массовых операций
    def optimize_for_production(self):
        """Полная оптимизация для продакшена"""
        try:
            logger.info("Starting production optimization...")
            
            # 1. Force merge индексов
            self.optimize_indices_for_search()
            
            # 2. Настройка оптимальных параметров для поиска
            optimization_settings = {
                "index.refresh_interval": "30s",
                "index.max_result_window": 50000,
                # Отключаем swapping для production
                "index.store.preload": ["nvd", "dvd"],
                # Настройки для более быстрого поиска
                "index.search.slowlog.threshold.query.warn": "10s",
                "index.search.slowlog.threshold.query.info": "5s",
                "index.search.slowlog.threshold.query.debug": "2s",
                "index.search.slowlog.threshold.fetch.warn": "1s",
            }
            
            for index_name in [self.materials_index, self.price_list_index]:
                if self.es.indices.exists(index=index_name):
                    self.es.indices.put_settings(
                        index=index_name,
                        settings=optimization_settings
                    )
                    logger.info(f"Applied production settings to {index_name}")
            
            # 3. Очищаем кеши для свежего старта
            self.es.indices.clear_cache(index=[self.materials_index, self.price_list_index])
            
            # 4. Warming up - выполняем базовые запросы для прогрева кешей
            self._warmup_indices()
            
            logger.info("Production optimization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize for production: {e}")
            return False
    
    def _warmup_indices(self):
        """Прогрев индексов базовыми запросами"""
        try:
            warmup_queries = ["кабель", "лампа", "автомат", "выключатель", "провод"]
            
            for query in warmup_queries:
                self.search_materials(query, 5)
                self.search_price_list(query, 5)
                
            logger.info("Index warmup completed")
        except Exception as e:
            logger.warning(f"Index warmup failed: {e}")
    
    # ОПТИМИЗАЦИЯ 33: Метод для экспорта полной статистики производительности
    def export_performance_stats(self, filepath: str = None) -> Dict[str, Any]:
        """Экспорт всей статистики производительности"""
        try:
            full_stats = {
                'elasticsearch_connection': {
                    'host': self.host,
                    'port': self.port,
                    'bulk_size': self.bulk_size,
                    'max_workers': self.max_workers
                },
                'indexing_performance': self.get_performance_stats(),
                'search_performance': self.get_search_performance_report(),
                'index_statistics': self.get_index_stats(),
                'cluster_health': self.health_check(),
                'timestamp': datetime.now().isoformat(),
                'cache_stats': {
                    'cache_size': len(self._query_cache),
                    'cache_ttl_seconds': self._cache_ttl,
                    'total_queries': self._total_queries,
                    'cache_hits': self._cache_hits,
                    'cache_hit_ratio_percent': round((self._cache_hits / max(self._total_queries, 1)) * 100, 2)
                }
            }
            
            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(full_stats, f, indent=2, ensure_ascii=False)
                logger.info(f"Performance stats exported to {filepath}")
            
            return full_stats
            
        except Exception as e:
            logger.error(f"Failed to export performance stats: {e}")
            return {}