#!/data/data/com.termux/files/usr/bin/bash
# scripts/termux_start.sh
# Place this script at ~/.termux/boot/start-ai.sh (or point Termux:Boot to it)
# It will start the watcher in the background in your Termux environment.

REPO_DIR="$HOME/linuxautoai"
cd "$REPO_DIR" || exit 1
# ensure python deps are installed (optional)
# pip3 install --user -r requirements.txt
nohup python3 watcher.py >/dev/null 2>&1 &
