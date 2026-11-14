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
    exit 1
fi

"$PYTHON" "$SCRIPT_DIR/tools/k2_updater.py" inspect "$FIRMWARE"
