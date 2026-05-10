from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultPartnerCategory:
    id: str
    name: str
    description: str
    sort_order: int
    keywords: tuple[str, ...]


RESIDENTIAL_PARTNER_CATEGORY_ID = "seed-partner-category-residential"

DEFAULT_PARTNER_CATEGORIES: tuple[DefaultPartnerCategory, ...] = (
    DefaultPartnerCategory(
        id=RESIDENTIAL_PARTNER_CATEGORY_ID,
        name="주거 청소",
        description="입주/이사/거주/정기 청소 협력사",
        sort_order=10,
        keywords=("입주", "이사", "거주", "주거", "정기"),
    ),
    DefaultPartnerCategory(
        id="seed-partner-category-aircon",
        name="에어컨 청소",
        description="에어컨/냉난방 청소 협력사",
        sort_order=20,
        keywords=("에어컨", "냉난방"),
    ),
    DefaultPartnerCategory(
        id="seed-partner-category-grout",
        name="줄눈",
        description="줄눈 시공 협력사",
        sort_order=30,
        keywords=("줄눈",),
    ),
    DefaultPartnerCategory(
        id="seed-partner-category-new-house-syndrome",
        name="새집증후군",
        description="새집증후군 케어 협력사",
        sort_order=40,
        keywords=("새집증후군", "새집"),
    ),
    DefaultPartnerCategory(
        id="seed-partner-category-elastic-coating",
        name="탄성코트",
        description="탄성코트 시공 협력사",
        sort_order=50,
        keywords=("탄성코트", "탄성코드", "탄성"),
    ),
)


def infer_partner_category_id(service_text: str | None) -> str | None:
    if not service_text:
        return None

    normalized = "".join(str(service_text).split())
    for category in DEFAULT_PARTNER_CATEGORIES:
        if any(keyword in normalized for keyword in category.keywords):
            return category.id
    return None
