# E2E Тестовые команды для main.py

## 1. Базовые команды

### Проверка подключения
```bash
python main.py --check-connection
```

### Создание/пересоздание индексов (осторожно - удаляет данные!)
```bash
python main.py --setup
```

### Загрузка прайс-листа без удаления существующих данных
```bash
python main.py --price-list catalog.json
```

## 2. Тесты поиска кабелей

### Точный поиск конкретного кабеля (ID: 9994067)
```bash
python main.py --search-material "Кабель силовой ППГнг(А)-FRHF 1х70мк(PE)-1 ТРТС Кабэкс" --top-n 5
```
✅ Должен найти: ID 9994067, Бренд: Кабэкс

### Упрощенный поиск кабеля 1х70
```bash
python main.py --search-material "ППГнг(А)-FRHF 1х70" --top-n 5
```
✅ Должен найти кабели 1х70
❌ НЕ должен найти кабели 1х95

### Поиск кабеля с опечаткой
```bash
python main.py --search-material "Кабель ППГнг FRHF 1x70" --top-n 3
```
✅ Должен найти несмотря на опечатку (1x70 вместо 1х70)

### Проверка, что НЕ находит неправильный размер
```bash
python main.py --search-material "ППГнг(А)-FRHF 1х70" --top-n 10 | grep "1х95"
```
❌ НЕ должно быть результатов с 1х95

## 3. Тесты слаботочного оборудования

### Поиск RS-485
```bash
python main.py --search-material "RS-485" --top-n 3
```

### Поиск аккумуляторов DTM
```bash
python main.py --search-material "Аккумулятор DTM 12В" --top-n 3
```

### Поиск оборудования Рубеж R3
```bash
python main.py --search-material "Блок индикации Рубеж-БИУ R3" --top-n 3
```

### Поиск FireSec
```bash
python main.py --search-material "FireSec" --top-n 3
```

## 4. Общие тесты поиска

### Поиск популярных товаров
```bash
python main.py --search-material "Кабель ВВГНГ" --top-n 5
python main.py --search-material "Автомат ABB" --top-n 5
python main.py --search-material "Розетка Legrand" --top-n 5
```

## 5. Проверка вывода

### Проверка наличия всех полей
```bash
python main.py --search-material "Кабель ВВГНГ" --top-n 1
```

Должны присутствовать поля:
- ID: [число]
- Артикул: (если есть)
- Бренд/Поставщик: [название]
- Цена: [число] RUB или "не указана"
- Похожесть: [процент]%
- Детали похожести

## 6. Производительность

### Тест скорости поиска
```bash
time python main.py --search-material "Кабель" --top-n 20
```
✅ Должен выполниться менее чем за 5 секунд

## 7. Полный процесс сопоставления

### Загрузка и сопоставление материалов с прайс-листом
```bash
# Подготовка тестовых данных
echo "id,name,equipment_code,manufacturer" > test_materials.csv
echo "1,\"Кабель силовой ППГнг(А)-FRHF 1х70\",\"ППГнг(А)-FRHF 1х70\",\"Кабельный завод\"" >> test_materials.csv

# Запуск сопоставления
python main.py --materials test_materials.csv --price-list catalog.json --output results.json --threshold 30 --format json
```

## 8. Автоматический запуск всех тестов

```bash
# Быстрый тест
python test_e2e_main.py

# Полный тест
python test_complete_system.py
python test_slabotochka.py
python test_real_cable.py
```

## Ожидаемые результаты

✅ **Успешно:**
- ID позиции отображается
- Бренд/поставщик отображается
- Процент схожести рассчитывается
- Кабели 1х70 не путаются с 1х95
- Слаботочное оборудование находится по моделям

⚠️ **Известные ограничения:**
- Цены могут отсутствовать (зависит от данных в catalog.json)
- Артикул может быть пустым (используется ID как основной идентификатор)
- Первый поиск после загрузки может быть медленнее