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


KAKAO_TEMPLATE_DEFINITIONS: dict[MessageType, KakaoTemplateDefinition] = {
    MessageType.CUSTOMER_SCHEDULE_CONFIRMED: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        template_id_setting="solapi_kakao_template_customer_schedule_confirmed",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    MessageType.CUSTOMER_DAY_BEFORE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        template_id_setting="solapi_kakao_template_customer_day_before",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    MessageType.PARTNER_ASSIGNMENT: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_ASSIGNMENT,
        template_id_setting="solapi_kakao_template_partner_assignment",
        variables=(
            KakaoTemplateVariable("#{협력사명}", "partner_name"),
            KakaoTemplateVariable("#{방문일정}", "schedule"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
            KakaoTemplateVariable("#{요청사항}", "special_request"),
        ),
    ),
    MessageType.CUSTOMER_PHOTO_READY: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_PHOTO_READY,
        template_id_setting="solapi_kakao_template_customer_photo_ready",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    MessageType.CUSTOMER_BALANCE_DUE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_BALANCE_DUE,
        template_id_setting="solapi_kakao_template_customer_balance_due",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
            KakaoTemplateVariable("#{고객링크}", "customer_link"),
        ),
    ),
    MessageType.CUSTOMER_QUOTE: KakaoTemplateDefinition(
        message_type=MessageType.CUSTOMER_QUOTE,
        template_id_setting="solapi_kakao_template_customer_quote",
        variables=(
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{서비스명}", "service_name"),
            KakaoTemplateVariable("#{수량}", "size_or_quantity"),
            KakaoTemplateVariable("#{소비자가}", "consumer_price"),
            KakaoTemplateVariable("#{할인가}", "discount_amount"),
            KakaoTemplateVariable("#{총금액}", "total_amount"),
            KakaoTemplateVariable("#{계약금}", "deposit_amount"),
            KakaoTemplateVariable("#{잔금}", "balance_amount"),
            KakaoTemplateVariable("#{VAT_표기}", "vat_label"),
            KakaoTemplateVariable("#{방문예정일}", "schedule"),
            KakaoTemplateVariable("#{회사명}", "company_name"),
        ),
    ),
    MessageType.PARTNER_CUSTOMER_INFO: KakaoTemplateDefinition(
        message_type=MessageType.PARTNER_CUSTOMER_INFO,
        template_id_setting="solapi_kakao_template_partner_customer_info",
        variables=(
            KakaoTemplateVariable("#{협력사담당자}", "partner_manager_name"),
            KakaoTemplateVariable("#{고객명}", "customer_name"),
            KakaoTemplateVariable("#{연락처마스킹}", "masked_customer_phone"),
            KakaoTemplateVariable("#{방문일}", "schedule"),
            KakaoTemplateVariable("#{주소}", "customer_address"),
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
