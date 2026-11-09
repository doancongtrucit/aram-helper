# Cài ARAM Helper trên Windows: môi trường Python riêng (.venv) + thư viện + shortcut Desktop / Start Menu.
# Chạy bằng cách bấm đúp install-windows.bat (hoặc: powershell -ExecutionPolicy Bypass -File install-windows.ps1)
# Tuỳ chọn: -NoShortcut (không tạo shortcut)
param([switch]$NoShortcut)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$App = $PSScriptRoot
Set-Location $App
Write-Host "=== Cài ARAM Helper ===" -ForegroundColor Cyan
Write-Host "Thư mục: $App"

# 1. Tìm Python >= 3.10
function Find-Python {
    foreach ($cmd in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = Get-Command $cmd[0] -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        $args_ = @($cmd | Select-Object -Skip 1) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        try { $ver = & $exe.Source @args_ 2>$null } catch { continue }
        if ($ver -match '^(\d+)\.(\d+)$' -and ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10))) {
            return @($exe.Source) + @($cmd | Select-Object -Skip 1)
        }
    }
    return @()
}

$py = @(Find-Python)
if ($py.Count -eq 0) {
    Write-Host "Chưa có Python 3.10 trở lên." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $ans = Read-Host "Cài Python 3.12 bằng winget ngay bây giờ? (Y/N)"
        if ($ans -match '^[Yy]') {
            winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            $py = @(Find-Python)
        }
    }
    if ($py.Count -eq 0) {
        Write-Host "Hãy cài Python từ https://www.python.org/downloads/ (tick 'Add python.exe to PATH') rồi chạy lại file này." -ForegroundColor Red
        exit 1
    }
}
$pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)
Write-Host ("Python: " + (& $pyExe @pyArgs --version))

# 2. Môi trường riêng .venv + thư viện
$venv = Join-Path $App ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "Tạo môi trường Python riêng (.venv)..."
    & $pyExe @pyArgs -m venv $venv
}
$vpy = Join-Path $venv "Scripts\python.exe"
$vpyw = Join-Path $venv "Scripts\pythonw.exe"
Write-Host "Cài thư viện (lần đầu mất 1-2 phút)..."
& $vpy -m pip install --disable-pip-version-check -q --upgrade pip
& $vpy -m pip install --disable-pip-version-check -q -r (Join-Path $App "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "Cài thư viện thất bại – kiểm tra kết nối mạng rồi chạy lại." -ForegroundColor Red; exit 1 }

# 3. Kiểm tra nhanh
& $vpy -c "import tkinter, PIL, numpy, cv2; print('Kiểm tra thư viện: OK')"
if ($LASTEXITCODE -ne 0) { Write-Host "Thiếu thư viện (tkinter đi kèm bản Python chính thức từ python.org)." -ForegroundColor Red; exit 1 }

# 4. Shortcut
if (-not $NoShortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $targets = @(
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "ARAM Helper.lnk"),
        (Join-Path ([Environment]::GetFolderPath("Programs")) "ARAM Helper.lnk")
    )
    foreach ($lnkPath in $targets) {
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.TargetPath = $vpyw
        $lnk.Arguments = '"' + (Join-Path $App "app.py") + '"'
        $lnk.WorkingDirectory = $App
        $lnk.Description = "ARAM Helper – gợi ý lõi ARAM Hỗn Loạn"
        $lnk.IconLocation = "$vpyw,0"
        $lnk.Save()
        Write-Host "Đã tạo shortcut: $lnkPath"
    }
}

Write-Host ""
Write-Host "Cài xong! Mở 'ARAM Helper' trên Desktop / Start Menu (hoặc bấm đúp run.bat)." -ForegroundColor Green
Write-Host "Hướng dẫn: HUONG_DAN.md"
