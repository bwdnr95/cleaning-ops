param(
  [int]$Port = 8002,
  [string]$FrontendUrl = "http://127.0.0.1:5175"
)

$ErrorActionPreference = "Stop"

$origin = $FrontendUrl.TrimEnd("/")

$env:ENVIRONMENT = "e2e"
$env:DATABASE_URL = "sqlite:///./e2e_cleaning_ops.db"
$env:FRONTEND_URL = $origin
$env:CORS_ORIGINS = "[`"$origin`"]"
$env:STORAGE_ROOT = "e2e_storage"
# E2E는 절대 실제 문자/알림톡을 보내지 않는다(.env 의 solapi 설정을 무시하고 mock 강제).
$env:MESSAGE_PROVIDER = "mock"

python -m scripts.reset_e2e_db
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
