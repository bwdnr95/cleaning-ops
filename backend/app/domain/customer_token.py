from secrets import token_urlsafe

CUSTOMER_TOKEN_PREFIX = "ct2_"


def generate_customer_token() -> str:
    return f"{CUSTOMER_TOKEN_PREFIX}{token_urlsafe(24)}"
