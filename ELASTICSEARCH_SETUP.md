# 🐳 Настройка Elasticsearch в Docker Desktop

## ✅ Успешная установка (текущий статус)

Elasticsearch успешно запущен и работает на `localhost:9200`!

## 📋 Пошаговая инструкция

### 1. Подготовка
- ✅ Docker Desktop установлен и запущен
- ✅ Порты 9200 и 9300 свободны

### 2. Запуск Elasticsearch

#### Вариант A: Быстрый запуск (одна команда)
```bash
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "xpack.security.enrollment.enabled=false" \
  elasticsearch:8.15.1
```

#### Вариант B: Docker Compose (рекомендуется)
```bash
# В папке проекта
docker-compose up -d
```

### 3. Проверка работы
```bash
# Проверка статуса контейнера
docker ps

# Проверка HTTP API
curl http://localhost:9200

# Проверка из приложения
python main.py --check-connection
```

## 🔧 Управление контейнером

### Полезные команды Docker:
```bash
# Просмотр статуса
docker ps

# Просмотр логов
docker logs elasticsearch

# Остановка
docker stop elasticsearch

# Запуск остановленного контейнера
docker start elasticsearch

# Удаление контейнера
docker rm elasticsearch

# Удаление с данными
docker rm -f elasticsearch
```

### Команды Docker Compose:
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Просмотр логов
docker-compose logs -f elasticsearch

# Перезапуск
docker-compose restart elasticsearch
```

## 🚨 Устранение неполадок

### Проблема: Порт 9200 уже занят
```bash
# Найти процесс использующий порт
netstat -ano | findstr :9200

# Остановить конфликтующий контейнер
docker stop $(docker ps -q --filter "publish=9200")
```

### Проблема: Контейнер не запускается (нехватка памяти)
Добавьте ограничения памяти:
```bash
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  elasticsearch:8.15.1
```

### Проблема: "Connection refused"
1. Проверьте что контейнер запущен: `docker ps`
2. Проверьте логи: `docker logs elasticsearch`
3. Подождите 30-60 секунд после запуска
4. Проверьте firewall и антивирус

### Проблема: "Docker not found"
1. Убедитесь что Docker Desktop запущен
2. Перезапустите Docker Desktop
3. Откройте терминал от имени администратора

### Проблема: Медленная работа
1. Увеличьте выделенную Docker память (Settings → Resources → Memory)
2. Используйте ограничения Java heap: `-e "ES_JAVA_OPTS=-Xms512m -Xmx1g"`

## 🔍 Проверка работы приложения

После запуска Elasticsearch:

1. **Запустите GUI:**
   ```bash
   python main.py --gui
   ```

2. **Или CLI проверку:**
   ```bash
   python main.py --check-connection
   ```

3. **Или интерактивную настройку:**
   ```bash
   python main.py --init
   ```

## 📊 Дополнительные возможности

### Kibana (веб-интерфейс для Elasticsearch)
Если используете Docker Compose:
```bash
# Запуск с Kibana
docker-compose --profile with-kibana up -d

# Kibana будет доступен по адресу: http://localhost:5601
```

### Мониторинг здоровья кластера
```bash
# Проверка состояния кластера
curl http://localhost:9200/_cluster/health

# Просмотр индексов
curl http://localhost:9200/_cat/indices?v

# Статистика
curl http://localhost:9200/_stats
```

## 💡 Рекомендации

1. **Для разработки:** Используйте быстрый запуск
2. **Для постоянной работы:** Используйте Docker Compose
3. **Для слабых машин:** Добавляйте ограничения памяти
4. **Для production:** Настройте security и persistent storage

## 🔄 Автозапуск

Чтобы Elasticsearch запускался автоматически с Docker Desktop:
```bash
# При создании контейнера добавьте флаг
docker run -d --restart unless-stopped --name elasticsearch ...

# Или для существующего контейнера
docker update --restart unless-stopped elasticsearch
```

---

**✅ Текущий статус:** Elasticsearch запущен и готов к работе!  
**🔗 URL:** http://localhost:9200  
**🐳 Контейнер:** `elasticsearch`  
**📱 Тест:** `python main.py --check-connection`