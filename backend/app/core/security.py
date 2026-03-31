import secrets


def generate_api_key() -> str:
    return "kp_" + secrets.token_urlsafe(32)
