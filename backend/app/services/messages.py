import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from http.client import HTTPException as HttpClientException
from json import JSONDecodeError
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import business_now, business_today, to_business_time, to_utc
from app.domain.constants import (
    MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES,
    MessageChannel,
    MessageStatus,
    MessageType,
    OrderStatus,
    RecipientType,
    TimelineEventType,
)
from app.domain.message_templates import (
    KAKAO_TEMPLATE_DEFINITIONS,
    get_kakao_template_definition,
    render_kakao_variables,
)
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PaymentStatus
from app.domain.phone import normalize_phone
from app.models.message import MessageLog
from app.models.order import Order
from app.models.partner import Partner
from app.repositories.messages import MessageRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.photos import PhotoRepository
from app.schemas.message import (
    DayBeforeNoticeRunRead,
    MessageLogRead,
    MessagePreviewRead,
    MessageSendRequest,
    MessageSettingsRead,
)
from app.services.timeline import TimelineService

logger = logging.getLogger(__name__)

SOLAPI_MESSAGE_LOG_CUSTOM_FIELD = "cleaningOpsMessageLogId"
SOLAPI_SMS_MAX_BYTES = 90


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request: Request, timeout: float):
    return build_opener(NoRedirectHandler()).open(request, timeout=timeout)


# 본문/카카오 템플릿에 고객 링크(customer_token 기반)가 포함되는 고객 메시지 타입.
# 이 타입들은 customer_token 이 없으면 죽은 링크를 보내지 않고 발송 실패로 처리한다.
MESSAGE_TYPES_WITH_CUSTOMER_LINK: frozenset[MessageType] = frozenset(
    {
        MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        MessageType.CUSTOMER_DAY_BEFORE,
        MessageType.CUSTOMER_PHOTO_READY,
        MessageType.CUSTOMER_BALANCE_DUE,
        MessageType.CUSTOMER_AS_NOTICE,
        MessageType.CUSTOMER_ACCESS_LINK,
    }
)

DAY_BEFORE_NOTICE_AUTOMATION_STATUSES: set[str] = {
    OrderStatus.SCHEDULE_CONFIRMED.value,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
    OrderStatus.SCHEDULED.value,
}

DAY_BEFORE_NOTICE_RECOVERY_STATUSES: frozenset[str] = frozenset(
    {
        *DAY_BEFORE_NOTICE_AUTOMATION_STATUSES,
        OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
    }
)

PARTNER_ASSIGNMENT_RECOVERY_STATUSES: frozenset[str] = frozenset(
    {
        OrderStatus.NEW.value,
        OrderStatus.CONSULTING.value,
        OrderStatus.PARTNER_CONFIRMING.value,
        OrderStatus.SCHEDULE_CONFIRMED.value,
        OrderStatus.DAY_BEFORE_NOTICE_NEEDED.value,
        OrderStatus.DAY_BEFORE_NOTICE_DONE.value,
        OrderStatus.SCHEDULED.value,
        OrderStatus.IN_PROGRESS.value,
    }
)

SCHEDULE_CONFIRMATION_RECOVERY_STATUSES: frozenset[str] = frozenset(
    {
        OrderStatus.SCHEDULE_CONFIRMED.value,
        OrderStatus.SCHEDULED.value,
    }
)

BALANCE_NOTICE_ALLOWED_STATUSES: frozenset[str] = frozenset(
    {
        OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
        OrderStatus.CUSTOMER_DELIVERY_DONE.value,
        OrderStatus.COMPLETED.value,
    }
)


@dataclass(frozen=True)
class MessageSendResult:
    status: MessageStatus
    error_message: str | None = None
    channel: MessageChannel | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    provider_group_id: str | None = None
    provider_error_code: str | None = None
    provider_status_code: str | None = None
    provider_status_message: str | None = None
    provider_response: dict[str, object] | None = None
    provider_reported_at: datetime | None = None
    delivered_at: datetime | None = None


def solapi_unknown_outcome(
    *,
    channel: MessageChannel | None,
    error_message: str,
    error_code: str,
    provider_response: dict[str, object] | None = None,
) -> MessageSendResult:
    return MessageSendResult(
        status=MessageStatus.PENDING,
        error_message=error_message,
        channel=channel,
        provider="solapi",
        provider_error_code=error_code,
        provider_status_message="provider acceptance could not be confirmed",
        provider_response=provider_response,
    )


@dataclass(frozen=True)
class SolapiWebhookProcessResult:
    received: int
    updated: int
    ignored: int
    unknown: int


@dataclass(frozen=True)
class NotificationRecoveryTarget:
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    successful_since: datetime
    expected_scheduled_date: date | None = None


@dataclass(frozen=True)
class NotificationRecoveryRunResult:
    scanned_orders: int
    attempted: int
    sent: int
    skipped: int
    failed: int


@dataclass(frozen=True)
class MessageProviderSendInput:
    content: str
    recipient_phone: str
    channel: MessageChannel
    message_type: MessageType
    kakao_template_id: str | None = None
    kakao_variables: dict[str, str] | None = None
    fallback_sms_content: str | None = None
    message_log_id: str | None = None


class KakaoPreviewState(TypedDict):
    kakao_channel_id_configured: bool
    kakao_template_configured: bool
    fallback_sms_enabled: bool
    can_send: bool
    warnings: list[str]


class MessageProvider:
    provider_name = "unknown"

    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        raise NotImplementedError

    def send_with_context(self, send_input: MessageProviderSendInput) -> MessageSendResult:
        return self.send(send_input.content, send_input.recipient_phone)


class MockMessageProvider(MessageProvider):
    provider_name = "mock"

    def send_with_context(self, send_input: MessageProviderSendInput) -> MessageSendResult:
        if not send_input.content or not send_input.recipient_phone:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                error_message="missing_recipient",
                channel=send_input.channel,
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )
        return MessageSendResult(
            status=MessageStatus.SENT,
            channel=send_input.channel,
            provider=self.provider_name,
        )

    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        if not content or not recipient_phone:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                error_message="missing_recipient",
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )
        return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)


class ConfigurationErrorMessageProvider(MessageProvider):
    provider_name = "configuration_error"

    def __init__(self, error_message: str) -> None:
        self.error_message = error_message

    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        return MessageSendResult(
            status=MessageStatus.FAILED,
            error_message=self.error_message,
            provider=self.provider_name,
            provider_error_code="unsupported_message_provider",
        )


class SolapiMessageProvider(MessageProvider):
    provider_name = "solapi"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        sender_number: str | None = None,
        send_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.solapi_api_key
        self.api_secret = api_secret if api_secret is not None else settings.solapi_api_secret
        self.sender_number = (
            sender_number if sender_number is not None else settings.solapi_sender_number
        )
        self.send_url = send_url or settings.solapi_send_url
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.solapi_timeout_seconds
        )

    def send_with_context(self, send_input: MessageProviderSendInput) -> MessageSendResult:
        if send_input.channel == MessageChannel.ALIMTALK:
            return self._send_kakao_alimtalk(send_input)
        return self._send_text_message(
            send_input.content,
            send_input.recipient_phone,
            requested_channel=send_input.channel,
            message_log_id=send_input.message_log_id,
        )

    def send(self, content: str, recipient_phone: str) -> MessageSendResult:
        return self._send_text_message(
            content,
            recipient_phone,
            requested_channel=MessageChannel.SMS,
            message_log_id=None,
        )

    def _send_text_message(
        self,
        content: str,
        recipient_phone: str,
        *,
        requested_channel: MessageChannel,
        message_log_id: str | None,
    ) -> MessageSendResult:
        actual_channel = self._resolve_text_channel(content, requested_channel)
        if not content or not recipient_phone:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message="missing_recipient",
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )
        if not self.api_key or not self.api_secret:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message="solapi_missing_credentials",
                provider=self.provider_name,
                provider_error_code="solapi_missing_credentials",
            )

        from_number = normalize_phone(self.sender_number)
        if not from_number:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message="solapi_missing_sender_number",
                provider=self.provider_name,
                provider_error_code="solapi_missing_sender_number",
            )

        to_number = normalize_phone(recipient_phone)
        if not to_number:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message="missing_recipient",
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )

        message: dict[str, object] = {
            "to": to_number,
            "from": from_number,
            "text": content,
            "type": actual_channel.value.upper(),
        }
        if message_log_id:
            message["customFields"] = {
                SOLAPI_MESSAGE_LOG_CUSTOM_FIELD: message_log_id,
            }
        payload: dict[str, object] = {"messages": [message]}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.send_url,
            data=body,
            headers={
                "Authorization": build_solapi_auth_header(self.api_key, self.api_secret),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.warning("Solapi HTTP error: status=%s", exc.code)
            if exc.code >= 500:
                return solapi_unknown_outcome(
                    channel=actual_channel,
                    error_message="solapi_outcome_unknown",
                    error_code="solapi_outcome_unknown",
                )
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message=f"solapi_http_error: {exc.code} {read_solapi_error_body(exc)}",
                provider=self.provider_name,
                provider_error_code="solapi_http_error",
            )
        except (TimeoutError, URLError, OSError, HttpClientException, UnicodeError) as exc:
            logger.warning("Solapi request outcome is unknown: %s", type(exc).__name__)
            return solapi_unknown_outcome(
                channel=actual_channel,
                error_message="solapi_outcome_unknown",
                error_code="solapi_outcome_unknown",
            )

        try:
            decoded_payload = json.loads(raw_body) if raw_body else {}
        except JSONDecodeError:
            return solapi_unknown_outcome(
                channel=actual_channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
            )
        if not isinstance(decoded_payload, dict):
            return solapi_unknown_outcome(
                channel=actual_channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
            )

        failure_reason = extract_solapi_failure_reason(decoded_payload)
        if failure_reason:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=actual_channel,
                error_message=f"solapi_failed: {failure_reason}",
                provider=self.provider_name,
                provider_error_code="solapi_provider_failed",
                provider_group_id=extract_solapi_group_id(decoded_payload),
                provider_message_id=extract_solapi_message_id(decoded_payload),
                provider_status_code=extract_solapi_status_code(decoded_payload),
                provider_status_message=extract_solapi_status_message(decoded_payload),
                provider_response=decoded_payload,
            )

        provider_group_id = extract_solapi_group_id(decoded_payload)
        provider_message_id = extract_solapi_message_id(decoded_payload)
        if not provider_group_id and not provider_message_id:
            return solapi_unknown_outcome(
                channel=actual_channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
                provider_response=decoded_payload,
            )

        return MessageSendResult(
            status=MessageStatus.SENT,
            channel=actual_channel,
            provider=self.provider_name,
            provider_group_id=provider_group_id,
            provider_message_id=provider_message_id,
            provider_status_code=extract_solapi_status_code(decoded_payload),
            provider_status_message=extract_solapi_status_message(decoded_payload),
            provider_response=decoded_payload,
        )

    @staticmethod
    def _resolve_text_channel(
        content: str,
        requested_channel: MessageChannel,
    ) -> MessageChannel:
        if requested_channel not in {MessageChannel.SMS, MessageChannel.LMS}:
            raise ValueError("unsupported_text_channel")
        if (
            requested_channel == MessageChannel.LMS
            or len(content.encode("utf-8")) > SOLAPI_SMS_MAX_BYTES
        ):
            return MessageChannel.LMS
        return MessageChannel.SMS

    def _send_kakao_alimtalk(self, send_input: MessageProviderSendInput) -> MessageSendResult:
        result = self._send_kakao_alimtalk_once(send_input)
        if result.status != MessageStatus.FAILED or not send_input.fallback_sms_content:
            return result

        fallback = self._send_text_message(
            send_input.fallback_sms_content,
            send_input.recipient_phone,
            requested_channel=MessageChannel.SMS,
            message_log_id=send_input.message_log_id,
        )
        if fallback.status == MessageStatus.PENDING:
            return MessageSendResult(
                status=MessageStatus.PENDING,
                channel=fallback.channel or MessageChannel.SMS,
                error_message=fallback.error_message,
                provider=self.provider_name,
                provider_error_code=fallback.provider_error_code,
                provider_message_id=fallback.provider_message_id,
                provider_group_id=fallback.provider_group_id,
                provider_status_code=fallback.provider_status_code,
                provider_status_message="alimtalk_failed_sms_fallback_outcome_unknown",
                provider_response={
                    "alimtalk": result.provider_response or {"error": result.error_message},
                    "fallback_sms": fallback.provider_response or {"error": fallback.error_message},
                },
            )
        if fallback.status != MessageStatus.SENT:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message=result.error_message,
                provider=self.provider_name,
                provider_error_code=result.provider_error_code,
                provider_status_message="alimtalk_failed_and_sms_fallback_failed",
                provider_response={
                    "alimtalk": result.provider_response or {"error": result.error_message},
                    "fallback_sms": fallback.provider_response or {"error": fallback.error_message},
                },
            )

        return MessageSendResult(
            status=MessageStatus.SENT,
            channel=fallback.channel or MessageChannel.SMS,
            provider=self.provider_name,
            provider_message_id=fallback.provider_message_id,
            provider_group_id=fallback.provider_group_id,
            provider_status_code=fallback.provider_status_code,
            provider_status_message="alimtalk_failed_sms_fallback_sent",
            provider_response={
                "alimtalk": result.provider_response or {"error": result.error_message},
                "fallback_sms": fallback.provider_response,
            },
        )

    def _send_kakao_alimtalk_once(self, send_input: MessageProviderSendInput) -> MessageSendResult:
        if not send_input.recipient_phone:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="missing_recipient",
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )
        if not self.api_key or not self.api_secret:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="solapi_missing_credentials",
                provider=self.provider_name,
                provider_error_code="solapi_missing_credentials",
            )

        from_number = normalize_phone(self.sender_number)
        if not from_number:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="solapi_missing_sender_number",
                provider=self.provider_name,
                provider_error_code="solapi_missing_sender_number",
            )

        to_number = normalize_phone(send_input.recipient_phone)
        if not to_number:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="missing_recipient",
                provider=self.provider_name,
                provider_error_code="missing_recipient",
            )

        sender_profile_id = get_solapi_kakao_sender_profile_id()
        if not sender_profile_id:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="solapi_missing_kakao_pf_id",
                provider=self.provider_name,
                provider_error_code="solapi_missing_kakao_pf_id",
            )

        if not send_input.kakao_template_id:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=MessageChannel.ALIMTALK,
                error_message="solapi_missing_kakao_template_id",
                provider=self.provider_name,
                provider_error_code="solapi_missing_kakao_template_id",
            )

        message: dict[str, object] = {
            "to": to_number,
            "from": from_number,
            "text": send_input.fallback_sms_content or send_input.content,
            "type": "ATA",
            "kakaoOptions": {
                "pfId": sender_profile_id,
                "templateId": send_input.kakao_template_id,
                "disableSms": not settings.solapi_alimtalk_fallback_sms,
                "variables": send_input.kakao_variables or {},
            },
        }
        if send_input.message_log_id:
            message["customFields"] = {
                SOLAPI_MESSAGE_LOG_CUSTOM_FIELD: send_input.message_log_id,
            }
        payload: dict[str, object] = {"messages": [message]}
        return self._post_solapi_payload(payload, channel=MessageChannel.ALIMTALK)

    def _post_solapi_payload(
        self,
        payload: dict[str, object],
        *,
        channel: MessageChannel,
    ) -> MessageSendResult:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.send_url,
            data=body,
            headers={
                "Authorization": build_solapi_auth_header(self.api_key, self.api_secret),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.warning("Solapi HTTP error: status=%s", exc.code)
            if exc.code >= 500:
                return solapi_unknown_outcome(
                    channel=channel,
                    error_message="solapi_outcome_unknown",
                    error_code="solapi_outcome_unknown",
                )
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=channel,
                error_message=f"solapi_http_error: {exc.code} {read_solapi_error_body(exc)}",
                provider=self.provider_name,
                provider_error_code="solapi_http_error",
            )
        except (TimeoutError, URLError, OSError, HttpClientException, UnicodeError) as exc:
            logger.warning("Solapi request outcome is unknown: %s", type(exc).__name__)
            return solapi_unknown_outcome(
                channel=channel,
                error_message="solapi_outcome_unknown",
                error_code="solapi_outcome_unknown",
            )

        try:
            decoded_payload = json.loads(raw_body) if raw_body else {}
        except JSONDecodeError:
            return solapi_unknown_outcome(
                channel=channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
            )
        if not isinstance(decoded_payload, dict):
            return solapi_unknown_outcome(
                channel=channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
            )

        failure_reason = extract_solapi_failure_reason(decoded_payload)
        if failure_reason:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                channel=channel,
                error_message=f"solapi_failed: {failure_reason}",
                provider=self.provider_name,
                provider_error_code="solapi_provider_failed",
                provider_group_id=extract_solapi_group_id(decoded_payload),
                provider_message_id=extract_solapi_message_id(decoded_payload),
                provider_status_code=extract_solapi_status_code(decoded_payload),
                provider_status_message=extract_solapi_status_message(decoded_payload),
                provider_response=decoded_payload,
            )

        provider_group_id = extract_solapi_group_id(decoded_payload)
        provider_message_id = extract_solapi_message_id(decoded_payload)
        if not provider_group_id and not provider_message_id:
            return solapi_unknown_outcome(
                channel=channel,
                error_message="solapi_invalid_response",
                error_code="solapi_invalid_response",
                provider_response=decoded_payload,
            )

        return MessageSendResult(
            status=MessageStatus.SENT,
            channel=channel,
            provider=self.provider_name,
            provider_group_id=provider_group_id,
            provider_message_id=provider_message_id,
            provider_status_code=extract_solapi_status_code(decoded_payload),
            provider_status_message=extract_solapi_status_message(decoded_payload),
            provider_response=decoded_payload,
        )


def build_message_provider() -> MessageProvider:
    provider_name = settings.message_provider.strip().lower()
    if provider_name in {"", "mock"}:
        return MockMessageProvider()
    if provider_name == "solapi":
        return SolapiMessageProvider()
    return ConfigurationErrorMessageProvider(f"unsupported_message_provider: {provider_name}")


def build_solapi_auth_header(
    api_key: str,
    api_secret: str,
    *,
    now: datetime | None = None,
    salt: str | None = None,
) -> str:
    sent_at = now or datetime.now(UTC)
    date_text = sent_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt_text = salt or uuid4().hex
    signature = hmac.new(
        api_secret.encode("utf-8"),
        f"{date_text}{salt_text}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"HMAC-SHA256 apiKey={api_key}, date={date_text}, salt={salt_text}, signature={signature}"
    )


def extract_solapi_failure_reason(response_payload: dict[str, object]) -> str | None:
    failed_messages = response_payload.get("failedMessageList")
    if not isinstance(failed_messages, list) or not failed_messages:
        return None

    first_failure = failed_messages[0]
    if not isinstance(first_failure, dict):
        return "unknown"

    for key in ("reason", "errorMessage", "message"):
        value = first_failure.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def extract_solapi_group_id(response_payload: dict[str, object]) -> str | None:
    group_info = response_payload.get("groupInfo")
    if not isinstance(group_info, dict):
        return None
    for key in ("groupId", "_id", "id"):
        value = group_info.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def extract_solapi_message_id(response_payload: dict[str, object]) -> str | None:
    for key in ("messageId", "_id", "id"):
        value = response_payload.get(key)
        if isinstance(value, str) and value:
            return value

    message_list = response_payload.get("messageList")
    if not isinstance(message_list, list) or not message_list:
        return None
    first_message = message_list[0]
    if not isinstance(first_message, dict):
        return None
    for key in ("messageId", "_id", "id"):
        value = first_message.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def extract_solapi_status_code(response_payload: dict[str, object]) -> str | None:
    return string_value(response_payload.get("statusCode"))


def extract_solapi_status_message(response_payload: dict[str, object]) -> str | None:
    for key in ("statusMessage", "message", "reason", "errorMessage"):
        value = string_value(response_payload.get(key))
        if value:
            return value
    return None


def parse_solapi_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# 메시지 배송 수명주기 순서. 솔라피 배송 리포트가 순서를 뒤집어 도착해도
# (예: DELIVERED 이후 늦게 SENT 가 들어오는 경우) 상태가 후퇴하지 않도록 강제한다.
# FAILED/DELIVERY_FAILED 는 종결 상태로 취급하여 더 이상 전이하지 않는다.
MESSAGE_LIFECYCLE_ORDER: dict[MessageStatus, int] = {
    MessageStatus.PENDING: 10,
    MessageStatus.SENT: 20,
    MessageStatus.DELIVERED: 30,
}

# 종결(terminal) 상태: 한 번 진입하면 배송 리포트로 덮어쓰지 않는다.
MESSAGE_TERMINAL_STATUSES: frozenset[MessageStatus] = frozenset(
    {MessageStatus.FAILED, MessageStatus.DELIVERY_FAILED, MessageStatus.DELIVERED}
)


def is_monotonic_delivery_transition(
    current: MessageStatus,
    next_status: MessageStatus,
) -> bool:
    """배송 리포트로 적용하려는 next_status 가 수명주기를 전진시키는지 판단한다.

    - 현재 상태가 종결 상태면 어떤 전이도 허용하지 않는다.
    - DELIVERY_FAILED 로의 전이는 (실패 기록 목적) 항상 허용한다.
    - 그 외에는 정의된 순서상 더 앞으로 나아갈 때만 허용한다.
    """
    if current in MESSAGE_TERMINAL_STATUSES:
        return False
    if next_status == MessageStatus.DELIVERY_FAILED:
        return True
    current_rank = MESSAGE_LIFECYCLE_ORDER.get(current)
    next_rank = MESSAGE_LIFECYCLE_ORDER.get(next_status)
    if current_rank is None or next_rank is None:
        return False
    return next_rank > current_rank


def solapi_delivery_status(status_code: str | None) -> MessageStatus | None:
    if status_code == "4000":
        return MessageStatus.DELIVERED
    if status_code in {"2000", "3000"}:
        return MessageStatus.SENT
    if status_code:
        return MessageStatus.DELIVERY_FAILED
    return None


def is_solapi_single_report_event(event: dict[str, object]) -> bool:
    has_correlation_key = bool(
        extract_solapi_message_log_id(event)
        or string_value(event.get("messageId"))
        or string_value(event.get("groupId"))
    )
    return has_correlation_key and bool(string_value(event.get("statusCode")))


def extract_solapi_message_log_id(event: dict[str, object]) -> str | None:
    custom_fields = event.get("customFields")
    if not isinstance(custom_fields, dict):
        return None
    return string_value(custom_fields.get(SOLAPI_MESSAGE_LOG_CUSTOM_FIELD))


def string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def read_solapi_error_body(exc: HTTPError) -> str:
    try:
        raw_body = exc.read().decode("utf-8", errors="replace")
    except (AttributeError, OSError, HttpClientException, UnicodeError):
        return ""
    if not raw_body:
        return ""
    try:
        decoded_payload = json.loads(raw_body)
    except JSONDecodeError:
        return raw_body[:500]
    if not isinstance(decoded_payload, dict):
        return raw_body[:500]

    for key in ("message", "errorMessage", "reason"):
        value = decoded_payload.get(key)
        if isinstance(value, str) and value:
            return value
    return raw_body[:500]


class MessageService:
    def __init__(self, db: Session, provider: MessageProvider | None = None) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.messages = MessageRepository(db)
        self.partners = PartnerRepository(db)
        self.photos = PhotoRepository(db)
        self.timeline = TimelineService(db)
        self.provider = provider or build_message_provider()

    def list_logs(self) -> list[MessageLogRead]:
        return [
            MessageLogRead.model_validate(log).model_copy(
                update={"order_customer_name": customer_name}
            )
            for log, customer_name in self.messages.list_messages_with_customer()
        ]

    def _lock_order_then_message(
        self,
        *,
        order_id: str,
        message_id: str,
    ) -> tuple[Order | None, MessageLog | None]:
        order = self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).scalar_one_or_none()
        log = self.db.execute(
            select(MessageLog)
            .where(MessageLog.id == message_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).scalar_one_or_none()
        return order, log

    def resolve_unknown_outcome(
        self,
        message_id: str,
        *,
        resolution: str,
        actor_user_id: str,
    ) -> MessageLog:
        order_id = self.db.scalar(select(MessageLog.order_id).where(MessageLog.id == message_id))
        if order_id is None:
            raise ValueError("message_not_found")
        order, log = self._lock_order_then_message(
            order_id=order_id,
            message_id=message_id,
        )
        if log is None:
            raise ValueError("message_not_found")
        if (
            log.provider != "solapi"
            or log.status != MessageStatus.PENDING
            or log.provider_error_code not in MESSAGE_PROVIDER_OUTCOME_UNKNOWN_ERROR_CODES
        ):
            raise ValueError("message_not_unknown_pending")

        if order is None:
            raise ValueError("order_not_found")

        now = datetime.now(UTC)
        if resolution == "confirmed_sent":
            log.status = MessageStatus.SENT
            log.error_message = None
            log.provider_error_code = "manually_confirmed_sent"
            log.provider_status_message = "operator confirmed sent in SOLAPI console"
            log.provider_reported_at = now
            log.sent_at = log.requested_at or now
            self._apply_confirmed_sent_log_side_effects(
                order,
                log,
                actor_user_id=actor_user_id,
            )
        elif resolution == "confirmed_not_sent":
            log.status = MessageStatus.FAILED
            log.error_message = "운영자가 SOLAPI 콘솔에서 미발송을 확인했습니다."
            log.provider_error_code = "manually_confirmed_not_sent"
            log.provider_status_message = "operator confirmed not sent in SOLAPI console"
            log.provider_reported_at = now
            log.sent_at = None
        else:
            raise ValueError("invalid_unknown_outcome_resolution")

        self.timeline.record(
            order_id=log.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.MESSAGE_SENT,
            title="SOLAPI 불명 결과 수동 확정",
            metadata={
                "message_log_id": log.id,
                "message_type": log.message_type,
                "resolution": resolution,
                "status": log.status,
            },
        )
        self.db.commit()
        self.db.refresh(log)
        return log

    def settings_status(self) -> MessageSettingsRead:
        provider = settings.message_provider.strip().lower() or "mock"
        credentials_configured = bool(settings.solapi_api_key and settings.solapi_api_secret)
        sender_configured = bool(normalize_phone(settings.solapi_sender_number))
        webhook_configured = bool(settings.solapi_webhook_secret)
        channel_id_configured = bool(get_solapi_kakao_sender_profile_id())
        template_status = {
            message_type.value: bool(getattr(settings, definition.template_id_setting, ""))
            for message_type, definition in KAKAO_TEMPLATE_DEFINITIONS.items()
        }
        solapi_ready = credentials_configured and sender_configured
        can_send_sms = provider != "solapi" or solapi_ready
        can_send_alimtalk = (
            provider == "solapi"
            and solapi_ready
            and channel_id_configured
            and all(template_status.values())
        )

        warnings: list[str] = []
        if provider == "mock":
            warnings.append("message_provider_mock")
        elif provider == "solapi":
            if not credentials_configured:
                warnings.append("solapi_missing_credentials")
            if not sender_configured:
                warnings.append("solapi_missing_sender_number")
            if not webhook_configured:
                warnings.append("solapi_missing_webhook_secret")
            if not channel_id_configured:
                warnings.append("solapi_missing_kakao_channel_id")
            missing_templates = [
                message_type
                for message_type, is_configured in template_status.items()
                if not is_configured
            ]
            if missing_templates:
                warnings.append("solapi_missing_kakao_template_ids")
        else:
            warnings.append("unsupported_message_provider")

        return MessageSettingsRead(
            provider=provider,
            kakao_channel_url=settings.kakao_channel_url.strip() or None,
            solapi_credentials_configured=credentials_configured,
            solapi_sender_configured=sender_configured,
            solapi_webhook_configured=webhook_configured,
            kakao_channel_id_configured=channel_id_configured,
            kakao_templates_configured=template_status,
            alimtalk_fallback_sms=settings.solapi_alimtalk_fallback_sms,
            can_send_sms=can_send_sms,
            can_send_alimtalk=can_send_alimtalk,
            warnings=warnings,
        )

    def send_automation_once(
        self,
        payload: MessageSendRequest,
        *,
        actor_user_id: str | None = None,
        successful_since: datetime | None = None,
        expected_scheduled_date: date | None = None,
    ) -> MessageLog | None:
        order = self.db.execute(
            select(Order)
            .where(
                Order.id == payload.order_id,
                Order.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        self._validate_message_preconditions(
            order,
            payload,
            expected_scheduled_date=expected_scheduled_date,
        )
        effective_successful_since = self._effective_successful_since(
            order,
            payload,
            successful_since,
        )

        pending_before = datetime.now(UTC) - timedelta(
            minutes=settings.message_pending_retry_after_minutes
        )
        recipient_partner_id = (
            order.partner_id if payload.recipient_type == RecipientType.PARTNER else None
        )
        marked_unknown_count = self.messages.mark_stale_solapi_pending_unknown(
            order_id=order.id,
            message_type=payload.message_type,
            pending_before=pending_before,
            recipient_partner_id=recipient_partner_id,
        )
        if marked_unknown_count:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MESSAGE_SENT,
                title="SOLAPI 발송 결과 확인 필요",
                description="중단된 발송의 수락 여부를 SOLAPI 콘솔에서 확인해야 합니다.",
                metadata={
                    "message_type": payload.message_type,
                    "unknown_pending_count": marked_unknown_count,
                    "pending_before": pending_before.isoformat(),
                    "automation_recovery": True,
                },
            )
        expired_count = self.messages.expire_stale_pending_attempts(
            order_id=order.id,
            message_type=payload.message_type,
            pending_before=pending_before,
            recipient_partner_id=recipient_partner_id,
        )
        if expired_count:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MESSAGE_SENT,
                title="멈춘 자동 메시지 재시도",
                description="응답이 없는 이전 자동 발송 시도를 실패 처리하고 다시 발송합니다.",
                metadata={
                    "message_type": payload.message_type,
                    "expired_pending_count": expired_count,
                    "pending_before": pending_before.isoformat(),
                    "automation_recovery": True,
                },
            )

        if self.messages.has_blocking_delivery_attempt(
            order_id=order.id,
            message_type=payload.message_type,
            retry_since=pending_before,
            successful_since=effective_successful_since,
            recipient_partner_id=recipient_partner_id,
        ):
            self.db.commit()
            return None

        return self.send(
            payload,
            actor_user_id=actor_user_id,
            expected_scheduled_date=expected_scheduled_date,
        )

    def _effective_successful_since(
        self,
        order: Order,
        payload: MessageSendRequest,
        successful_since: datetime | None,
    ) -> datetime | None:
        timestamps = [successful_since] if successful_since is not None else []
        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            partner_confirmed_at = self.timeline.latest_current_partner_confirmation(
                order_id=order.id,
                partner_id=order.partner_id,
            )
            if partner_confirmed_at is not None:
                timestamps.append(to_utc(partner_confirmed_at))
        return max(timestamps, default=None)

    def recover_workflow_notifications(self) -> NotificationRecoveryRunResult:
        orders = list(
            self.db.scalars(
                select(Order)
                .where(Order.deleted_at.is_(None))
                .order_by(Order.created_at.asc(), Order.id.asc())
            )
        )
        targets = [target for order in orders for target in self._workflow_recovery_targets(order)]
        sent = 0
        skipped = 0
        failed = 0
        for target in targets:
            try:
                log = self.send_automation_once(
                    MessageSendRequest(
                        order_id=target.order_id,
                        message_type=target.message_type,
                        recipient_type=target.recipient_type,
                    ),
                    successful_since=target.successful_since,
                    expected_scheduled_date=target.expected_scheduled_date,
                )
            except (RuntimeError, ValueError):
                self.db.rollback()
                failed += 1
                logger.exception(
                    "workflow_notification_recovery_failed",
                    extra={
                        "order_id": target.order_id,
                        "message_type": target.message_type,
                    },
                )
                continue

            if log is None:
                skipped += 1
            elif log.status in {MessageStatus.SENT, MessageStatus.DELIVERED}:
                sent += 1
            else:
                failed += 1

        return NotificationRecoveryRunResult(
            scanned_orders=len(orders),
            attempted=len(targets),
            sent=sent,
            skipped=skipped,
            failed=failed,
        )

    def _workflow_recovery_targets(self, order: Order) -> list[NotificationRecoveryTarget]:
        targets: list[NotificationRecoveryTarget] = []
        current_partner = self.partners.get(order.partner_id) if order.partner_id else None
        has_active_partner = bool(current_partner and current_partner.is_active)
        tomorrow = business_today() + timedelta(days=1)
        local_now = business_now()
        partner_confirmed_at = self.timeline.latest_current_partner_confirmation(
            order_id=order.id,
            partner_id=order.partner_id,
        )
        is_day_before_recovery_time = (
            local_now.hour,
            local_now.minute,
        ) >= (
            settings.automation_day_before_notice_hour,
            settings.automation_day_before_notice_minute,
        )
        if (
            settings.automation_day_before_notice_scheduler_enabled
            and is_day_before_recovery_time
            and order.scheduled_date == tomorrow
            and order.status in DAY_BEFORE_NOTICE_RECOVERY_STATUSES
            and partner_confirmed_at is not None
        ):
            targets.append(
                NotificationRecoveryTarget(
                    order_id=order.id,
                    message_type=MessageType.CUSTOMER_DAY_BEFORE,
                    recipient_type=RecipientType.CUSTOMER,
                    successful_since=business_day_start_utc(),
                    expected_scheduled_date=tomorrow,
                )
            )
        if (
            settings.automation_send_partner_assignment
            and has_active_partner
            and not order.as_intake_pending
            and not order.as_requested
            and order.status in PARTNER_ASSIGNMENT_RECOVERY_STATUSES
        ):
            partner_assigned_at = self.timeline.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.PARTNER_ASSIGNED,
            )
            if partner_assigned_at is not None:
                targets.append(
                    NotificationRecoveryTarget(
                        order_id=order.id,
                        message_type=MessageType.PARTNER_ASSIGNMENT,
                        recipient_type=RecipientType.PARTNER,
                        successful_since=partner_assigned_at,
                    )
                )

        if (
            settings.automation_send_schedule_confirmed
            and order.scheduled_date is not None
            and order.status in SCHEDULE_CONFIRMATION_RECOVERY_STATUSES
        ):
            if partner_confirmed_at is not None:
                targets.append(
                    NotificationRecoveryTarget(
                        order_id=order.id,
                        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                        recipient_type=RecipientType.CUSTOMER,
                        successful_since=partner_confirmed_at,
                    )
                )

        if order.as_requested and order.status != OrderStatus.CANCELLED:
            as_requested_at = self.timeline.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.AS_REQUESTED,
            )
            if as_requested_at is not None:
                partner_assigned_at = self.timeline.latest_created_at(
                    order_id=order.id,
                    event_type=TimelineEventType.PARTNER_ASSIGNED,
                )
                partner_as_since = max(
                    timestamp
                    for timestamp in (as_requested_at, partner_assigned_at)
                    if timestamp is not None
                )
                if has_active_partner:
                    targets.append(
                        NotificationRecoveryTarget(
                            order_id=order.id,
                            message_type=MessageType.PARTNER_AS_REQUEST,
                            recipient_type=RecipientType.PARTNER,
                            successful_since=partner_as_since,
                        ),
                    )
                targets.append(
                    NotificationRecoveryTarget(
                        order_id=order.id,
                        message_type=MessageType.CUSTOMER_AS_NOTICE,
                        recipient_type=RecipientType.CUSTOMER,
                        successful_since=as_requested_at,
                    )
                )

        if (
            settings.automation_send_customer_balance_due
            and order.work_completed_at is not None
            and order.status in BALANCE_NOTICE_ALLOWED_STATUSES
            and not order.as_intake_pending
            and not order.as_requested
            and has_customer_balance_due(order)
        ):
            targets.append(
                NotificationRecoveryTarget(
                    order_id=order.id,
                    message_type=MessageType.CUSTOMER_BALANCE_DUE,
                    recipient_type=RecipientType.CUSTOMER,
                    successful_since=order.work_completed_at,
                )
            )
        return targets

    def send_day_before_notices(
        self,
        *,
        target_date: date | None = None,
        actor_user_id: str | None = None,
    ) -> DayBeforeNoticeRunRead:
        notice_date = target_date or business_today() + timedelta(days=1)
        orders = self.orders.list_day_before_notice_candidates(
            target_date=notice_date,
            statuses=DAY_BEFORE_NOTICE_AUTOMATION_STATUSES,
        )
        order_ids = [order.id for order in orders]
        sent_order_ids: list[str] = []
        skipped_order_ids: list[str] = []
        failed_order_ids: list[str] = []
        retryable_order_ids: list[str] = []
        unconfirmed_order_ids: list[str] = []
        day_start = business_day_start_utc()

        for order_id in order_ids:
            order = self.orders.get(order_id)
            if order is None:
                failed_order_ids.append(order_id)
                continue
            if (
                self.timeline.latest_current_partner_confirmation(
                    order_id=order.id,
                    partner_id=order.partner_id,
                )
                is None
            ):
                unconfirmed_order_ids.append(order_id)
                continue
            payload = MessageSendRequest(
                order_id=order_id,
                message_type=MessageType.CUSTOMER_DAY_BEFORE,
                recipient_type=RecipientType.CUSTOMER,
            )
            try:
                log = self.send_automation_once(
                    payload,
                    actor_user_id=actor_user_id,
                    successful_since=day_start,
                    expected_scheduled_date=notice_date,
                )
            except ValueError:
                self.db.rollback()
                failed_order_ids.append(order_id)
                continue

            if log is None:
                skipped_order_ids.append(order_id)
                current_order = self.orders.get(order_id)
                sent_since = (
                    self._effective_successful_since(
                        current_order,
                        payload,
                        day_start,
                    )
                    if current_order is not None
                    else day_start
                )
                last_sent_at = self.messages.last_sent_at(
                    order_id=order_id,
                    message_type=MessageType.CUSTOMER_DAY_BEFORE,
                    sent_since=sent_since,
                )
                if last_sent_at:
                    if current_order is not None:
                        self._mark_day_before_notice_done(
                            current_order,
                            actor_user_id=actor_user_id,
                        )
                        self.db.commit()
                elif current_order is not None and not self.messages.has_unknown_delivery_outcome(
                    order_id=order_id,
                    message_type=MessageType.CUSTOMER_DAY_BEFORE,
                    attempted_since=sent_since,
                ):
                    retryable_order_ids.append(order_id)
                continue

            if log.status in {MessageStatus.SENT, MessageStatus.DELIVERED}:
                sent_order_ids.append(order_id)
            else:
                failed_order_ids.append(order_id)

        return DayBeforeNoticeRunRead(
            target_date=notice_date,
            scanned=len(order_ids),
            sent=len(sent_order_ids),
            skipped_already_sent=len(skipped_order_ids),
            skipped_unconfirmed=len(unconfirmed_order_ids),
            failed=len(failed_order_ids),
            retryable=len(retryable_order_ids),
            sent_order_ids=sent_order_ids,
            skipped_order_ids=skipped_order_ids,
            unconfirmed_order_ids=unconfirmed_order_ids,
            failed_order_ids=failed_order_ids,
            retryable_order_ids=retryable_order_ids,
        )

    def preview(self, payload: MessageSendRequest) -> MessagePreviewRead:
        payload = self._resolve_message_channel(payload)
        channel = payload.channel
        if channel is None:
            raise RuntimeError("message_channel_not_resolved")
        order = self.orders.get(payload.order_id)
        if order is None:
            raise ValueError("order_not_found")
        self._validate_message_preconditions(order, payload)

        recipient_type, recipient_name, recipient_phone = self._resolve_recipient(order, payload)
        partner = self.partners.get(order.partner_id) if order.partner_id else None
        customer_link = self._build_customer_link(order.customer_token)
        context = self._build_template_context(
            order,
            partner,
            customer_link,
        )
        content = self._render_content(
            payload,
            order=order,
            partner=partner,
            customer_link=customer_link,
        )
        kakao_template_id, kakao_variables = self._build_kakao_template(payload, context)
        kakao_preview_state = self._build_kakao_preview_state(payload, kakao_template_id)
        return MessagePreviewRead(
            order_id=order.id,
            message_type=payload.message_type,
            recipient_type=recipient_type,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            channel=channel,
            content=content,
            kakao_template_id=kakao_template_id,
            kakao_variables=kakao_variables,
            fallback_sms_content=(
                content
                if channel == MessageChannel.ALIMTALK and settings.solapi_alimtalk_fallback_sms
                else None
            ),
            **kakao_preview_state,
        )

    def send(
        self,
        payload: MessageSendRequest,
        *,
        actor_user_id: str | None = None,
        expected_scheduled_date: date | None = None,
    ) -> MessageLog:
        payload = self._resolve_message_channel(payload)
        channel = payload.channel
        if channel is None:
            raise RuntimeError("message_channel_not_resolved")
        order = self.db.execute(
            select(Order)
            .where(
                Order.id == payload.order_id,
                Order.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        ).scalar_one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        self._validate_message_preconditions(
            order,
            payload,
            expected_scheduled_date=expected_scheduled_date,
        )
        dispatch_scheduled_date = order.scheduled_date
        dispatch_requested_time = order.requested_time
        dispatch_partner_confirmed_at = (
            self.timeline.latest_current_partner_confirmation(
                order_id=order.id,
                partner_id=order.partner_id,
            )
            if payload.message_type
            in {
                MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                MessageType.CUSTOMER_DAY_BEFORE,
            }
            else None
        )

        recipient_type, recipient_name, recipient_phone = self._resolve_recipient(order, payload)
        partner = self.partners.get(order.partner_id) if order.partner_id else None
        # 협력사 수신 메시지는 발송 시점의 배정 협력사를 식별자로 박아둔다(전화번호 비의존).
        recipient_partner_id = order.partner_id if recipient_type == RecipientType.PARTNER else None
        current_message_epoch = self._current_message_epoch(order, payload)
        pending_before = datetime.now(UTC) - timedelta(
            minutes=settings.message_pending_retry_after_minutes
        )
        marked_unknown_count = self.messages.mark_stale_solapi_pending_unknown(
            order_id=order.id,
            message_type=payload.message_type,
            pending_before=pending_before,
            recipient_partner_id=recipient_partner_id,
        )
        if marked_unknown_count:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MESSAGE_SENT,
                title="SOLAPI 발송 결과 확인 필요",
                description="중단된 발송의 수락 여부를 SOLAPI 콘솔에서 확인해야 합니다.",
                metadata={
                    "message_type": payload.message_type,
                    "unknown_pending_count": marked_unknown_count,
                    "pending_before": pending_before.isoformat(),
                },
            )
        if self.messages.has_unknown_delivery_outcome(
            order_id=order.id,
            message_type=payload.message_type,
            attempted_since=current_message_epoch,
            recipient_partner_id=recipient_partner_id,
        ):
            self.db.commit()
            raise ValueError("message_outcome_unknown")
        expired_pending_count = self.messages.expire_stale_pending_attempts(
            order_id=order.id,
            message_type=payload.message_type,
            pending_before=pending_before,
            recipient_partner_id=recipient_partner_id,
        )
        if expired_pending_count:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MESSAGE_SENT,
                title="멈춘 메시지 발송 만료",
                metadata={
                    "message_type": payload.message_type,
                    "expired_pending_count": expired_pending_count,
                },
            )
        if self.messages.has_pending_delivery_attempt(
            order_id=order.id,
            message_type=payload.message_type,
            attempted_since=current_message_epoch,
            recipient_partner_id=recipient_partner_id,
        ):
            raise ValueError("message_send_in_progress")

        # FIX 1: 수신자 전화번호가 비어 있으면 IntegrityError(500) 대신
        # FAILED 로그 + timeline 을 남기고 깨끗한 실패 결과를 반환한다.
        if not normalize_phone(recipient_phone):
            return self._record_presend_failure(
                payload,
                recipient_type=recipient_type,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                recipient_partner_id=recipient_partner_id,
                error_code="recipient_phone_missing",
                error_message="수신자 전화번호가 없어 메시지를 발송할 수 없습니다.",
                actor_user_id=actor_user_id,
            )

        # FIX 6: 고객 링크가 포함되는 고객 메시지인데 customer_token 이 없으면
        # '.../c/None' 같은 죽은 링크를 보내지 않고 발송 실패로 기록한다.
        if (
            payload.message_type in MESSAGE_TYPES_WITH_CUSTOMER_LINK
            and not (order.customer_token or "").strip()
        ):
            return self._record_presend_failure(
                payload,
                recipient_type=recipient_type,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                recipient_partner_id=recipient_partner_id,
                error_code="customer_token_missing",
                error_message="고객 링크 토큰이 없어 메시지를 발송할 수 없습니다.",
                actor_user_id=actor_user_id,
            )

        customer_link = self._build_customer_link(order.customer_token)
        context = self._build_template_context(
            order,
            partner,
            customer_link,
        )
        content = self._render_content(
            payload,
            order=order,
            partner=partner,
            customer_link=customer_link,
        )
        kakao_template_id, kakao_variables = self._build_kakao_template(payload, context)
        message_log_id = str(uuid4())
        provider_input = MessageProviderSendInput(
            content=content,
            recipient_phone=recipient_phone,
            channel=channel,
            message_type=payload.message_type,
            kakao_template_id=kakao_template_id,
            kakao_variables=kakao_variables,
            fallback_sms_content=(
                content
                if channel == MessageChannel.ALIMTALK and settings.solapi_alimtalk_fallback_sms
                else None
            ),
            message_log_id=message_log_id,
        )
        requested_at = datetime.now(UTC)
        provider_name = getattr(self.provider, "provider_name", "unknown")

        log = MessageLog(
            id=message_log_id,
            order_id=payload.order_id,
            recipient_type=recipient_type,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            recipient_partner_id=recipient_partner_id,
            message_type=payload.message_type,
            channel=channel,
            content=content,
            status=MessageStatus.PENDING,
            error_message=None,
            provider=provider_name,
            provider_message_id=None,
            provider_group_id=None,
            provider_error_code=None,
            provider_status_code=None,
            provider_status_message=None,
            provider_response=None,
            requested_at=requested_at,
            provider_reported_at=None,
            sent_at=None,
            delivered_at=None,
        )
        self.messages.add(log)
        self.db.commit()
        self.db.refresh(log)

        result = self._send_with_provider(provider_input)
        provider_name = result.provider or provider_name
        actual_channel = result.channel or channel
        current_order, locked_log = self._lock_order_then_message(
            order_id=payload.order_id,
            message_id=log.id,
        )
        if locked_log is None:
            raise RuntimeError("message_log_missing_after_provider_send")
        log = locked_log
        should_apply_provider_side_effects = log.status == MessageStatus.PENDING
        self._apply_provider_result(
            log,
            result,
            provider_name=provider_name,
            actual_channel=actual_channel,
            requested_at=requested_at,
        )
        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.MESSAGE_SENT,
            title="메시지 발송",
            description=self._message_sent_description(
                payload.message_type,
                MessageStatus(log.status),
            ),
            metadata={
                "message_log_id": log.id,
                "message_type": payload.message_type,
                "recipient_type": recipient_type,
                "status": log.status,
                "provider": provider_name,
                "provider_group_id": log.provider_group_id,
                "provider_error_code": log.provider_error_code,
                "provider_status_code": log.provider_status_code,
            },
        )
        if (
            should_apply_provider_side_effects
            and log.status in {MessageStatus.SENT, MessageStatus.DELIVERED}
            and current_order is not None
        ):
            can_apply_workflow_transition = self._dispatch_snapshot_is_current(
                current_order,
                payload,
                log,
                dispatch_scheduled_date=dispatch_scheduled_date,
                dispatch_requested_time=dispatch_requested_time,
                dispatch_partner_confirmed_at=dispatch_partner_confirmed_at,
            )
            self._apply_sent_side_effects(
                current_order,
                payload,
                log,
                actor_user_id=actor_user_id,
                can_apply_workflow_transition=can_apply_workflow_transition,
            )

        self.db.commit()
        self.db.refresh(log)
        return log

    def _resolve_message_channel(self, payload: MessageSendRequest) -> MessageSendRequest:
        if payload.channel is not None:
            return payload
        return payload.model_copy(
            update={"channel": self._default_message_channel(payload.message_type)}
        )

    def _current_message_epoch(
        self,
        order: Order,
        payload: MessageSendRequest,
    ) -> datetime | None:
        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            return self.timeline.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.PARTNER_ASSIGNED,
            )
        if payload.message_type in {
            MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            MessageType.CUSTOMER_DAY_BEFORE,
        }:
            return self.timeline.latest_current_partner_confirmation(
                order_id=order.id,
                partner_id=order.partner_id,
            )
        if payload.message_type in {
            MessageType.PARTNER_AS_REQUEST,
            MessageType.CUSTOMER_AS_NOTICE,
        }:
            as_requested_at = self.timeline.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.AS_REQUESTED,
            )
            if payload.message_type == MessageType.PARTNER_AS_REQUEST:
                partner_assigned_at = self.timeline.latest_created_at(
                    order_id=order.id,
                    event_type=TimelineEventType.PARTNER_ASSIGNED,
                )
                return max(
                    (
                        timestamp
                        for timestamp in (as_requested_at, partner_assigned_at)
                        if timestamp
                    ),
                    default=None,
                )
            return as_requested_at
        if payload.message_type in {
            MessageType.CUSTOMER_BALANCE_DUE,
            MessageType.CUSTOMER_PHOTO_READY,
        }:
            return to_utc(order.work_completed_at) if order.work_completed_at else None
        return None

    def _validate_message_preconditions(
        self,
        order: Order,
        payload: MessageSendRequest,
        *,
        expected_scheduled_date: date | None = None,
    ) -> None:
        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            if (
                order.status not in PARTNER_ASSIGNMENT_RECOVERY_STATUSES
                or order.as_requested
                or order.as_intake_pending
            ):
                raise ValueError("partner_assignment_not_allowed")
        if payload.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED:
            partner_confirmed_at = self.timeline.latest_current_partner_confirmation(
                order_id=order.id,
                partner_id=order.partner_id,
            )
            if order.scheduled_date is None or partner_confirmed_at is None:
                raise ValueError("partner_confirmation_required")
            if (
                expected_scheduled_date is not None
                and order.scheduled_date != expected_scheduled_date
            ):
                raise ValueError("schedule_confirmation_target_changed")
            if order.status not in SCHEDULE_CONFIRMATION_RECOVERY_STATUSES:
                raise ValueError("schedule_confirmation_not_allowed")
        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            if (
                order.scheduled_date is None
                or order.status not in DAY_BEFORE_NOTICE_RECOVERY_STATUSES
            ):
                raise ValueError("day_before_notice_not_allowed")
            target_date = expected_scheduled_date or (business_today() + timedelta(days=1))
            if order.scheduled_date != target_date:
                if expected_scheduled_date is None:
                    raise ValueError("day_before_notice_not_due")
                raise ValueError("day_before_notice_target_changed")
            if (
                self.timeline.latest_current_partner_confirmation(
                    order_id=order.id,
                    partner_id=order.partner_id,
                )
                is None
            ):
                raise ValueError("partner_confirmation_required")
        if payload.message_type == MessageType.CUSTOMER_BALANCE_DUE:
            if (
                order.status not in BALANCE_NOTICE_ALLOWED_STATUSES
                or order.work_completed_at is None
                or order.as_intake_pending
                or order.as_requested
                or not has_customer_balance_due(order)
            ):
                raise ValueError("customer_balance_not_due")
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            if order.status != OrderStatus.CUSTOMER_DELIVERY_NEEDED:
                raise ValueError("customer_photo_ready_not_allowed")
            if self.photos.count_visible_for_order(order.id) == 0:
                raise ValueError("no_customer_visible_photos")
            evidence_created_after = self.timeline.latest_partner_work_epoch(
                order_id=order.id,
                partner_id=order.partner_id,
                work_completed_at=order.work_completed_at,
                work_is_active=False,
            )
            if not self.photos.has_customer_delivery_evidence(
                order.id,
                created_after=evidence_created_after,
            ):
                raise ValueError("customer_photo_evidence_incomplete")
        if (
            payload.message_type in {MessageType.PARTNER_AS_REQUEST, MessageType.CUSTOMER_AS_NOTICE}
            and not order.as_requested
        ):
            raise ValueError("as_request_required")

    def _default_message_channel(self, message_type: MessageType) -> MessageChannel:
        if message_type == MessageType.CUSTOMER_ACCESS_LINK:
            return MessageChannel.LMS
        if self._can_send_alimtalk_for(message_type):
            return MessageChannel.ALIMTALK
        return MessageChannel.SMS

    def _can_send_alimtalk_for(self, message_type: MessageType) -> bool:
        provider = settings.message_provider.strip().lower() or "mock"
        if provider != "solapi":
            return False
        if not (settings.solapi_api_key and settings.solapi_api_secret):
            return False
        if not normalize_phone(settings.solapi_sender_number):
            return False
        if not get_solapi_kakao_sender_profile_id():
            return False
        definition = get_kakao_template_definition(message_type)
        if definition is None:
            return False
        return bool(getattr(settings, definition.template_id_setting, ""))

    def _record_presend_failure(
        self,
        payload: MessageSendRequest,
        *,
        recipient_type: RecipientType,
        recipient_name: str | None,
        recipient_phone: str | None,
        recipient_partner_id: str | None,
        error_code: str,
        error_message: str,
        actor_user_id: str | None,
    ) -> MessageLog:
        """발송 전 검증 실패를 FAILED 로그 + timeline 으로 기록한다.

        recipient_name/recipient_phone 은 NOT NULL 컬럼이므로
        값이 없으면 안전한 placeholder('미상'/'')로 채워 IntegrityError 를 피한다.
        provider 실패와 동일한 timeline 경로(MESSAGE_SENT)를 사용해
        '실패는 반드시 로깅한다' 규칙을 만족시킨다.
        """
        requested_at = datetime.now(UTC)
        provider_name = getattr(self.provider, "provider_name", "unknown")

        log = MessageLog(
            id=str(uuid4()),
            order_id=payload.order_id,
            recipient_type=recipient_type,
            recipient_name=recipient_name or "미상",
            recipient_phone=recipient_phone or "",
            recipient_partner_id=recipient_partner_id,
            message_type=payload.message_type,
            channel=payload.channel,
            content="",
            status=MessageStatus.FAILED,
            error_message=error_message,
            provider=provider_name,
            provider_message_id=None,
            provider_group_id=None,
            provider_error_code=error_code,
            provider_status_code=None,
            provider_status_message=None,
            provider_response=None,
            requested_at=requested_at,
            provider_reported_at=None,
            sent_at=None,
            delivered_at=None,
        )
        self.messages.add(log)

        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.MESSAGE_SENT,
            title="메시지 발송",
            description=self._message_sent_description(payload.message_type, MessageStatus.FAILED),
            metadata={
                "message_log_id": log.id,
                "message_type": payload.message_type,
                "recipient_type": recipient_type,
                "status": MessageStatus.FAILED,
                "provider": provider_name,
                "provider_group_id": None,
                "provider_error_code": error_code,
                "provider_status_code": None,
            },
        )

        self.db.commit()
        self.db.refresh(log)
        return log

    def process_solapi_webhook_events(
        self,
        events: list[dict[str, object]],
    ) -> SolapiWebhookProcessResult:
        updated = 0
        ignored = 0
        unknown = 0
        resolved_events: list[tuple[str, str, dict[str, object]]] = []

        for event in events:
            if not is_solapi_single_report_event(event):
                ignored += 1
                continue

            log = self._find_solapi_log_for_event(event)
            if log is None:
                unknown += 1
                continue
            resolved_events.append((log.order_id, log.id, event))

        for order_id, message_id, event in sorted(
            resolved_events,
            key=lambda item: (item[0], item[1]),
        ):
            order, log = self._lock_order_then_message(
                order_id=order_id,
                message_id=message_id,
            )
            if log is None:
                unknown += 1
                continue
            self._apply_solapi_single_report(log, event, locked_order=order)
            updated += 1

        self.db.commit()
        return SolapiWebhookProcessResult(
            received=len(events),
            updated=updated,
            ignored=ignored,
            unknown=unknown,
        )

    def _send_with_provider(self, provider_input: MessageProviderSendInput) -> MessageSendResult:
        try:
            send_with_context: object = getattr(self.provider, "send_with_context", None)
            if callable(send_with_context):
                result = send_with_context(provider_input)
                if isinstance(result, MessageSendResult):
                    return result
                raise TypeError("provider_result_invalid")
            return self.provider.send(provider_input.content, provider_input.recipient_phone)
        except Exception as exc:
            logger.exception("Message provider raised an exception")
            provider_name = getattr(self.provider, "provider_name", "unknown")
            if provider_name == "solapi":
                return solapi_unknown_outcome(
                    channel=provider_input.channel,
                    error_message="solapi_outcome_unknown",
                    error_code="solapi_outcome_unknown",
                )
            return MessageSendResult(
                status=MessageStatus.FAILED,
                error_message=f"provider_exception: {exc}",
                channel=provider_input.channel,
                provider=provider_name,
                provider_error_code="provider_exception",
            )

    def _apply_provider_result(
        self,
        log: MessageLog,
        result: MessageSendResult,
        *,
        provider_name: str,
        actual_channel: MessageChannel,
        requested_at: datetime,
    ) -> None:
        if log.status != MessageStatus.PENDING:
            # SOLAPI가 API 응답보다 빠르게 웹훅을 보낼 수 있다. 그 사이 웹훅이
            # 상태를 확정했다면 늦은 요청 응답으로 배송 수명주기를 후퇴시키지 않는다.
            log.channel = actual_channel
            log.provider = provider_name
            log.provider_message_id = log.provider_message_id or result.provider_message_id
            log.provider_group_id = log.provider_group_id or result.provider_group_id
            return
        log.channel = actual_channel
        log.status = result.status
        log.error_message = result.error_message
        log.provider = provider_name
        log.provider_message_id = result.provider_message_id
        log.provider_group_id = result.provider_group_id
        log.provider_error_code = result.provider_error_code
        log.provider_status_code = result.provider_status_code
        log.provider_status_message = result.provider_status_message
        log.provider_response = result.provider_response
        log.provider_reported_at = result.provider_reported_at
        log.sent_at = requested_at if result.status == MessageStatus.SENT else None
        log.delivered_at = result.delivered_at

    def _find_solapi_log_for_event(self, event: dict[str, object]) -> MessageLog | None:
        message_log_id = extract_solapi_message_log_id(event)
        if message_log_id:
            log = self.messages.get(message_log_id)
            if log is not None and log.provider == "solapi":
                return log

        message_id = string_value(event.get("messageId"))
        if message_id:
            log = self.messages.find_by_provider_message_id("solapi", message_id)
            if log is not None:
                return log

        group_id = string_value(event.get("groupId"))
        if not group_id:
            return None

        logs = self.messages.find_by_provider_group_id("solapi", group_id)
        if len(logs) == 1:
            return logs[0]
        return None

    def _apply_solapi_single_report(
        self,
        log: MessageLog,
        event: dict[str, object],
        *,
        locked_order: Order | None,
    ) -> None:
        old_status = log.status
        status_code = string_value(event.get("statusCode"))
        status_message = string_value(event.get("statusMessage"))
        next_status = solapi_delivery_status(status_code)
        reported_at = (
            parse_solapi_datetime(event.get("dateReported"))
            or parse_solapi_datetime(event.get("dateProcessed"))
            or datetime.now(UTC)
        )
        received_at = parse_solapi_datetime(event.get("dateReceived"))
        if log.provider_reported_at is not None and reported_at <= to_utc(log.provider_reported_at):
            return

        # 상태 전이가 수명주기를 전진시킬 때만 status 를 갱신한다.
        # 순서가 뒤바뀐 리포트(DELIVERED → SENT)나 동일 상태 재수신은 무시하여
        # 상태 후퇴와 timeline 이벤트 중복 발행을 막는다.
        # provider 메타데이터는 최신 리포트로 갱신하되, status 후퇴는 막는다.
        log.provider = "solapi"
        log.provider_message_id = string_value(event.get("messageId")) or log.provider_message_id
        log.provider_group_id = string_value(event.get("groupId")) or log.provider_group_id
        log.provider_status_code = status_code
        log.provider_status_message = status_message
        log.provider_reported_at = reported_at
        log.provider_response = event

        if next_status is None or not is_monotonic_delivery_transition(
            old_status,
            next_status,
        ):
            return

        log.status = next_status

        if next_status == MessageStatus.DELIVERED:
            log.delivered_at = received_at or reported_at
            log.error_message = None
            log.provider_error_code = None
        elif next_status == MessageStatus.SENT:
            log.error_message = None
            log.provider_error_code = None
        elif next_status == MessageStatus.DELIVERY_FAILED:
            log.error_message = status_message or f"solapi_delivery_failed: {status_code}"
            log.provider_error_code = status_code or "solapi_delivery_failed"

        if next_status in {MessageStatus.SENT, MessageStatus.DELIVERED} and old_status not in {
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
        }:
            log.sent_at = log.sent_at or log.requested_at or reported_at
            if locked_order is not None:
                self._apply_confirmed_sent_log_side_effects(
                    locked_order,
                    log,
                    actor_user_id=None,
                )

        if old_status != next_status:
            self._record_delivery_status_event(
                log,
                status=next_status,
                status_code=status_code,
                status_message=status_message,
            )

    def _resolve_recipient(
        self, order: Order, payload: MessageSendRequest
    ) -> tuple[RecipientType, str, str]:
        if payload.message_type in {
            MessageType.PARTNER_ASSIGNMENT,
            MessageType.PARTNER_CUSTOMER_INFO,
            MessageType.PARTNER_AS_REQUEST,
        }:
            if not order.partner_id:
                raise ValueError("partner_not_assigned")
            partner = self.db.execute(
                select(Partner)
                .where(
                    Partner.id == order.partner_id,
                    Partner.is_active.is_(True),
                )
                .execution_options(populate_existing=True)
            ).scalar_one_or_none()
            if partner is None:
                raise ValueError("partner_not_found")
            recipient_phone = partner.manager_phone or partner.phone
            return (
                RecipientType.PARTNER,
                partner.manager_name or partner.name or "",
                recipient_phone or "",
            )

        if payload.recipient_type != RecipientType.CUSTOMER:
            raise ValueError("invalid_recipient_type")
        return RecipientType.CUSTOMER, order.customer_name or "", order.customer_phone or ""

    def _dispatch_snapshot_is_current(
        self,
        order: Order,
        payload: MessageSendRequest,
        log: MessageLog,
        *,
        dispatch_scheduled_date: date | None,
        dispatch_requested_time: str | None,
        dispatch_partner_confirmed_at: datetime | None,
    ) -> bool:
        if order.deleted_at is not None:
            return False
        if (
            log.recipient_type == RecipientType.PARTNER
            and log.recipient_partner_id != order.partner_id
        ):
            return False
        expected_scheduled_date = (
            dispatch_scheduled_date
            if payload.message_type
            in {
                MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                MessageType.CUSTOMER_DAY_BEFORE,
            }
            else None
        )
        if expected_scheduled_date is not None and order.requested_time != dispatch_requested_time:
            return False
        try:
            self._validate_message_preconditions(
                order,
                payload,
                expected_scheduled_date=expected_scheduled_date,
            )
        except ValueError:
            return False
        if payload.message_type not in {
            MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            MessageType.CUSTOMER_DAY_BEFORE,
        }:
            return True
        current_partner_confirmed_at = self.timeline.latest_current_partner_confirmation(
            order_id=order.id,
            partner_id=order.partner_id,
        )
        if dispatch_partner_confirmed_at is None or current_partner_confirmed_at is None:
            return dispatch_partner_confirmed_at is current_partner_confirmed_at
        return to_utc(dispatch_partner_confirmed_at) == to_utc(current_partner_confirmed_at)

    def _apply_confirmed_sent_log_side_effects(
        self,
        order: Order,
        log: MessageLog,
        *,
        actor_user_id: str | None,
    ) -> None:
        payload = MessageSendRequest(
            order_id=log.order_id,
            message_type=log.message_type,
            recipient_type=log.recipient_type,
            channel=log.channel,
        )
        attempted_at = to_utc(log.requested_at or log.created_at)
        current_epoch = self._current_message_epoch(order, payload)
        is_current_epoch = current_epoch is None or attempted_at >= to_utc(current_epoch)
        is_current_partner = (
            log.recipient_type != RecipientType.PARTNER
            or log.recipient_partner_id == order.partner_id
        )
        can_apply_workflow_transition = (
            order.deleted_at is None and is_current_epoch and is_current_partner
        )
        if can_apply_workflow_transition:
            try:
                expected_scheduled_date = None
                if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
                    expected_scheduled_date = to_business_time(
                        log.requested_at or log.created_at
                    ).date() + timedelta(days=1)
                self._validate_message_preconditions(
                    order,
                    payload,
                    expected_scheduled_date=expected_scheduled_date,
                )
            except ValueError:
                can_apply_workflow_transition = False
        self._apply_sent_side_effects(
            order,
            payload,
            log,
            actor_user_id=actor_user_id,
            can_apply_workflow_transition=can_apply_workflow_transition,
        )

    def _apply_sent_side_effects(
        self,
        order: Order,
        payload: MessageSendRequest,
        log: MessageLog,
        *,
        actor_user_id: str | None,
        can_apply_workflow_transition: bool,
    ) -> None:
        if payload.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED:
            if can_apply_workflow_transition:
                self._advance_status(
                    order,
                    OrderStatus.SCHEDULE_CONFIRMED,
                    actor_user_id=actor_user_id,
                    title="일정확정 안내 완료",
                    description="고객에게 일정확정 안내를 발송했습니다.",
                )
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            if can_apply_workflow_transition:
                self._mark_day_before_notice_done(order, actor_user_id=actor_user_id)
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            if can_apply_workflow_transition:
                self._advance_status(
                    order,
                    OrderStatus.PARTNER_CONFIRMING,
                    actor_user_id=actor_user_id,
                    title="협력사 배정 안내 완료",
                    description="협력사에게 작업 배정 안내를 발송했습니다.",
                )
            return

        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            # 정책 변경(2026-05-18): 사진 링크 발송은 메시지/timeline만 남기고
            # 주문 상태는 자동 advance 하지 않는다. 재전송 가능성을 보장하기 위함.
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_BALANCE_DUE:
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_AS_NOTICE:
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_ACCESS_LINK:
            self._record_customer_link_sent(order, log, actor_user_id=actor_user_id)
            return

        if payload.message_type == MessageType.CUSTOMER_QUOTE:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.QUOTE_SENT,
                title="견적서 발송",
                metadata={"message_log_id": log.id, "channel": log.channel},
            )
            return

        if payload.message_type == MessageType.PARTNER_CUSTOMER_INFO:
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_UNPAID_NOTICE_SENT,
                title="협력사 고객정보 전송",
                metadata={"message_log_id": log.id, "channel": log.channel},
            )
            return

    def _mark_day_before_notice_done(
        self,
        order: Order,
        *,
        actor_user_id: str | None,
    ) -> None:
        if order.status == OrderStatus.DAY_BEFORE_NOTICE_DONE:
            return
        if order.status not in DAY_BEFORE_NOTICE_AUTOMATION_STATUSES:
            return
        if not should_advance_status(order.status, OrderStatus.DAY_BEFORE_NOTICE_DONE):
            return
        old_status = order.status
        order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.STATUS_CHANGED,
            title="전날 안내 완료",
            description="고객에게 방문 전날 안내를 발송했습니다.",
            metadata={"from": old_status, "to": order.status},
        )

    def _advance_status(
        self,
        order: Order,
        next_status: OrderStatus,
        *,
        actor_user_id: str | None,
        title: str,
        description: str,
    ) -> None:
        old_status = order.status
        if not should_advance_status(old_status, next_status):
            return
        order.status = next_status
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.STATUS_CHANGED,
            title=title,
            description=description,
            metadata={"from": old_status, "to": order.status},
        )

    def _record_customer_link_sent(
        self,
        order: Order,
        log: MessageLog,
        *,
        actor_user_id: str | None,
    ) -> None:
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.CUSTOMER_LINK_SENT,
            title="고객 링크 발송",
            metadata={"message_log_id": log.id, "channel": log.channel},
        )

    def _record_delivery_status_event(
        self,
        log: MessageLog,
        *,
        status: MessageStatus,
        status_code: str | None,
        status_message: str | None,
    ) -> None:
        title = (
            "메시지 배송 실패" if status == MessageStatus.DELIVERY_FAILED else "메시지 배송 완료"
        )
        self.timeline.record(
            order_id=log.order_id,
            actor_user_id=None,
            event_type=TimelineEventType.MESSAGE_SENT,
            title=title,
            description=status_message,
            metadata={
                "message_log_id": log.id,
                "message_type": log.message_type,
                "recipient_type": log.recipient_type,
                "status": status,
                "provider": "solapi",
                "provider_status_code": status_code,
                "provider_status_message": status_message,
            },
        )

    def _build_template_context(
        self,
        order: Order,
        partner: Partner | None,
        customer_link: str,
    ) -> dict[str, object]:
        partner_login_link = self._build_partner_login_link(order.id)
        schedule_amount = (
            format_money(order_consumer_total(order)) if order.customer_visible_payment else "-"
        )
        schedule_deposit = (
            format_money(order.deposit_amount) if order.customer_visible_payment else "-"
        )
        schedule_balance = (
            format_money(customer_balance_due_amount(order))
            if order.customer_visible_payment
            else "-"
        )
        schedule_total = format_money(order.total_amount) if order.customer_visible_payment else "-"
        return {
            "customer_name": order.customer_name,
            "service_name": format_service_name(order),
            "size_or_quantity": order.size_or_quantity or "-",
            "schedule": format_schedule(order),
            "customer_address": order.customer_address,
            "customer_link": customer_link,
            # 사진/전날/잔금 알림톡의 고객링크는 '버튼 웹링크' 변수(#{고객링크})다. 버튼 URL은
            # 템플릿에 `https://#{고객링크}` 로 등록돼 프로토콜이 고정영역이므로, 변수값에는
            # scheme(https://)을 빼고 도메인+경로만 넣어야 이중 프로토콜이 되지 않는다.
            "customer_link_button": customer_link.split("://", 1)[-1],
            "partner_name": partner.name if partner else "",
            "partner_manager_name": partner.manager_name or partner.name if partner else "",
            "special_request": order.special_request or "-",
            "as_memo": order.as_memo or "-",
            "consumer_price": format_money(order_consumer_total(order)),
            "discount_amount": format_money(order.discount_amount),
            "total_amount": format_money(order.total_amount),
            "deposit_amount": format_money(order.deposit_amount),
            "balance_amount": format_money(customer_balance_due_amount(order)),
            "schedule_consumer_price": schedule_amount,
            "schedule_deposit_amount": schedule_deposit,
            "schedule_balance_amount": schedule_balance,
            "schedule_total_amount": schedule_total,
            "vat_label": format_vat_label(order.vat_type),
            "company_name": settings.app_name,
            "masked_customer_phone": mask_phone_last4(order.customer_phone),
            # SOLAPI 클린잡 템플릿 변수용: #{연락처}(고객 실번호 — 협력사가
            # 연락/고객 본인 확인), #{대수}는 별도 값이 없어 "-"로 채운다.
            "customer_phone": order.customer_phone or "-",
            "customer_phone_without_auth_suffix": mask_customer_phone_auth_suffix(
                order.customer_phone
            ),
            "unit_count": "-",
            "partner_login_link": partner_login_link,
            "partner_login_link_button": partner_login_link.split("://", 1)[-1],
        }

    def _build_kakao_template(
        self,
        payload: MessageSendRequest,
        context: dict[str, object],
    ) -> tuple[str | None, dict[str, str] | None]:
        if payload.channel != MessageChannel.ALIMTALK:
            return None, None

        definition = get_kakao_template_definition(payload.message_type)
        if definition is None:
            return None, None

        template_id = getattr(settings, definition.template_id_setting, "")
        return template_id or None, render_kakao_variables(definition, context)

    def _build_kakao_preview_state(
        self,
        payload: MessageSendRequest,
        kakao_template_id: str | None,
    ) -> KakaoPreviewState:
        if payload.channel != MessageChannel.ALIMTALK:
            return {
                "kakao_channel_id_configured": False,
                "kakao_template_configured": False,
                "fallback_sms_enabled": False,
                "can_send": True,
                "warnings": [],
            }

        has_channel_id = bool(get_solapi_kakao_sender_profile_id())
        has_template_id = bool(kakao_template_id)
        fallback_sms_enabled = settings.solapi_alimtalk_fallback_sms
        warnings: list[str] = []

        if not has_channel_id:
            warnings.append("solapi_missing_kakao_channel_id")
        if not has_template_id:
            warnings.append("solapi_missing_kakao_template_id")
        if warnings and fallback_sms_enabled:
            warnings.append("alimtalk_fallback_sms_enabled")

        return {
            "kakao_channel_id_configured": has_channel_id,
            "kakao_template_configured": has_template_id,
            "fallback_sms_enabled": fallback_sms_enabled,
            "can_send": (has_channel_id and has_template_id) or fallback_sms_enabled,
            "warnings": warnings,
        }

    def _render_content(
        self,
        payload: MessageSendRequest,
        *,
        order: Order,
        partner: Partner | None,
        customer_link: str,
    ) -> str:
        schedule = format_schedule(order)
        if payload.message_type == MessageType.CUSTOMER_PHOTO_READY:
            return (
                f"[클린잡] {order.customer_name}님, {order.service_name} 작업 사진 "
                "확인이 준비되었습니다.\n"
                f"아래 링크에서 연락처 뒷자리 인증 후 확인해주세요.\n{customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_ACCESS_LINK:
            return (
                f"[클린잡] {order.customer_name}님, 예약·작업 내역 확인 링크입니다.\n"
                f"연락처 뒷자리 인증 후 확인해주세요.\n{customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_BALANCE_DUE:
            return (
                f"[클린잡] {order.customer_name}님, {format_service_name(order)} "
                "작업이 완료되었습니다.\n"
                f"잔금: {format_money(customer_balance_due_amount(order))}\n"
                f"결제 및 작업 내역 확인: {customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_AS_NOTICE:
            as_memo = truncate_sms_section(order.as_memo or payload.memo or "")
            return (
                f"[클린잡] {order.customer_name}님, AS 요청이 접수되었습니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"방문: {schedule}\n"
                f"AS 내용: {as_memo or '-'}\n"
                f"진행 상황 확인: {customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED:
            return (
                f"[클린잡] {order.customer_name}님, 예약 일정이 확정되었습니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"방문: {schedule}\n"
                f"주소: {order.customer_address}\n"
                f"예약 확인: {customer_link}"
            )
        if payload.message_type == MessageType.CUSTOMER_DAY_BEFORE:
            return (
                "[클린잡] 내일 방문 예정 안내드립니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"방문: {schedule}\n"
                f"요청사항과 안내는 아래 링크에서 확인해주세요.\n{customer_link}"
            )
        if payload.message_type == MessageType.PARTNER_ASSIGNMENT:
            partner_name = partner.name if partner else "협력사"
            return (
                f"[클린잡] {partner_name}에 신규 작업이 배정되었습니다.\n"
                f"방문: {schedule}\n"
                f"서비스: {format_service_name(order)}\n"
                f"고객: {order.customer_name}\n"
                f"주소: {order.customer_address}\n"
                f"요청사항: {order.special_request or '-'}\n"
                f"작업 일정 확인: {self._build_partner_login_link(order.id)}"
            )
        if payload.message_type == MessageType.CUSTOMER_QUOTE:
            return (
                f"[클린잡] {order.customer_name}님 견적 안내드립니다.\n"
                f"서비스: {format_service_name(order)}\n"
                f"소비자가(VAT {format_vat_label(order.vat_type)}): "
                f"{format_money(order_consumer_total(order))}\n"
                f"할인가: {format_money(order.discount_amount)}\n"
                f"계약금: {format_money(order.deposit_amount)} / "
                f"잔금: {format_money(order.balance_amount)}\n"
                f"방문: {schedule}"
            )
        if payload.message_type == MessageType.PARTNER_CUSTOMER_INFO:
            partner_name = partner.manager_name or partner.name if partner else "협력사"
            # 미입금 고객정보 안내는 협력사가 고객에게 직접 연락(미수금 회수)해야 하므로
            # 고객 실번호를 그대로 전달한다(알림톡 #{연락처} 변수와 동일 기준).
            return (
                f"[클린잡] {partner_name}님, 미입금 고객 정보를 전달드립니다.\n"
                f"고객: {order.customer_name} ({order.customer_phone or '-'})\n"
                f"방문: {schedule}\n"
                f"주소: {order.customer_address}\n"
                f"요청사항: {order.special_request or '-'}"
            )
        if payload.message_type == MessageType.PARTNER_AS_REQUEST:
            partner_name = partner.manager_name or partner.name if partner else "협력사"
            as_memo = truncate_sms_section(order.as_memo or payload.memo or "")
            # 미입금 고객정보 안내와 동일 기준: 협력사가 고객에게 직접 재방문 일정을 조율해야 하므로
            # 고객 실번호를 그대로 전달한다. 운영자 결정(2026-07-03).
            return (
                f"[클린잡] {partner_name}님, AS(재작업) 요청이 접수되었습니다.\n"
                f"고객: {order.customer_name} ({order.customer_phone or '-'})\n"
                f"방문지: {order.customer_address}\n"
                f"AS 내용: {as_memo or '-'}\n"
                f"작업 확인: {self._build_partner_login_link(order.id)}"
            )
        return f"[클린잡] {payload.message_type.value}: {format_service_name(order)}"

    def _build_customer_link(self, customer_token: str | None) -> str:
        encoded_token = quote(customer_token or "", safe="")
        return f"{settings.frontend_url.rstrip('/')}/c#token={encoded_token}"

    def _build_partner_login_link(self, order_id: str | None = None) -> str:
        base = f"{settings.frontend_url.rstrip('/')}/partner"
        if not order_id:
            return base
        return f"{base}?job={quote(order_id, safe='')}"

    def _message_sent_description(self, message_type: MessageType, status: MessageStatus) -> str:
        label = {
            MessageType.CUSTOMER_SCHEDULE_CONFIRMED: "고객 일정확정 안내",
            MessageType.CUSTOMER_DAY_BEFORE: "고객 전날 안내",
            MessageType.PARTNER_ASSIGNMENT: "협력사 배정 안내",
            MessageType.CUSTOMER_PHOTO_READY: "고객 사진 확인 안내",
            MessageType.CUSTOMER_BALANCE_DUE: "고객 잔금 안내",
            MessageType.CUSTOMER_QUOTE: "고객 견적서",
            MessageType.PARTNER_CUSTOMER_INFO: "협력사 고객정보",
            MessageType.PARTNER_AS_REQUEST: "협력사 AS 요청",
            MessageType.CUSTOMER_AS_NOTICE: "고객 AS 안내",
            MessageType.CUSTOMER_ACCESS_LINK: "고객 접속 링크",
        }.get(message_type, message_type.value)
        return f"{label} 발송 결과: {status.value}"


STATUS_ORDER: dict[OrderStatus, int] = {
    OrderStatus.NEW: 10,
    OrderStatus.CONSULTING: 20,
    OrderStatus.PARTNER_CONFIRMING: 30,
    OrderStatus.SCHEDULE_CONFIRMED: 40,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED: 50,
    OrderStatus.DAY_BEFORE_NOTICE_DONE: 60,
    OrderStatus.SCHEDULED: 70,
    OrderStatus.IN_PROGRESS: 80,
    OrderStatus.PHOTO_REVIEW_PENDING: 90,
    OrderStatus.CUSTOMER_DELIVERY_NEEDED: 100,
    OrderStatus.CUSTOMER_DELIVERY_DONE: 110,
    # 컴플레인/미수금으로 막힌 보류 상태. 최종결제완료(120) 직전이지만 자동 전진 대상은 아니다.
    OrderStatus.CUSTOMER_CHECK_NEEDED: 115,
    OrderStatus.COMPLETED: 120,
    OrderStatus.CANCELLED: 999,
}


def should_advance_status(current: OrderStatus, next_status: OrderStatus) -> bool:
    if current == next_status or current == OrderStatus.CANCELLED:
        return False
    # 신규 상태가 STATUS_ORDER 에 누락돼도 KeyError 로 발송 후처리가 깨지지 않도록 방어한다.
    # (순위를 모르는 상태에서는 자동 전진을 하지 않는다 = 안전한 기본값.)
    current_rank = STATUS_ORDER.get(current)
    next_rank = STATUS_ORDER.get(next_status)
    if current_rank is None or next_rank is None:
        return False
    return current_rank < next_rank


def format_service_name(order: Order) -> str:
    if order.size_or_quantity:
        return f"{order.service_name} ({order.size_or_quantity})"
    return order.service_name


def get_solapi_kakao_sender_profile_id() -> str:
    return settings.solapi_kakao_pf_id.strip() or settings.solapi_kakao_channel_id.strip()


def mask_customer_phone_auth_suffix(phone: str | None) -> str:
    normalized = normalize_phone(phone or "")
    if len(normalized) < 3:
        return "-"
    return f"{normalized[:3]}-****-****"


def business_day_start_utc() -> datetime:
    local_start = datetime.combine(
        business_today(),
        time.min,
        tzinfo=ZoneInfo(settings.business_timezone),
    )
    return local_start.astimezone(UTC)


def format_schedule(order: Order) -> str:
    date_text = order.scheduled_date.isoformat() if order.scheduled_date else "일정 미정"
    if order.requested_time:
        return f"{date_text} {order.requested_time}"
    return date_text


def truncate_sms_section(value: str, *, max_bytes: int = 1000) -> str:
    normalized = value.strip()
    encoded = normalized.encode("utf-8")
    if len(encoded) <= max_bytes:
        return normalized
    suffix = "…(전체 내용은 시스템에서 확인)"
    byte_budget = max(max_bytes - len(suffix.encode("utf-8")), 0)
    prefix = encoded[:byte_budget].decode("utf-8", errors="ignore").rstrip()
    return f"{prefix}{suffix}"


def format_money(value: object) -> str:
    amount = int(Decimal(str(value or 0)))
    return f"{amount:,}원"


def customer_balance_due_amount(order: Order) -> Decimal:
    if order.balance_amount is not None:
        return Decimal(str(order.balance_amount))
    total = order_consumer_total(order)
    deposit = Decimal(str(order.deposit_amount or 0))
    return max(total - deposit, Decimal("0"))


def has_customer_balance_due(order: Order) -> bool:
    if order.payment_status in {PaymentStatus.PAID, PaymentStatus.REFUNDED}:
        return False
    return has_positive_amount(customer_balance_due_amount(order))


def has_positive_amount(value: object) -> bool:
    try:
        return Decimal(str(value or 0)) > 0
    except (ValueError, TypeError):
        return False


def format_vat_label(value: object) -> str:
    return "별도" if value == "excluded" else "포함"


def mask_phone_last4(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 4:
        return "***-****-****"
    return f"***-****-{digits[-4:]}"
