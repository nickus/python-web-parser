# Система поиска материалов с процентом похожести

Полнофункциональная программа для поиска и сопоставления материалов с прайс-листами с использованием Elasticsearch и расчетом процента похожести.

## Возможности

- **Загрузка материалов** из различных форматов (CSV, Excel, JSON)
- **Загрузка прайс-листов** из различных форматов 
- **Полнотекстовый поиск** с использованием Elasticsearch
- **Расчет процента похожести** на основе множественных критериев:
  - Название материала
  - Описание
  - Категория
  - Бренд
  - Технические характеристики
- **Пакетная обработка** с многопоточностью
- **Экспорт результатов** в JSON и CSV форматы
- **Статистика и отчетность**

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd PythonProject
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Убедитесь, что у вас запущен Elasticsearch:
```bash
# Для локальной установки
docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch:8.15.1
```

## Использование

### Командная строка

```bash
# Создание индексов
python main.py --setup

# Загрузка материалов и прайс-листа, запуск сопоставления
python main.py --materials data/materials.csv --price-list data/price_list.csv --output results.json

# С настройкой порога похожести
python main.py --materials data/materials.csv --price-list data/price_list.csv --threshold 30 --output results.json

# Экспорт в CSV
python main.py --materials data/materials.csv --price-list data/price_list.csv --format csv --output results.csv
```

### Программный интерфейс

```python
from src.material_matcher_app import MaterialMatcherApp

# Инициализация приложения
app = MaterialMatcherApp()

# Создание индексов
app.setup_indices()

# Загрузка данных
materials = app.load_materials('data/materials.csv')
price_items = app.load_price_list('data/price_list.csv')

# Индексация
app.index_data(materials, price_items)

# Запуск сопоставления
results = app.run_matching()

# Экспорт результатов
app.export_results(results, 'results.json')
```

## Форматы файлов

### Материалы (materials.csv)
```csv
id,name,description,category,brand,model,unit,specifications
1,"Кабель ВВГНГ","Силовой кабель","Кабели","Рыбинсккабель","ВВГНГ-LS 3x2.5","м","{\"voltage\": \"0.66кВ\", \"cores\": 3}"
2,"Автомат защиты","Автоматический выключатель","Автоматика","ABB","S201 C16","шт","{\"current\": \"16А\", \"poles\": 1}"
```

### Прайс-лист (price_list.csv)
```csv
id,material_name,description,price,currency,supplier,category,brand,unit,specifications
1,"Кабель силовой ВВГНГ-LS","Кабель для внутренней проводки",150.50,"RUB","Электротехника ООО","Кабели","Рыбинсккабель","м","{\"voltage\": \"660В\", \"cores\": 3}"
2,"Выключатель автоматический S201","Однополюсный автомат",890.00,"RUB","Электро-Торг","Автоматика","ABB","шт","{\"current\": \"16А\"}"
```

## Конфигурация

Создайте файл `config.json`:

```json
{
  "elasticsearch": {
    "host": "localhost",
    "port": 9200,
    "username": null,
    "password": null
  },
  "matching": {
    "similarity_threshold": 20.0,
    "max_results_per_material": 10,
    "max_workers": 4
  }
}
```

## Алгоритм расчета похожести

Система использует многокритериальный подход для расчета процента похожести:

1. **Название** (вес 40%): Сравнение названий материалов
2. **Описание** (вес 20%): Анализ описаний
3. **Категория** (вес 15%): Сопоставление категорий
4. **Бренд** (вес 15%): Сравнение производителей
5. **Характеристики** (вес 10%): Анализ технических параметров

Для каждого критерия используются:
- Нечеткое сравнение строк (fuzzywuzzy)
- Токенизация и нормализация
- Частичное совпадение
- Семантический анализ

## Структура результатов

```json
{
  "material": {
    "id": "1",
    "name": "Кабель ВВГНГ",
    "category": "Кабели"
  },
  "price_item": {
    "id": "1",
    "material_name": "Кабель силовой ВВГНГ-LS",
    "price": 150.50,
    "supplier": "Электротехника ООО"
  },
  "similarity_percentage": 87.5,
  "similarity_details": {
    "name": 85.0,
    "description": 90.0,
    "category": 100.0,
    "brand": 95.0,
    "specifications": 80.0
  },
  "elasticsearch_score": 2.453
}
```

## Архитектура

- `models/` - Модели данных (Material, PriceListItem, SearchResult)
- `services/` - Бизнес-логика:
  - `elasticsearch_service.py` - Работа с Elasticsearch
  - `similarity_service.py` - Расчет похожести
  - `matching_service.py` - Сопоставление материалов
- `utils/` - Утилиты загрузки и экспорта данных
- `material_matcher_app.py` - Главное приложение

## Требования

- Python 3.8+
- Elasticsearch 8.x
- Зависимости из requirements.txt

## Производительность

- Многопоточная обработка для больших объемов данных
- Оптимизированные индексы Elasticsearch
- Кеширование результатов поиска
- Пакетная индексация