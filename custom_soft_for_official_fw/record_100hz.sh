#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Створення віртуального середовища Python..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

mkdir -p recordings
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUT_FILE="recordings/highspeed_100hz_${TIMESTAMP}.sqlite"

echo "======================================================"
echo "⚡ WITRN K2 - Швидкісний запис (100 Гц)"
echo "======================================================"
echo "Параметри:"
echo " - Вихідний файл:  ${OUT_FILE}"
echo " - Частота:        100 Гц (100 вимірювань/сек)"
echo " - Натисніть Ctrl+C для завершення запису"
echo "======================================================"
echo ""

exec .venv/bin/python -m witrn_k2.cli record \
    -o "$OUT_FILE" \
    -r 100 \
    --format sqlite \
    "$@"
