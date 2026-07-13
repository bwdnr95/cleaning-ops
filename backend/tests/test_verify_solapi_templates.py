from collections.abc import Iterator

import pytest

from app.core.config import settings
from app.domain.message_templates import KAKAO_TEMPLATE_DEFINITIONS
from scripts.verify_solapi_alimtalk_templates import (
    EXPECTED_PROFILE_ID,
    EXPECTED_TEMPLATE_IDS,
    RejectRedirects,
    verify_templates,
)


def approved_template_items() -> Iterator[dict[str, object]]:
    for message_type, template_id in EXPECTED_TEMPLATE_IDS.items():
        variables = " ".join(
            variable.solapi_key
            for variable in KAKAO_TEMPLATE_DEFINITIONS[message_type].variables
        )
        yield {
            "templateId": template_id,
            "pfId": EXPECTED_PROFILE_ID,
            "status": "APPROVED",
            "content": variables,
        }


def configure_expected_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", EXPECTED_PROFILE_ID)
    monkeypatch.setattr(settings, "solapi_kakao_channel_id", "")
    for message_type, template_id in EXPECTED_TEMPLATE_IDS.items():
        definition = KAKAO_TEMPLATE_DEFINITIONS[message_type]
        monkeypatch.setattr(settings, definition.template_id_setting, template_id)


def test_verify_templates_requires_approved_live_and_runtime_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_expected_runtime(monkeypatch)

    is_valid, results = verify_templates(list(approved_template_items()))

    assert is_valid is True
    assert len(results) == len(EXPECTED_TEMPLATE_IDS)
    assert all(result["matches"] is True for result in results)


def test_verify_templates_rejects_runtime_template_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_expected_runtime(monkeypatch)
    first_definition = next(iter(KAKAO_TEMPLATE_DEFINITIONS.values()))
    monkeypatch.setattr(settings, first_definition.template_id_setting, "WRONG_TEMPLATE")

    is_valid, results = verify_templates(list(approved_template_items()))

    assert is_valid is False
    assert any(result["runtimeTemplateMatches"] is False for result in results)


def test_verify_templates_rejects_unapproved_live_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_expected_runtime(monkeypatch)
    items = list(approved_template_items())
    items[0]["status"] = "PENDING"

    is_valid, results = verify_templates(items)

    assert is_valid is False
    assert results[0]["matches"] is False


def test_solapi_verifier_does_not_forward_authorization_on_redirect() -> None:
    assert RejectRedirects().redirect_request() is None
