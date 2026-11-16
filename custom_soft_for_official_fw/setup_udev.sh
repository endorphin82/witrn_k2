#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_SRC="$SCRIPT_DIR/99-witrn-k2.rules"
RULES_DEST="/etc/udev/rules.d/99-witrn-k2.rules"

echo "=== Встановлення правил udev для WITRN K2 ==="

if [ "$EUID" -ne 0 ]; then
    echo "Запуск з підвищеними привілеями (sudo)..."
    sudo cp "$RULES_SRC" "$RULES_DEST"
    sudo chmod 644 "$RULES_DEST"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --attr-match=idVendor=0716 --attr-match=idProduct=5060
else
    cp "$RULES_SRC" "$RULES_DEST"
    chmod 644 "$RULES_DEST"
    udevadm control --reload-rules
    udevadm trigger --attr-match=idVendor=0716 --attr-match=idProduct=5060
fi

echo "✓ Правила успішно встановлено в $RULES_DEST"
echo "✓ Правила udev перезавантажено та активовано."
