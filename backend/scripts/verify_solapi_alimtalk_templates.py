import json
import re
from collections.abc import Iterable
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.core.config import settings
from app.domain.constants import MessageType
from app.domain.message_templates import KAKAO_TEMPLATE_DEFINITIONS, SOLAPI_KAKAO_PROFILE_ID
from app.services.messages import build_solapi_auth_header

EXPECTED_PROFILE_ID = SOLAPI_KAKAO_PROFILE_ID
EXPECTED_TEMPLATE_IDS: dict[MessageType, str] = {
    message_type: definition.expected_template_id
    for message_type, definition in KAKAO_TEMPLATE_DEFINITIONS.items()
}
VARIABLE_PATTERN = re.compile(r"#\{[^}]+\}")


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def iter_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
        return
    if isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def template_items(payload: object) -> list[dict[str, object]]:
    raw_items: object = payload
    if isinstance(payload, dict):
        raw_items = payload.get("templateList", [])
    if not isinstance(raw_items, list):
        raise ValueError("unexpected_solapi_template_response")
    return [item for item in raw_items if isinstance(item, dict)]


def verify_templates(items: list[dict[str, object]]) -> tuple[bool, list[dict[str, object]]]:
    by_id = {
        template_id: item
        for item in items
        if isinstance((template_id := item.get("templateId")), str)
    }
    results: list[dict[str, object]] = []
    is_valid = True

    for message_type, expected_template_id in EXPECTED_TEMPLATE_IDS.items():
        item = by_id.get(expected_template_id)
        definition = KAKAO_TEMPLATE_DEFINITIONS[message_type]
        expected_variables = {variable.solapi_key for variable in definition.variables}
        actual_variables = (
            set(VARIABLE_PATTERN.findall("\n".join(iter_strings(item)))) if item else set()
        )
        status = item.get("status") if item else None
        profile_id = (item.get("pfId") or item.get("channelId")) if item else None
        configured_template_id = getattr(settings, definition.template_id_setting, "")
        configured_profile_id = (
            settings.solapi_kakao_pf_id.strip()
            or settings.solapi_kakao_channel_id.strip()
        )
        matches = bool(
            item
            and status == "APPROVED"
            and profile_id == EXPECTED_PROFILE_ID
            and actual_variables == expected_variables
            and configured_template_id == expected_template_id
            and configured_profile_id == EXPECTED_PROFILE_ID
        )
        is_valid = is_valid and matches
        results.append(
            {
                "messageType": message_type.value,
                "templateId": expected_template_id,
                "status": status,
                "profileId": profile_id,
                "missingVariables": sorted(expected_variables - actual_variables),
                "unexpectedVariables": sorted(actual_variables - expected_variables),
                "runtimeTemplateMatches": configured_template_id == expected_template_id,
                "runtimeProfileMatches": configured_profile_id == EXPECTED_PROFILE_ID,
                "matches": matches,
            }
        )

    return is_valid, results


def main() -> int:
    if not settings.solapi_api_key or not settings.solapi_api_secret:
        raise ValueError("solapi_credentials_not_configured")
    request = Request(
        "https://api.solapi.com/kakao/v2/templates/sendable",
        headers={
            "Authorization": build_solapi_auth_header(
                settings.solapi_api_key,
                settings.solapi_api_secret,
            )
        },
    )
    opener = build_opener(RejectRedirects())
    with opener.open(request, timeout=15) as response:
        payload: object = json.load(response)
    is_valid, results = verify_templates(template_items(payload))
    print(
        json.dumps(
            {
                "verified": is_valid,
                "matched": sum(bool(row["matches"]) for row in results),
                "templates": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
