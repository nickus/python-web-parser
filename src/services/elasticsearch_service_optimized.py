"""
Оптимизированный сервис Elasticsearch с улучшенными поисковыми запросами
"""

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk
from typing import List, Dict, Any, Optional
import logging
import time
from datetime import datetime

from ..models.material import Material, PriceListItem

logger = logging.getLogger(__name__)


class OptimizedElasticsearchService:
    """Оптимизированный сервис для работы с Elasticsearch"""

    def __init__(self, host: str = 'localhost', port: int = 9200,
                 username: str = None, password: str = None,
                 bulk_size: int = 1000, max_workers: int = 4):
        """Инициализация подключения к Elasticsearch"""
        self.host = host
        self.port = port
        self.bulk_size = bulk_size
        self.max_workers = max_workers

        # Конфигурация подключения
        connection_config = {
            "request_timeout": 30,
            "max_retries": 3,
            "retry_on_timeout": True,
            "retry_on_status": [429, 502, 503, 504],
            "verify_certs": False,
            "sniff_on_start": False,
            "sniff_on_connection_fail": False,
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
        self.materials_index = 'materials_optimized'
        self.price_list_index = 'price_list'

        logger.info(f"Initialized OptimizedElasticsearchService to {host}:{port}")

    def recreate_price_list_index(self) -> bool:
        """
        Принудительное пересоздание индекса (удаляет существующий)
        Используется только при явном запросе пользователя (--setup)
        """
        try:
            if self.es.indices.exists(index=self.price_list_index):
                self.es.indices.delete(index=self.price_list_index)
                logger.info(f"Deleted existing index: {self.price_list_index}")
            return self.create_optimized_price_list_index()
        except Exception as e:
            logger.error(f"Failed to recreate index: {e}")
            return False

    def create_optimized_price_list_index(self) -> bool:
        """
        Создание оптимизированного индекса для прайс-листа

        Ключевые улучшения:
        1. Добавлены поля для нормализованного текста
        2. Настроен русский анализатор
        3. Добавлены edge_ngram для префиксного поиска
        4. Оптимизированы настройки для поиска
        """
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},

                    # Основное поле для поиска с несколькими анализаторами
                    "name": {
                        "type": "text",
                        "analyzer": "russian_optimized",
                        "fields": {
                            # Для точного поиска
                            "exact": {
                                "type": "text",
                                "analyzer": "keyword_lowercase"
                            },
                            # Для префиксного поиска
                            "prefix": {
                                "type": "text",
                                "analyzer": "edge_ngram_analyzer",
                                "search_analyzer": "standard"
                            },
                            # Для поиска по частям слов
                            "ngram": {
                                "type": "text",
                                "analyzer": "ngram_analyzer",
                                "search_analyzer": "standard"
                            },
                            # Исходное значение
                            "raw": {
                                "type": "keyword"
                            }
                        }
                    },

                    # Нормализованное название для быстрого сравнения
                    "name_normalized": {
                        "type": "text",
                        "analyzer": "normalization_analyzer"
                    },

                    "brand": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "russian_optimized"}
                        }
                    },

                    "article": {
                        "type": "keyword",
                        "fields": {
                            "text": {"type": "text", "analyzer": "standard"}
                        }
                    },

                    "class_code": {"type": "keyword"},
                    "price": {"type": "float"},

                    # Комбинированное поле для полнотекстового поиска
                    "search_text": {
                        "type": "text",
                        "analyzer": "russian_optimized"
                    },

                    # Предрассчитанные embedding/features для ML (будущее)
                    "features": {
                        "type": "dense_vector",
                        "dims": 128,
                        "index": False  # Пока не используем для поиска
                    },

                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "1s",

                # Анализаторы
                "analysis": {
                    "analyzer": {
                        # Основной русский анализатор
                        "russian_optimized": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "russian_stop",
                                "russian_stemmer"
                            ]
                        },

                        # Для нормализации (убирает спецсимволы, приводит к единому виду)
                        "normalization_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "asciifolding",
                                "trim"
                            ],
                            "char_filter": ["special_chars_filter"]
                        },

                        # Для префиксного поиска
                        "edge_ngram_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "edge_ngram_filter"
                            ]
                        },

                        # Для поиска по частям слов
                        "ngram_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "ngram_filter"
                            ]
                        },

                        # Для точного поиска с lowercase
                        "keyword_lowercase": {
                            "type": "custom",
                            "tokenizer": "keyword",
                            "filter": ["lowercase"]
                        }
                    },
                    "filter": {
                        "russian_stop": {
                            "type": "stop",
                            "stopwords": "_russian_"
                        },
                        "russian_stemmer": {
                            "type": "stemmer",
                            "language": "russian"
                        },
                        "edge_ngram_filter": {
                            "type": "edge_ngram",
                            "min_gram": 2,
                            "max_gram": 15
                        },
                        "ngram_filter": {
                            "type": "ngram",
                            "min_gram": 3,
                            "max_gram": 4
                        }
                    },
                    "char_filter": {
                        "special_chars_filter": {
                            "type": "pattern_replace",
                            "pattern": "[^a-zA-Zа-яА-Я0-9\\s]",
                            "replacement": " "
                        }
                    }
                }
            }
        }

        try:
            # Проверяем существует ли индекс
            if self.es.indices.exists(index=self.price_list_index):
                logger.info(f"Index already exists: {self.price_list_index}")
                return True

            # Создаем новый индекс только если его нет
            self.es.indices.create(index=self.price_list_index, body=mapping)
            logger.info(f"Created optimized index: {self.price_list_index}")
            return True

        except Exception as e:
            logger.error(f"Failed to create price list index: {e}")
            return False

    def index_price_list_optimized(self, price_items: List[PriceListItem]) -> bool:
        """
        Оптимизированная индексация прайс-листа

        Добавляет:
        - Нормализованные поля для быстрого поиска
        - Комбинированное поле search_text
        - Предварительную обработку данных
        """
        if not price_items:
            logger.warning("No price items to index")
            return True

        start_time = time.time()

        try:
            # Подготовка документов для индексации
            actions = []
            for item in price_items:
                # Базовый документ
                doc = item.to_dict()

                # Добавляем нормализованное название
                doc['name_normalized'] = self._normalize_text(item.name or '')

                # Создаем комбинированное поле для поиска
                search_parts = [
                    item.name or '',
                    item.brand or '',
                    item.article or '',
                    item.class_code or '',
                    item.description or ''
                ]
                doc['search_text'] = ' '.join(filter(None, search_parts))

                # Добавляем временные метки
                doc['created_at'] = datetime.now()
                doc['updated_at'] = datetime.now()

                # Placeholder для будущих ML features
                doc['features'] = [0.0] * 128

                action = {
                    "_index": self.price_list_index,
                    "_id": item.id,
                    "_source": doc
                }
                actions.append(action)

            # Bulk индексация
            success_count = 0
            error_count = 0

            for success, info in parallel_bulk(
                self.es,
                actions,
                chunk_size=self.bulk_size,
                thread_count=self.max_workers,
                request_timeout=60
            ):
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    logger.warning(f"Failed to index item: {info}")

            # Обновляем индекс
            self.es.indices.refresh(index=self.price_list_index)

            elapsed_time = time.time() - start_time
            logger.info(
                f"Indexed {success_count} price items in {elapsed_time:.2f}s "
                f"({success_count/elapsed_time:.1f} docs/sec)"
            )

            return error_count == 0

        except Exception as e:
            logger.error(f"Error indexing price list: {e}")
            return False

    def search_price_list_optimized(self,
                                    query: str,
                                    size: int = 20,
                                    min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Оптимизированный поиск в прайс-листе

        Использует:
        - Multi-match запросы с разными весами
        - Fuzzy matching для опечаток
        - Phrase matching для точности
        - Boosting для важных полей
        """
        search_query = {
            "query": {
                "bool": {
                    "should": [
                        # 1. Точное совпадение фразы (высший приоритет)
                        {
                            "match_phrase": {
                                "name": {
                                    "query": query,
                                    "boost": 5.0
                                }
                            }
                        },

                        # 2. Точное совпадение в exact поле
                        {
                            "match": {
                                "name.exact": {
                                    "query": query,
                                    "boost": 4.0
                                }
                            }
                        },

                        # 3. Multi-match по основным полям с fuzzy
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "name^3",
                                    "name.prefix^2",
                                    "search_text",
                                    "brand^1.5",
                                    "article^1.5"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "prefix_length": 2,
                                "boost": 2.0
                            }
                        },

                        # 4. N-gram поиск для частичных совпадений
                        {
                            "match": {
                                "name.ngram": {
                                    "query": query,
                                    "boost": 1.0
                                }
                            }
                        },

                        # 5. Полнотекстовый поиск как fallback
                        {
                            "match": {
                                "search_text": {
                                    "query": query,
                                    "fuzziness": "AUTO",
                                    "boost": 0.5
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "min_score": min_score,

            # Возвращаем только нужные поля для экономии
            "_source": [
                "id", "name", "brand", "article", "class_code",
                "price", "description", "material_name"
            ],

            # Добавляем highlighting для отладки
            "highlight": {
                "fields": {
                    "name": {},
                    "search_text": {}
                }
            }
        }

        try:
            response = self.es.search(index=self.price_list_index, body=search_query)
            hits = response['hits']['hits']

            # Логируем для отладки
            if hits:
                logger.debug(f"Search '{query}' returned {len(hits)} results, top score: {hits[0]['_score']}")

            return hits

        except Exception as e:
            logger.error(f"Error searching price list: {e}")
            return []

    def _normalize_text(self, text: str) -> str:
        """Базовая нормализация текста"""
        import re

        if not text:
            return ""

        # Приводим к нижнему регистру
        text = text.lower()

        # Заменяем спецсимволы на пробелы
        text = re.sub(r'[^\w\s]', ' ', text)

        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def check_connection(self) -> bool:
        """Проверка подключения к Elasticsearch"""
        try:
            return self.es.ping()
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False