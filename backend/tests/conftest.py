"""테스트 전역 환경 격리.

backend/.env 가 시연 배포용 값(`FRONTEND_URL=https://...`)을 가질 수 있어
테스트가 dev 환경 메시지 본문을 검증할 때 회귀가 발생한다. 테스트는
어떤 워킹 디렉토리에서 실행되든 결정적인 값을 봐야 하므로, app.* 가
import 되기 전에 os.environ 으로 핵심 설정을 고정한다.
"""

from __future__ import annotations

import os

_TEST_ENV: dict[str, str] = {
    "ENVIRONMENT": "test",
    "FRONTEND_URL": "http://localhost:5173",
    "CORS_ORIGINS": '["http://localhost:5173"]',
    "MESSAGE_PROVIDER": "mock",
    "STORAGE_PROVIDER": "local",
    "STORAGE_ROOT": "test_storage",
    "DATABASE_URL": "sqlite:///./test_cleaning_ops.db",
    "SENTRY_DSN": "",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value
