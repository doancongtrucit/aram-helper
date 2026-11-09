# Gỡ ARAM Helper trên Windows: xoá shortcut + môi trường .venv. Hỏi trước khi xoá dữ liệu cache (data\).
# Chạy: powershell -ExecutionPolicy Bypass -File uninstall-windows.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$App = $PSScriptRoot
foreach ($lnk in @(
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "ARAM Helper.lnk"),
        (Join-Path ([Environment]::GetFolderPath("Programs")) "ARAM Helper.lnk"))) {
    if (Test-Path $lnk) { Remove-Item $lnk -Confirm:$false; Write-Host "Đã xoá $lnk" }
}
$venv = Join-Path $App ".venv"
if (Test-Path $venv) { Remove-Item $venv -Recurse -Force -Confirm:$false; Write-Host "Đã xoá .venv" }
$data = Join-Path $App "data"
if (Test-Path $data) {
    $ans = Read-Host "Xoá luôn dữ liệu đã tải (data\: cache, icon, hiệu chỉnh, vị trí overlay)? (Y/N)"
    if ($ans -match '^[Yy]') { Remove-Item $data -Recurse -Force -Confirm:$false; Write-Host "Đã xoá data\" }
}
Write-Host "Đã gỡ. Có thể xoá cả thư mục $App nếu muốn."
