param(
  [int]$Port = 8002,
  [string]$FrontendUrl = "http://127.0.0.1:5175",
  [string]$RunId = "$Port-$PID"
)

$ErrorActionPreference = "Stop"

$origin = $FrontendUrl.TrimEnd("/")
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') {
  throw "Invalid E2E run id"
}
$e2eRoot = [System.IO.Path]::GetFullPath(
  (Join-Path ([System.IO.Path]::GetTempPath()) "cleaning-ops-e2e")
)
$runPath = [System.IO.Path]::GetFullPath((Join-Path $e2eRoot $RunId))
$rootPrefix = $e2eRoot.TrimEnd("\") + "\"
if (-not $runPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Invalid E2E run path"
}
$databasePath = [System.IO.Path]::GetFullPath(
  (Join-Path $runPath "e2e_cleaning_ops.db")
)
$storagePath = [System.IO.Path]::GetFullPath(
  (Join-Path $runPath "storage")
)
New-Item -ItemType Directory -Path $runPath -Force | Out-Null
Set-Content -LiteralPath (Join-Path $runPath "server.pid") -Value ([string]$PID) -NoNewline
$databaseUrlPath = $databasePath.Replace("\", "/")

$env:ENVIRONMENT = "e2e"
$env:DATABASE_URL = "sqlite:///$databaseUrlPath"
$env:FRONTEND_URL = $origin
$env:CORS_ORIGINS = "[`"$origin`"]"
$env:STORAGE_ROOT = $storagePath
# E2E는 절대 실제 문자/알림톡을 보내지 않는다(.env 의 solapi 설정을 무시하고 mock 강제).
$env:MESSAGE_PROVIDER = "mock"

$serverExitCode = 0
try {
  python -m scripts.reset_e2e_db
  if ($LASTEXITCODE -ne 0) {
    throw "E2E database reset failed with exit code $LASTEXITCODE"
  }
  python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
  $serverExitCode = $LASTEXITCODE
} finally {
  if ($runPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $runPath -Recurse -Force -ErrorAction SilentlyContinue
  }
}
exit $serverExitCode
