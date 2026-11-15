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
OUT_FILE="recordings/charge_${TIMESTAMP}.sqlite"

echo "======================================================"
echo "🔋 WITRN K2 - Тест заряджання з автозупинкою"
echo "======================================================"
echo "Параметри:"
echo " - Вихідний файл:   ${OUT_FILE}"
echo " - Умова зупинки:   струм < 0.05A (50 мА) протягом 10 сек"
echo " - Частота запису:  10 Гц"
echo " - Автоекспорт:     офіційний WITRN CSV"
echo "======================================================"
echo ""

exec .venv/bin/python -m witrn_k2.cli record \
    -o "$OUT_FILE" \
    -r 10 \
    --format witrn_csv \
    --auto-stop \
    --auto-kind current \
    --threshold 0.05 \
    --trigger-duration 10.0 \
    "$@"
