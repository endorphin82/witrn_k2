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

PYTHON=".venv/bin/python"

while true; do
    clear 2>/dev/null || true
    echo "=========================================================="
    echo "⚡ WITRN K2 USB Tester — Меню швидкого вибору"
    echo "=========================================================="
    echo " 1) 🌐 Веб-інтерфейс (Web Dashboard, 127.0.0.1:8000)"
    echo " 2) 🖥️  Графічний додаток (PyQt6 Desktop GUI)"
    echo " 3) 📊 Термінальний дашборд (Rich TUI)"
    echo " 4) 🎮 Термінальний дашборд у режимі СИМУЛЯТОРА"
    echo " 5) ⚡ Компактний однорядковий монітор (Live)"
    echo " 6) 🔋 Запис заряджання акумулятора (Автозупинка при <50мА)"
    echo " 7) 🚀 Швидкісний запис (100 Гц)"
    echo " 8) 🔍 Діагностика підключення тестера (info)"
    echo " 9) 📈 Аналіз останнього збереженого запису"
    echo " 0) ❌ Вихід"
    echo "=========================================================="
    read -rp "Оберіть дію [0-9]: " choice

    case "$choice" in
        1)
            echo "Запуск веб-сервера..."
            $PYTHON -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser
            ;;
        2)
            echo "Запуск GUI..."
            $PYTHON -m witrn_k2.cli gui
            ;;
        3)
            echo "Запуск TUI..."
            $PYTHON -m witrn_k2.cli dash
            ;;
        4)
            echo "Запуск TUI (Симулятор)..."
            $PYTHON -m witrn_k2.cli dash --simulator
            ;;
        5)
            echo "Запуск компактного монітора..."
            $PYTHON -m witrn_k2.cli live
            ;;
        6)
            ./record_charge.sh
            read -rp "Натисніть Enter для повернення в меню..." _
            ;;
        7)
            ./record_100hz.sh
            read -rp "Натисніть Enter для повернення в меню..." _
            ;;
        8)
            echo ""
            $PYTHON -m witrn_k2.cli info || true
            echo ""
            read -rp "Натисніть Enter для повернення в меню..." _
            ;;
        9)
            LAST_FILE=$(ls -t recordings/*.sqlite 2>/dev/null | head -n 1 || true)
            if [ -n "$LAST_FILE" ]; then
                $PYTHON -m witrn_k2.cli analyze "$LAST_FILE"
            else
                echo "У папці recordings/ ще немає файлів записів."
            fi
            read -rp "Натисніть Enter для повернення в меню..." _
            ;;
        0|q|Q)
            echo "До побачення!"
            exit 0
            ;;
        *)
            echo "Невірний вибір. Спробуйте ще раз."
            sleep 1
            ;;
    esac
done
