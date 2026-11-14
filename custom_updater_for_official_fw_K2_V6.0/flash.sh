#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Помилка: Віртуальне середовище .venv не знайдено в $SCRIPT_DIR!"
    exit 1
fi

FIRMWARE="${1:-$SCRIPT_DIR/K2_APP_6.0.k2}"

if [ ! -f "$FIRMWARE" ]; then
    echo "Помилка: Файл прошивки '$FIRMWARE' не знайдено!"
    echo "Використання: $0 [шлях_до_файлу.k2]"
    exit 1
fi

echo "=== Перевірка файлу прошивки ==="
"$PYTHON" "$SCRIPT_DIR/tools/k2_updater.py" inspect "$FIRMWARE"

echo ""
echo "=== Перевірка підключення WITRN K2 ==="
if ! lsusb | grep -q "0716:5060"; then
    echo "УВАГА: Пристрій WITRN K2 (0716:5060) не знайдено!"
    echo "Переконайтеся, що тестер переведено в режим DFU:"
    echo "  - Відключіть тестер"
    echo "  - Затисніть кнопку '-' (DFU)"
    echo "  - Підключіть кабель до порту CC1"
    echo "  - Після появи екрану 'DFU' відпустіть кнопку"
    exit 1
fi

echo ""
read -p "Розпочати процес прошивки $FIRMWARE? (y/N): " -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[yYіІдД] ]]; then
    echo "Прошивку скасовано."
    exit 0
fi

echo ""
echo "=== Прошивка тестера (Стирання -> Запис -> Верифікація) ==="
"$PYTHON" "$SCRIPT_DIR/tools/k2_updater.py" flash "$FIRMWARE" --dfu --yes

echo ""
echo "=== УСПІШНО ЗАВЕРШЕНО! Тестер перезавантажується в робочий режим. ==="
