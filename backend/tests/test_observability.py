import json

import sentry_sdk
from sentry_sdk.types import Event

from app.core.config import Settings
from app.core.observability import init_sentry, redact_customer_tokens, scrub_sentry_event


def test_sentry_initialization_disables_request_body_capture(monkeypatch) -> None:
    captured_options: dict[str, object] = {}

    def fake_init(**options: object) -> None:
        captured_options.update(options)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    init_sentry(Settings(environment="test", sentry_dsn="https://public@example.com/1"))

    assert captured_options["max_request_body_size"] == "never"
    assert captured_options["include_local_variables"] is False


def test_redact_customer_tokens_covers_api_page_and_query_links() -> None:
    secret = "customer-secret-token"
    values = [
        f"https://ops.example/api/customer/orders/{secret}/verify",
        f"POST /api/customer/orders/{secret}/as-requests",
        f"https://ops.example/c/{secret}",
        f"https://ops.example/customer/{secret}?source=message",
        f"https://ops.example/c?t={secret}",
        f"https://ops.example/customer?token={secret}",
        f"https://ops.example/c?customer_token={secret}",
        f"https://ops.example/c#token={secret}",
        f"https://ops.example/customer#customer_token={secret}",
        f"t={secret}",
        f"token={secret}&x=1",
        f"customer_token={secret}",
    ]

    for value in values:
        redacted = redact_customer_tokens(value)
        assert secret not in redacted
        assert "[redacted]" in redacted


def test_scrub_sentry_event_recursively_removes_customer_tokens() -> None:
    secret = "nested-customer-secret"
    webhook_secret = "solapi-webhook-secret-hash"
    event: Event = {
        "request": {
            "url": f"https://ops.example/api/customer/orders/{secret}/verify",
            "query_string": f"t={secret}",
            "headers": {
                "referer": f"https://ops.example/c/{secret}",
                "x-customer-token": secret,
                "x-solapi-secret": webhook_secret,
            },
        },
        "transaction": f"POST /api/customer/orders/{secret}/verify",
        "breadcrumbs": {
            "values": [
                {"data": {"url": f"https://ops.example/customer/{secret}"}},
            ]
        },
        "spans": [
            {
                "description": f"GET /api/customer/orders/{secret}/verify",
                "data": {
                    "url": f"https://ops.example/c?t={secret}",
                    "http.query": f"token={secret}&source=sentry",
                },
            }
        ],
        "extra": {
            "history": {"__cleaning_ops_customer_token": secret},
            "auth": {"authorization": secret},
        },
    }

    scrubbed = scrub_sentry_event(event)
    serialized = json.dumps(scrubbed)
    assert secret not in serialized
    assert webhook_secret not in serialized
    assert serialized.count("[redacted]") >= 10
