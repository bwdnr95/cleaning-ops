"""SOLAPI SMS 단건 테스트 발송 스크립트.

목적: 앱 전체를 solapi 로 전환(MESSAGE_PROVIDER=solapi)하기 전에,
backend/.env 의 SOLAPI 자격증명/발신번호만으로 실제 1건 발송이 되는지 안전하게 검증한다.
MESSAGE_PROVIDER 값과 무관하게 SolapiMessageProvider 를 직접 호출한다.

사용법 (backend/ 디렉터리에서):
    python scripts/test_solapi_sms.py 01012345678
    python scripts/test_solapi_sms.py 01012345678 "원하는 테스트 문구"

전제: backend/.env 에 SOLAPI_API_KEY / SOLAPI_API_SECRET / SOLAPI_SENDER_NUMBER 채워둘 것.
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ 가 아니라 backend/ 를 import 경로에 둔다(어디서 실행해도 app 모듈 인식).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.domain.constants import MessageStatus  # noqa: E402
from app.services.messages import SolapiMessageProvider  # noqa: E402

DEFAULT_CONTENT = "[클린잡] SOLAPI 연동 테스트 문자입니다. (이 메시지가 도착하면 SMS 발송 정상)"


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: python scripts/test_solapi_sms.py <수신번호> [메시지]")
        return 2

    to_number = sys.argv[1]
    content = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CONTENT

    print("=== 사전 점검 ===")
    print(f"  발신번호(SENDER_NUMBER): {settings.solapi_sender_number or '(미설정 - .env 채우기 필요)'}")
    print(f"  API_KEY 설정됨: {bool(settings.solapi_api_key)}")
    print(f"  API_SECRET 설정됨: {bool(settings.solapi_api_secret)}")
    print(f"  - 수신번호: {to_number}")
    print(f"  - 내용: {content}")
    print()

    if not (settings.solapi_api_key and settings.solapi_api_secret and settings.solapi_sender_number):
        print("[중단] API_KEY / API_SECRET / SENDER_NUMBER 중 비어 있는 값이 있습니다. backend/.env 를 먼저 채우세요.")
        return 2

    result = SolapiMessageProvider().send(content, to_number)

    print("=== 결과 ===")
    print(f"  status: {result.status}")
    print(f"  error_message: {result.error_message}")
    print(f"  provider_status_code: {result.provider_status_code}")
    print(f"  provider_status_message: {result.provider_status_message}")
    print(f"  provider_message_id: {result.provider_message_id}")
    print(f"  provider_group_id: {result.provider_group_id}")
    print(f"  provider_response: {result.provider_response}")
    print()

    if result.status == MessageStatus.SENT:
        print("[성공] SOLAPI 가 발송을 접수했습니다. 실제 수신/전송결과는 SOLAPI 콘솔 또는 단말기로 확인하세요.")
        return 0
    print("[실패] 위 error_message / provider_response 로 원인을 확인하세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
