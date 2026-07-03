from dataclasses import dataclass

from app.domain.constants import MessageType


@dataclass(frozen=True)
class KakaoTemplateVariable:
    solapi_key: str
    context_key: str


@dataclass(frozen=True)
class KakaoTemplateDefinition:
    message_type: MessageType
    template_id_setting: str
    variables: tuple[KakaoTemplateVariable, ...]
    fallback_sms_enabled: bool = True


# ⚠️ 아래 변수(solapi_key)는 SOLAPI 콘솔에 실제 등록·검수된 '주식회사클린잡' 알림톡 템플릿의
# 치환문자와 1:1로 맞춰져 있다(2026-07 대조). 템플릿을 수정하면 여기 solapi_key도 함께 바꿔야
# 발송이 실패하지 않는다. context_key는 _build_template_context(services/messages.py)가 채운다.
# 참고: 사진/잔금/전날 템플릿의 고객 링크는 '변수'가 아니라 알림톡 '버튼'이라 여기 변수에 없다.
KAKAO_TEMPLATE_DEFINITIONS: dict[MessageType, KakaoTemplateDefinition] = {
    # 일정 확정 안내 (KA01TP260625095558697f6OQqqhxjqb)
    MessageType.CUSTOMER_SCHEDULE_CONFIRMED: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        template_id_setting="solapi_kakao_template_customer_schedule_confirmed",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{연락처}", "customer_phone"),
            KakaoTemplateVariable("#{금액}", "consumer_price"),
            KakaoTemplateVariable("#{계약금}", "deposit_amount"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
            KakaoTemplateVariable("#{총금액}", "total_amount"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    # 전날 안내 (KA01TP260625095745441foLkYjPPfnS) — 고객 링크는 버튼.
    MessageType.CUSTOMER_DAY_BEFORE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        template_id_setting="solapi_kakao_template_customer_day_before",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{연락처}", "customer_phone"),
        ),
    ),
    # 협력사 배정 안내 (KA01TP2606250958458291cETifwPnXY)
    # ⚠️ 이 템플릿은 문구가 '고객 대상'이다(안녕하세요 #{고객명}님 … 배정되었습니다). 코드는
    # PARTNER_ASSIGNMENT를 협력사에게 보낸다 — 수신자/문구 정합은 운영 확인 필요(변수는 아래로 충족).
    MessageType.PARTNER_ASSIGNMENT: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_ASSIGNMENT,
        template_id_setting="solapi_kakao_template_partner_assignment",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{협력사명}", "partner_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{연락처}", "customer_phone"),
            KakaoTemplateVariable("#{요청사항}", "special_request"),
        ),
    ),
    # 사진 링크 발송 (KA01TP260625095950577Dxz0dLAs9aH) — 고객 링크는 버튼.
    MessageType.CUSTOMER_PHOTO_READY: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_PHOTO_READY,
        template_id_setting="solapi_kakao_template_customer_photo_ready",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
        ),
    ),
    # 잔금 안내 (KA01TP260625100057110pUAJaMeQ99G) — 고객 링크는 버튼.
    MessageType.CUSTOMER_BALANCE_DUE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_BALANCE_DUE,
        template_id_setting="solapi_kakao_template_customer_balance_due",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
        ),
    ),
    # 견적 안내 (KA01TP260625100150149r4XMoHWve1R)
    MessageType.CUSTOMER_QUOTE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_QUOTE,
        template_id_setting="solapi_kakao_template_customer_quote",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{성함}", "customer_name"),
            KakaoTemplateVariable("#{금액}", "consumer_price"),
            KakaoTemplateVariable("#{할인가}", "discount_amount"),
            KakaoTemplateVariable("#{계약금}", "deposit_amount"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
            KakaoTemplateVariable("#{총금액}", "total_amount"),
        ),
    ),
    # 협력사 고객정보(미입금) (KA01TP260625100259815c7MUvtoPo72)
    MessageType.PARTNER_CUSTOMER_INFO: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_CUSTOMER_INFO,
        template_id_setting="solapi_kakao_template_partner_customer_info",
        variables=(
            KakaoTemplateVariable("#{담당자}", "partner_manager_name"),
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{연락처}", "customer_phone"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{요청사항}", "special_request"),
        ),
    ),
}


def get_kakao_template_definition(message_type: MessageType) -> KakaoTemplateDefinition | None:
    return KAKAO_TEMPLATE_DEFINITIONS.get(message_type)


def render_kakao_variables(
    definition: KakaoTemplateDefinition,
    context: dict[str, object],
) -> dict[str, str]:
    variables: dict[str, str] = {}
    for variable in definition.variables:
        value = context.get(variable.context_key)
        variables[variable.solapi_key] = str(value) if value not in (None, "") else "-"
    return variables
