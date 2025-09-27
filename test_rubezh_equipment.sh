#!/bin/bash
# Тестовые команды для проверки точного сопоставления слаботочного оборудования Рубеж

echo "======================================================================"
echo "ТЕСТИРОВАНИЕ ТОЧНОГО СОПОСТАВЛЕНИЯ ОБОРУДОВАНИЯ РУБЕЖ"
echo "======================================================================"

echo -e "\n1. Рубеж-2ОП прот.R3 (ожидается ID: 3109396)"
venv/bin/python main.py --search-material "Прибор приемно-контрольный RS-485" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n2. ИВЭПР 24/2,5 RS-R3 (ожидается ID: 5028231)"
venv/bin/python main.py --search-material "Источник вторичного электропитания резервированный ИВЭПР" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n3. DTM 1217 (ожидается ID: 8057037)"
venv/bin/python main.py --search-material "Аккумулятор DTM 12В 17Ач" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n4. R3-Рубеж-ПДУ-ПТ (ожидается ID: 4620055)"
venv/bin/python main.py --search-material "Пульт дистанционного управления пожаротушения Рубеж-ПДУ-ПТ" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n5. FireSec-Pro R3 (ожидается ID: 3104572)"
venv/bin/python main.py --search-material "Инженерный пакет FireSec" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n6. R3-МС-Е (ожидается ID: 6229094)"
venv/bin/python main.py --search-material "Модуль сопряжения R3-Link" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n7. ШУН/В-18-03-R3 (ожидается ID: 3287967)"
venv/bin/python main.py --search-material "Шкаф управления пожарный адресный мощность 18 кВт" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n8. ШУН/В-11-03-R3 (ожидается ID: 1617295)"
venv/bin/python main.py --search-material "Шкаф управления пожарный адресный мощность 11 кВт" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n9. ШУН/В-7,5-03-R3 (ожидается ID: 253569)"
venv/bin/python main.py --search-material "Шкаф управления пожарный адресный мощность 7.5 кВт" --top-n 3 2>/dev/null | grep -E "^1\.|ID:" | head -2

echo -e "\n======================================================================"
echo "ПРОВЕРКА РЕЗУЛЬТАТОВ"
echo "======================================================================"

# Подсчет правильных ID
echo -e "\nПроверяем наличие правильных ID в результатах:"
for id in 3109396 5028231 8057037 4620055 3104572 6229094 3287967 1617295 253569; do
    echo -n "ID $id: "
    if venv/bin/python main.py --search-material "$(venv/bin/python -c "
import json
with open('catalog.json', 'r') as f:
    catalog = json.load(f)
item = next((x for x in catalog if str(x.get('id')) == '$id'), None)
if item:
    print(item.get('name', ''))
")" --top-n 5 2>/dev/null | grep -q "ID: $id"; then
        echo "✅ Найден"
    else
        echo "❌ Не найден"
    fi
done