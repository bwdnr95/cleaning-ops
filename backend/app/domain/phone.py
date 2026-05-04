import re


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def phone_suffix_matches(phone: str, suffix: str) -> bool:
    clean_phone = normalize_phone(phone)
    clean_suffix = normalize_phone(suffix)
    return len(clean_suffix) == 4 and clean_phone.endswith(clean_suffix)
