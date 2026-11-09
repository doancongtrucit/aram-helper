#!/usr/bin/env bash
# Gỡ ARAM Helper trên macOS: xoá .app, .venv, run-macos.command. Hỏi trước khi xoá dữ liệu cache (data/).
set -eu
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$HOME/Applications/ARAM Helper.app" "$APP_DIR/.venv" "$APP_DIR/run-macos.command"
echo "Đã xoá ARAM Helper.app, .venv, run-macos.command"
if [ -d "$APP_DIR/data" ]; then
  read -r -p "Xoá luôn dữ liệu đã tải (data/)? (y/N) " ans
  case "$ans" in [Yy]*) rm -rf "$APP_DIR/data"; echo "Đã xoá data/";; esac
fi
echo "Đã gỡ. Có thể xoá cả thư mục $APP_DIR nếu muốn."
