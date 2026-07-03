"""카카오 알림톡 템플릿 정의 ↔ SOLAPI 콘솔 등록 변수 정합 회귀 가드.

SOLAPI '주식회사클린잡' 채널에 검수 완료(발송 사용가능)된 템플릿의 치환문자와
KAKAO_TEMPLATE_DEFINITIONS의 solapi_key가 어긋나면 실발송이 실패하므로 여기서 잠근다.
템플릿을 콘솔에서 수정하면 이 기대값도 함께 갱신해야 한다.
"""

from app.domain.constants import MessageType
from app.domain.message_templates import get_kakao_template_definition, render_kakao_variables

# SOLAPI 콘솔(2026-07 대조) 템플릿별 실제 치환문자 집합.
EXPECTED_SOLAPI_KEYS = {
    MessageType.CUSTOMER_SCHEDULE_CONFIRMED: {
        "#{고객명}", "#{방문일정}", "#{서비스명}", "#{평수}", "#{대수}", "#{주소}",
        "#{연락처}", "#{금액}", "#{계약금}", "#{잔금}", "#{총금액}", "#{고객링크}",
    },
    MessageType.CUSTOMER_DAY_BEFORE: {
        "#{고객명}", "#{서비스명}", "#{방문일정}", "#{평수}", "#{대수}", "#{주소}", "#{연락처}",
        "#{고객링크}",
    },
    MessageType.PARTNER_ASSIGNMENT: {
        "#{고객명}", "#{서비스명}", "#{협력사명}", "#{방문일정}", "#{평수}", "#{대수}",
        "#{주소}", "#{연락처}", "#{요청사항}",
    },
    MessageType.CUSTOMER_PHOTO_READY: {"#{고객명}", "#{서비스명}", "#{고객링크}"},
    MessageType.CUSTOMER_BALANCE_DUE: {"#{고객명}", "#{서비스명}", "#{잔금}", "#{고객링크}"},
    MessageType.CUSTOMER_QUOTE: {
        "#{고객명}", "#{서비스명}", "#{방문일정}", "#{평수}", "#{대수}", "#{주소}", "#{성함}",
        "#{금액}", "#{할인가}", "#{계약금}", "#{잔금}", "#{총금액}",
    },
    MessageType.PARTNER_CUSTOMER_INFO: {
        "#{담당자}", "#{고객명}", "#{연락처}", "#{주소}", "#{요청사항}",
    },
}


def test_kakao_definitions_match_registered_solapi_variables():
    for mtype, keys in EXPECTED_SOLAPI_KEYS.items():
        definition = get_kakao_template_definition(mtype)
        assert definition is not None, mtype
        assert {v.solapi_key for v in definition.variables} == keys, mtype


def test_kakao_render_fills_every_variable_without_blank():
    # Kakao는 빈 변수를 거부하므로 모든 치환문자가 채워져야 한다("-" 허용).
    context = {
        "customer_name": "홍길동", "service_name": "입주청소", "schedule": "6/10 오후",
        "size_or_quantity": "30평", "unit_count": "-", "customer_address": "서울 강남",
        "customer_phone": "010-1234-5678", "consumer_price": "300,000원",
        "deposit_amount": "100,000원", "balance_amount": "200,000원", "total_amount": "300,000원",
        "discount_amount": "0원", "customer_link": "https://x.kr/c/tok",
        "customer_link_button": "x.kr/c/tok", "partner_name": "청소왕",
        "partner_manager_name": "김담당", "special_request": "현관 비번 1234",
    }
    for mtype in EXPECTED_SOLAPI_KEYS:
        rendered = render_kakao_variables(get_kakao_template_definition(mtype), context)
        assert set(rendered.keys()) == EXPECTED_SOLAPI_KEYS[mtype], mtype
        assert all(value for value in rendered.values()), (mtype, rendered)

    # 대표 매핑 스팟체크.
    schedule = render_kakao_variables(
        get_kakao_template_definition(MessageType.CUSTOMER_SCHEDULE_CONFIRMED), context
    )
    assert schedule["#{연락처}"] == "010-1234-5678"
    # 일정확정의 #{고객링크}는 '본문' 변수 → 풀 URL(scheme 포함).
    assert schedule["#{고객링크}"] == "https://x.kr/c/tok"
    assert schedule["#{대수}"] == "-"  # size_or_quantity가 단일 필드라 대수는 "-"

    # 사진/전날/잔금의 #{고객링크}는 '버튼 웹링크' 변수 → 템플릿이 https:// 를 붙이므로
    # 값에는 scheme 이 없어야 한다(이중 프로토콜 방지).
    for mtype in (
        MessageType.CUSTOMER_PHOTO_READY,
        MessageType.CUSTOMER_DAY_BEFORE,
        MessageType.CUSTOMER_BALANCE_DUE,
    ):
        rendered = render_kakao_variables(get_kakao_template_definition(mtype), context)
        assert rendered["#{고객링크}"] == "x.kr/c/tok", mtype
        assert "://" not in rendered["#{고객링크}"], mtype
