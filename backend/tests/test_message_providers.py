import hashlib
import hmac
import json
from datetime import UTC, datetime
from http.client import HTTPMessage

import pytest

from app.core.config import Settings, settings
from app.domain.constants import MessageChannel, MessageStatus, MessageType
from app.domain.message_templates import KAKAO_TEMPLATE_DEFINITIONS, SOLAPI_KAKAO_PROFILE_ID
from app.services import messages as messages_module
from app.services.messages import (
    MessageProviderSendInput,
    MockMessageProvider,
    SolapiMessageProvider,
    build_message_provider,
    build_solapi_auth_header,
)


def approved_template_settings() -> dict[str, str]:
    return {
        definition.template_id_setting: definition.expected_template_id
        for definition in KAKAO_TEMPLATE_DEFINITIONS.values()
    }


def test_build_solapi_auth_header_matches_expected_hmac() -> None:
    now = datetime(2026, 5, 5, 1, 2, 3, tzinfo=UTC)
    expected_signature = hmac.new(
        b"api-secret",
        b"2026-05-05T01:02:03Ztest-salt",
        hashlib.sha256,
    ).hexdigest()

    header = build_solapi_auth_header(
        "api-key",
        "api-secret",
        now=now,
        salt="test-salt",
    )

    assert header == (
        "HMAC-SHA256 apiKey=api-key, "
        f"date=2026-05-05T01:02:03Z, salt=test-salt, signature={expected_signature}"
    )


def test_message_provider_factory_keeps_mock_default_and_selects_solapi(monkeypatch) -> None:
    monkeypatch.setattr(settings, "message_provider", "mock")
    assert isinstance(build_message_provider(), MockMessageProvider)

    monkeypatch.setattr(settings, "message_provider", "solapi")
    assert isinstance(build_message_provider(), SolapiMessageProvider)


def test_solapi_provider_posts_normalized_payload(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "groupInfo": {"groupId": "group-1"},
                    "messageList": [{"messageId": "message-1"}],
                    "failedMessageList": [],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
        send_url="https://solapi.example.test/messages/v4/send-many/detail",
        timeout_seconds=3.5,
    )

    result = provider.send("hello", "010-1234-5678")

    assert result.status == MessageStatus.SENT
    assert result.provider == "solapi"
    assert result.provider_group_id == "group-1"
    assert result.provider_message_id == "message-1"
    assert result.provider_response is not None
    assert result.provider_response["groupInfo"] == {"groupId": "group-1"}
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://solapi.example.test/messages/v4/send-many/detail"
    assert request.get_method() == "POST"
    assert timeout == 3.5
    assert request.get_header("Authorization").startswith("HMAC-SHA256 apiKey=api-key")

    assert request.data is not None
    payload = json.loads(request.data.decode("utf-8"))
    assert payload == {
        "messages": [
            {
                "to": "01012345678",
                "from": "021234567",
                "text": "hello",
                "type": "SMS",
            }
        ]
    }


def test_solapi_provider_promotes_long_sms_to_lms_and_reports_actual_channel(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "groupInfo": {"groupId": "lms-group"},
                    "messageList": [{"messageId": "lms-message"}],
                    "failedMessageList": [],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="가" * 31,
            recipient_phone="010-1234-5678",
            channel=MessageChannel.SMS,
            message_type=MessageType.CUSTOMER_ACCESS_LINK,
        )
    )

    assert result.status == MessageStatus.SENT
    assert result.channel == MessageChannel.LMS
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["messages"][0]["type"] == "LMS"


def test_solapi_provider_includes_message_log_id_in_sms_custom_fields(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "groupInfo": {"groupId": "sms-group"},
                    "messageList": [{"messageId": "sms-message"}],
                    "failedMessageList": [],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="hello",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.SMS,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            message_log_id="internal-message-log-id",
        )
    )

    assert result.status == MessageStatus.SENT
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["messages"][0]["customFields"] == {
        messages_module.SOLAPI_MESSAGE_LOG_CUSTOM_FIELD: "internal-message-log-id"
    }


def test_solapi_provider_posts_approved_kakao_template(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"groupInfo": {"groupId": "kakao-group"}, "failedMessageList": []}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_channel_id", "channel-id")

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
        send_url="https://solapi.example.test/messages/v4/send-many/detail",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="fallback sms",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.ALIMTALK,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            kakao_template_id="KA01",
            kakao_variables={"#{고객명}": "홍길동"},
            message_log_id="internal-kakao-log-id",
        )
    )

    assert result.status == MessageStatus.SENT
    assert result.channel == MessageChannel.ALIMTALK
    assert result.provider_group_id == "kakao-group"
    assert len(requests) == 1

    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload == {
        "messages": [
            {
                "to": "01012345678",
                "from": "021234567",
                "text": "fallback sms",
                "type": "ATA",
                "customFields": {
                    messages_module.SOLAPI_MESSAGE_LOG_CUSTOM_FIELD: "internal-kakao-log-id"
                },
                "kakaoOptions": {
                    "pfId": "channel-id",
                    "templateId": "KA01",
                    "disableSms": False,
                    "variables": {"#{고객명}": "홍길동"},
                },
            }
        ]
    }


def test_solapi_provider_falls_back_to_sms_when_alimtalk_fails(monkeypatch) -> None:
    requests = []
    responses = [
        {"failedMessageList": [{"reason": "template mismatch"}]},
        {"groupInfo": {"groupId": "sms-group"}, "failedMessageList": []},
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_channel_id", "channel-id")

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="fallback sms",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.ALIMTALK,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            kakao_template_id="KA01",
            kakao_variables={"#{고객명}": "홍길동"},
            fallback_sms_content="fallback sms",
        )
    )

    assert result.status == MessageStatus.SENT
    assert result.channel == MessageChannel.SMS
    assert result.provider_group_id == "sms-group"
    assert result.provider_status_message == "alimtalk_failed_sms_fallback_sent"
    assert len(requests) == 2

    fallback_payload = json.loads(requests[1].data.decode("utf-8"))
    assert fallback_payload["messages"][0]["text"] == "fallback sms"
    assert fallback_payload["messages"][0]["type"] == "SMS"


def test_solapi_provider_preserves_unknown_sms_fallback_outcome(monkeypatch) -> None:
    requests = []

    class FailedAlimtalkResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"failedMessageList": [{"reason": "template mismatch"}]}).encode(
                "utf-8"
            )

    def fake_urlopen(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            return FailedAlimtalkResponse()
        raise TimeoutError("fallback response lost")

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")
    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="alimtalk",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.ALIMTALK,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            kakao_template_id="KA01",
            kakao_variables={"#{고객명}": "홍길동"},
            fallback_sms_content="fallback sms",
        )
    )

    assert result.status == MessageStatus.PENDING
    assert result.channel == MessageChannel.SMS
    assert result.provider_error_code == "solapi_outcome_unknown"
    assert result.provider_status_message == "alimtalk_failed_sms_fallback_outcome_unknown"
    assert len(requests) == 2


def test_solapi_provider_requires_environment_credentials() -> None:
    provider = SolapiMessageProvider(
        api_key="",
        api_secret="",
        sender_number="02-123-4567",
    )

    result = provider.send("hello", "010-1234-5678")

    assert result.status == MessageStatus.FAILED
    assert result.error_message == "solapi_missing_credentials"
    assert result.provider_error_code == "solapi_missing_credentials"


def test_solapi_provider_maps_failed_message_list(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "groupInfo": {"groupId": "group-failed"},
                    "failedMessageList": [{"reason": "invalid phone"}],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send("hello", "010-1234-5678")

    assert result.status == MessageStatus.FAILED
    assert result.error_message == "solapi_failed: invalid phone"
    assert result.provider_error_code == "solapi_provider_failed"
    assert result.provider_group_id == "group-failed"


@pytest.mark.parametrize(
    "raw_body",
    [b"[]", b"{}", b'{"failedMessageList": []}'],
)
def test_solapi_provider_keeps_unconfirmed_success_pending(monkeypatch, raw_body: bytes) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return raw_body

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send("hello", "010-1234-5678")

    assert result.status == MessageStatus.PENDING
    assert result.error_message == "solapi_invalid_response"
    assert result.provider_error_code == "solapi_invalid_response"


def test_solapi_provider_does_not_fallback_after_unknown_alimtalk_outcome(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        raise TimeoutError("response lost")

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )
    result = provider.send_with_context(
        MessageProviderSendInput(
            content="alimtalk",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.ALIMTALK,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            kakao_template_id="KA01",
            kakao_variables={"#{고객명}": "홍길동"},
            fallback_sms_content="fallback sms",
        )
    )

    assert result.status == MessageStatus.PENDING
    assert result.provider_error_code == "solapi_outcome_unknown"
    assert len(requests) == 1


@pytest.mark.parametrize("failure_kind", ["http_500", "truncated_body"])
def test_solapi_provider_keeps_post_dispatch_failures_pending_without_fallback(
    monkeypatch,
    failure_kind: str,
) -> None:
    requests = []

    class TruncatedResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            raise messages_module.HttpClientException("truncated response")

    def fake_urlopen(request, timeout):
        requests.append(request)
        if failure_kind == "http_500":
            raise messages_module.HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                HTTPMessage(),
                None,
            )
        return TruncatedResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")
    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    result = provider.send_with_context(
        MessageProviderSendInput(
            content="alimtalk",
            recipient_phone="010-1234-5678",
            channel=MessageChannel.ALIMTALK,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            kakao_template_id="KA01",
            kakao_variables={"#{고객명}": "홍길동"},
            fallback_sms_content="fallback sms",
        )
    )

    assert result.status == MessageStatus.PENDING
    assert result.provider_error_code == "solapi_outcome_unknown"
    assert len(requests) == 1


def test_solapi_runtime_opener_rejects_redirects(monkeypatch) -> None:
    installed_handlers = []
    opened_requests = []

    class FakeOpener:
        def open(self, request, timeout):
            opened_requests.append(request)
            raise messages_module.HTTPError(
                request.full_url,
                302,
                "Found",
                HTTPMessage(),
                None,
            )

    def fake_build_opener(*handlers):
        installed_handlers.extend(handlers)
        return FakeOpener()

    monkeypatch.setattr(messages_module, "build_opener", fake_build_opener)

    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )
    result = provider.send("hello", "010-1234-5678")

    assert result.status == MessageStatus.FAILED
    assert result.provider_error_code == "solapi_http_error"
    assert len(opened_requests) == 1
    assert any(
        isinstance(handler, messages_module.NoRedirectHandler) for handler in installed_handlers
    )


@pytest.mark.parametrize(
    ("api_key", "api_secret"),
    [("", ""), ("   ", "\t")],
)
def test_production_solapi_provider_requires_credentials(
    api_key: str,
    api_secret: str,
) -> None:
    with pytest.raises(ValueError, match="production solapi message provider missing settings"):
        Settings(
            environment="production",
            secret_key="x" * 32,
            storage_provider="s3",
            s3_bucket="bucket",
            s3_access_key_id="access",
            s3_secret_access_key="secret",
            s3_public_base_url="https://cdn.example.com",
            message_provider="solapi",
            solapi_api_key=api_key,
            solapi_api_secret=api_secret,
            solapi_sender_number="",
        )


@pytest.mark.parametrize(
    ("api_key", "api_secret"),
    [
        ("replace-with-solapi-api-key", "api-secret"),
        ("api-key", "replace-with-solapi-api-secret"),
    ],
)
def test_production_solapi_provider_rejects_placeholder_credentials(
    api_key: str,
    api_secret: str,
) -> None:
    with pytest.raises(ValueError, match="credentials must not use placeholders"):
        Settings.model_validate(
            {
                "environment": " PRODUCTION ",
                "secret_key": "x" * 32,
                "storage_provider": "s3",
                "s3_bucket": "bucket",
                "s3_access_key_id": "access",
                "s3_secret_access_key": "secret",
                "s3_public_base_url": "https://cdn.example.com",
                "message_provider": " SOLAPI ",
                "solapi_api_key": api_key,
                "solapi_api_secret": api_secret,
                "solapi_sender_number": "021234567",
                "solapi_webhook_secret": "w" * 32,
                "solapi_kakao_pf_id": SOLAPI_KAKAO_PROFILE_ID,
                "sentry_dsn": "https://public@example.com/1",
                **approved_template_settings(),
            }
        )


def test_production_rejects_mock_message_provider() -> None:
    with pytest.raises(ValueError, match="production requires message_provider=solapi"):
        Settings(
            environment="production",
            secret_key="x" * 32,
            storage_provider="s3",
            s3_bucket="bucket",
            s3_access_key_id="access",
            s3_secret_access_key="secret",
            s3_public_base_url="https://cdn.example.com",
            message_provider="mock",
            sentry_dsn="https://public@example.com/1",
        )


def test_production_solapi_provider_rejects_untrusted_send_url() -> None:
    with pytest.raises(ValueError, match="production solapi_send_url must use"):
        Settings.model_validate(
            {
                "environment": "production",
                "secret_key": "x" * 32,
                "storage_provider": "s3",
                "s3_bucket": "bucket",
                "s3_access_key_id": "access",
                "s3_secret_access_key": "secret",
                "s3_public_base_url": "https://cdn.example.com",
                "message_provider": "solapi",
                "solapi_api_key": "api-key",
                "solapi_api_secret": "api-secret",
                "solapi_sender_number": "021234567",
                "solapi_webhook_secret": "w" * 32,
                "solapi_kakao_pf_id": SOLAPI_KAKAO_PROFILE_ID,
                "solapi_send_url": "https://attacker.example/messages",
                "sentry_dsn": "https://public@example.com/1",
                **approved_template_settings(),
            }
        )


@pytest.mark.parametrize(
    "webhook_secret",
    ["short", "replace-with-random-webhook-secret-32chars"],
)
def test_production_solapi_provider_requires_strong_webhook_secret(
    webhook_secret: str,
) -> None:
    with pytest.raises(ValueError, match="solapi_webhook_secret must be a random value"):
        Settings.model_validate(
            {
                "environment": "production",
                "secret_key": "x" * 32,
                "storage_provider": "s3",
                "s3_bucket": "bucket",
                "s3_access_key_id": "access",
                "s3_secret_access_key": "secret",
                "s3_public_base_url": "https://cdn.example.com",
                "message_provider": "solapi",
                "solapi_api_key": "api-key",
                "solapi_api_secret": "api-secret",
                "solapi_sender_number": "021234567",
                "solapi_webhook_secret": webhook_secret,
                "solapi_kakao_pf_id": SOLAPI_KAKAO_PROFILE_ID,
                "sentry_dsn": "https://public@example.com/1",
                **approved_template_settings(),
            }
        )


def test_production_solapi_provider_requires_exact_approved_template_ids() -> None:
    template_settings = approved_template_settings()
    template_settings["solapi_kakao_template_customer_day_before"] = "wrong-template-id"

    with pytest.raises(ValueError, match="template IDs do not match approved templates"):
        Settings.model_validate(
            {
                "environment": "production",
                "secret_key": "x" * 32,
                "storage_provider": "s3",
                "s3_bucket": "bucket",
                "s3_access_key_id": "access",
                "s3_secret_access_key": "secret",
                "s3_public_base_url": "https://cdn.example.com",
                "message_provider": "solapi",
                "solapi_api_key": "api-key",
                "solapi_api_secret": "api-secret",
                "solapi_sender_number": "021234567",
                "solapi_webhook_secret": "w" * 32,
                "solapi_kakao_pf_id": SOLAPI_KAKAO_PROFILE_ID,
                "sentry_dsn": "https://public@example.com/1",
                **template_settings,
            }
        )
