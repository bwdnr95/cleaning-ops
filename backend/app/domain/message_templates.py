from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.constants import MessageType


@dataclass(frozen=True)
class KakaoTemplateVariable:
    solapi_key: str
    context_key: str


@dataclass(frozen=True)
class KakaoTemplateDefinition:
    message_type: MessageType
    expected_template_id: str
    template_id_setting: str
    variables: tuple[KakaoTemplateVariable, ...]
    fallback_sms_enabled: bool = True


# ⚠️ 아래 변수(solapi_key)는 SOLAPI 콘솔에 실제 등록·검수된 '주식회사클린잡' 알림톡 템플릿의
# 치환문자와 1:1로 맞춰져 있다(2026-07 대조). 템플릿을 수정하면 여기 solapi_key도 함께 바꿔야
# 발송이 실패하지 않는다. context_key는 _build_template_context(services/messages.py)가 채운다.
# 참고: 사진/잔금/전날 템플릿의 고객 링크는 알림톡 '버튼'의 웹링크(#{고객링크})다. 버튼 URL이
# `https://#{고객링크}` 로 등록돼 있어 이 변수 역시 kakaoOptions.variables 로 반드시 넘겨야 하며
# (안 넘기면 필수변수 누락으로 발송 실패), 값은 scheme 없는 customer_link_button 을 쓴다.
# 일정확정은 #{고객링크}가 '본문' 변수라 풀 URL(customer_link)을 그대로 쓴다.
SOLAPI_KAKAO_PROFILE_ID = "KA01PF260625095328232y4DcSniavuQ"


KAKAO_TEMPLATE_DEFINITIONS: dict[MessageType, KakaoTemplateDefinition] = {
    # 일정 확정 안내 (KA01TP260625095558697f6OQqqhxjqb)
    MessageType.CUSTOMER_SCHEDULE_CONFIRMED: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        expected_template_id="KA01TP260625095558697f6OQqqhxjqb",
        template_id_setting="solapi_kakao_template_customer_schedule_confirmed",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{연락처}", "customer_phone_without_auth_suffix"),
            KakaoTemplateVariable("#{금액}", "schedule_consumer_price"),
            KakaoTemplateVariable("#{계약금}", "schedule_deposit_amount"),
            KakaoTemplateVariable("#{잔금}", "schedule_balance_amount"),
            KakaoTemplateVariable("#{총금액}", "schedule_total_amount"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    # 전날 안내 (KA01TP260625095745441foLkYjPPfnS) — 고객 링크는 버튼 웹링크(#{고객링크}).
    MessageType.CUSTOMER_DAY_BEFORE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        expected_template_id="KA01TP260625095745441foLkYjPPfnS",
        template_id_setting="solapi_kakao_template_customer_day_before",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{평수}", "size_or_quantity"),
            KakaoTemplateVariable("#{대수}", "unit_count"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{연락처}", "customer_phone_without_auth_suffix"),
            KakaoTemplateVariable("#{고객링크}", "customer_link_button"),
        ),
    ),
    MessageType.PARTNER_ASSIGNMENT: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_ASSIGNMENT,
        expected_template_id="KA01TP260703114932918wBetIEHC8dg",
        template_id_setting="solapi_kakao_template_partner_job_assignment",
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
            KakaoTemplateVariable("#{협력사링크}", "partner_login_link_button"),
        ),
    ),
    # 사진 링크 발송 (KA01TP260625095950577Dxz0dLAs9aH) — 고객 링크는 버튼 웹링크(#{고객링크}).
    MessageType.CUSTOMER_PHOTO_READY: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_PHOTO_READY,
        expected_template_id="KA01TP260625095950577Dxz0dLAs9aH",
        template_id_setting="solapi_kakao_template_customer_photo_ready",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{고객링크}", "customer_link_button"),
        ),
    ),
    # 잔금 안내 (KA01TP260625100057110pUAJaMeQ99G) — 고객 링크는 버튼 웹링크(#{고객링크}).
    MessageType.CUSTOMER_BALANCE_DUE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_BALANCE_DUE,
        expected_template_id="KA01TP260625100057110pUAJaMeQ99G",
        template_id_setting="solapi_kakao_template_customer_balance_due",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
            KakaoTemplateVariable("#{고객링크}", "customer_link_button"),
        ),
    ),
    # 견적 안내 (KA01TP260625100150149r4XMoHWve1R)
    MessageType.CUSTOMER_QUOTE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_QUOTE,
        expected_template_id="KA01TP260625100150149r4XMoHWve1R",
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
        expected_template_id="KA01TP260625100259815c7MUvtoPo72",
        template_id_setting="solapi_kakao_template_partner_customer_info",
        variables=(
            KakaoTemplateVariable("#{담당자}", "partner_manager_name"),
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{연락처}", "customer_phone"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{요청사항}", "special_request"),
        ),
    ),
    MessageType.PARTNER_AS_REQUEST: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_AS_REQUEST,
        expected_template_id="KA01TP2607090709454037h9FwYAHMbW",
        template_id_setting="solapi_kakao_template_partner_as_request",
        variables=(
            KakaoTemplateVariable("#{협력사명}", "partner_name"),
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{협력사링크}", "partner_login_link_button"),
        ),
    ),
    MessageType.CUSTOMER_AS_NOTICE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_AS_NOTICE,
        expected_template_id="KA01TP260709071111937Ctnx5OzcNNq",
        template_id_setting="solapi_kakao_template_customer_as_notice",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{고객링크}", "customer_link_button"),
        ),
    ),
}


def get_kakao_template_definition(message_type: MessageType) -> KakaoTemplateDefinition | None:
    return KAKAO_TEMPLATE_DEFINITIONS.get(message_type)


def render_kakao_variables(
    definition: KakaoTemplateDefinition,
    context: Mapping[str, object],
) -> dict[str, str]:
    variables: dict[str, str] = {}
    for variable in definition.variables:
        value = context.get(variable.context_key)
        variables[variable.solapi_key] = str(value) if value not in (None, "") else "-"
    return variables
