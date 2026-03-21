#!/bin/bash
# Claude Desktop launcher for Arch Linux
# Ensures correct Wayland app-id and blur setup
#
# Usage:
#   claude-desktop              Start the app
#   claude-desktop --reload-colors  Signal running instance to reload pywal colors
#
# To auto-reload after pywal, add to your alias:
#   alias pacw='wal -i ~/wallpaper/ -n && claude-desktop --reload-colors'

# Pass through --reload-colors to the Python script
if [[ "$1" == "--reload-colors" ]]; then
    exec python3 /usr/lib/claude-desktop/claude_desktop.py --reload-colors
    exit $?
fi

# If running under KDE Plasma, check for blur support
if [[ "$XDG_CURRENT_DESKTOP" == *"KDE"* ]] || [[ "$XDG_CURRENT_DESKTOP" == *"plasma"* ]]; then
    if ! pacman -Qi kwin-effects-forceblur &>/dev/null && \
       ! pacman -Qi kwin-effects-better-blur-dx &>/dev/null && \
       ! pacman -Qi kvantum &>/dev/null; then
        echo "[claude-desktop] For blur: install kvantum or kwin-effects-forceblur (AUR)" >&2
    fi
fi

exec python3 /usr/lib/claude-desktop/claude_desktop.py "$@"
