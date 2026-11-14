#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Помилка: Віртуальне середовище .venv не знайдено в $SCRIPT_DIR!"
    exit 1
fi

echo "=== Перевірка підключення WITRN K2 (DFU) ==="
if ! lsusb | grep -q "0716:5060"; then
    echo "УВАГА: Пристрій WITRN K2 (0716:5060) не виявлено серед USB-пристроїв!"
    echo "Інструкція:"
    echo "  1. Відключіть тестер."
    echo "  2. Затисніть кнопку '-' (DFU)."
    echo "  3. Підключіть кабель до порту CC1."
    echo "  4. Коли з'явиться напис 'DFU', відпустіть кнопку та повторіть спробу."
    exit 1
fi

"$PYTHON" "$SCRIPT_DIR/tools/k2_updater.py" probe --dfu
