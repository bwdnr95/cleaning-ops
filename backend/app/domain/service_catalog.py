from enum import StrEnum


class ServiceUnit(StrEnum):
    PYEONG = "평"
    CASE = "건"
    UNIT = "대"
    SET = "세트"
    KAN = "칸"
    ETC = "기타"


SERVICE_UNITS: tuple[str, ...] = tuple(unit.value for unit in ServiceUnit)
