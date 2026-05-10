import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest

from app.core.config import Settings, settings
from app.domain.constants import MessageChannel, MessageStatus, MessageType
from app.services import messages as messages_module
from app.services.messages import (
    MessageProviderSendInput,
    MockMessageProvider,
    SolapiMessageProvider,
    build_message_provider,
    build_solapi_auth_header,
)


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
            }
        ]
    }


def test_solapi_provider_posts_approved_kakao_template(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"groupInfo": {"groupId": "kakao-group"}, "failedMessageList": []}).encode(
                "utf-8"
            )

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(messages_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")

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
                "kakaoOptions": {
                    "pfId": "pf-id",
                    "templateId": "KA01",
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
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")

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


def test_solapi_provider_maps_unexpected_response_to_failed(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def read(self) -> bytes:
            return b"[]"

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
    assert result.error_message == "solapi_invalid_response"
    assert result.provider_error_code == "solapi_invalid_response"


def test_production_solapi_provider_requires_credentials() -> None:
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
            solapi_api_key="",
            solapi_api_secret="",
            solapi_sender_number="",
        )
