from app.domain.partner_category import (
    RESIDENTIAL_PARTNER_CATEGORY_ID,
    infer_partner_category_id,
)


def test_infer_partner_category_from_service_text() -> None:
    assert infer_partner_category_id("입주청소") == RESIDENTIAL_PARTNER_CATEGORY_ID
    assert infer_partner_category_id("에어컨청소") == "seed-partner-category-aircon"
    assert infer_partner_category_id("줄눈") == "seed-partner-category-grout"
    assert infer_partner_category_id("새집증후군") == "seed-partner-category-new-house-syndrome"
    assert infer_partner_category_id("탄성코드") == "seed-partner-category-elastic-coating"
    assert infer_partner_category_id("알 수 없는 서비스") is None
