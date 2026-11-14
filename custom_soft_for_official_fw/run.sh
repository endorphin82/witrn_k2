#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================"
echo "⚡ WITRN K2 - Лабораторне ПЗ для аналізу даних"
echo "======================================================"

# Check or create virtual environment
if [ ! -d ".venv" ]; then
    echo "Створення віртуального середовища Python..."
    python3 -m venv .venv
    echo "Встановлення залежностей..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

# Run device check
echo "Перевірка підключення WITRN K2..."
.venv/bin/python -m witrn_k2.cli info || {
    echo "⚠️ Попередження: пристрій не готовий або відсутні права."
    echo "   Ви зможете скористатися режимом симулятора або надати права через sudo ./setup_udev.sh"
}

echo ""
echo "🚀 Запуск веб-сервера аналізатора на http://127.0.0.1:8000"
echo "   Натисніть Ctrl+C для зупинки."
echo ""

exec .venv/bin/python -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser
