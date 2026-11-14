#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Помилка: Віртуальне середовище .venv не знайдено в $SCRIPT_DIR!"
    exit 1
fi

echo "=== Створення резервної копії пам'яті WITRN K2 ==="
if ! lsusb | grep -q "0716:5060"; then
    echo "УВАГА: Пристрій WITRN K2 (0716:5060) не знайдено!"
    echo "Переведіть тестер у режим DFU (затиснути кнопку '-' при підключенні до порту CC1)."
    exit 1
fi

echo "Зчитування дампа пам'яті у два незалежних проходи (це займе близько 40 секунд)..."
"$PYTHON" "$SCRIPT_DIR/tools/k2_updater.py" backup --dfu

echo ""
echo "Бекап успішно завершено! Файли збережено у директорії $SCRIPT_DIR/k2_backups/"
