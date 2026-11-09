#!/usr/bin/env bash
# Cài ARAM Helper trên macOS: môi trường Python riêng (.venv) + thư viện + "ARAM Helper.app" trong ~/Applications.
# Chạy:  bash install-macos.sh        (tuỳ chọn: --no-app để không tạo .app)
# Trên macOS app có cửa sổ chính (tự nhận tướng trong trận, lõi, combo, trang bị). Tự đọc lõi trên màn hình,
# overlay và phím tắt hiện chỉ có trên Windows.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"
echo "=== Cài ARAM Helper (macOS) ==="
echo "Thư mục: $APP_DIR"

# 1. Python >= 3.10 có tkinter
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Chưa có Python 3.10 trở lên."
  echo "Cài bản chính thức (có sẵn tkinter): https://www.python.org/downloads/macos/"
  echo "hoặc Homebrew:  brew install python@3.12 python-tk@3.12"
  exit 1
fi
echo "Python: $("$PY" --version)"
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
  ver="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  echo "Python này thiếu tkinter (giao diện)."
  echo "Homebrew:  brew install python-tk@$ver   – hoặc cài Python từ python.org rồi chạy lại."
  exit 1
fi

# 2. Môi trường riêng + thư viện
if [ ! -x .venv/bin/python ]; then
  echo "Tạo môi trường Python riêng (.venv)..."
  "$PY" -m venv .venv
fi
echo "Cài thư viện..."
.venv/bin/python -m pip install --disable-pip-version-check -q --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
.venv/bin/python -c 'import tkinter, PIL; print("Kiểm tra thư viện: OK")'

# 3. Lệnh chạy bấm đúp trong Finder
cat > run-macos.command <<EOF
#!/usr/bin/env bash
cd "$APP_DIR" && exec .venv/bin/python app.py "\$@"
EOF
chmod +x run-macos.command

# 4. ARAM Helper.app trong ~/Applications (mở từ Launchpad / Spotlight)
if [ "${1:-}" != "--no-app" ]; then
  BUNDLE="$HOME/Applications/ARAM Helper.app"
  mkdir -p "$BUNDLE/Contents/MacOS"
  cat > "$BUNDLE/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>ARAM Helper</string>
  <key>CFBundleDisplayName</key><string>ARAM Helper</string>
  <key>CFBundleIdentifier</key><string>io.github.aram-helper</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>aram-helper</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
  cat > "$BUNDLE/Contents/MacOS/aram-helper" <<EOF
#!/usr/bin/env bash
cd "$APP_DIR" && exec .venv/bin/python app.py
EOF
  chmod +x "$BUNDLE/Contents/MacOS/aram-helper"
  echo "Đã tạo: $BUNDLE"
  echo "(Lần đầu mở nếu macOS chặn: chuột phải vào app → Open → Open.)"
fi

echo
echo "Cài xong! Mở 'ARAM Helper' trong ~/Applications, hoặc bấm đúp run-macos.command."
echo "Hướng dẫn: HUONG_DAN.md"
