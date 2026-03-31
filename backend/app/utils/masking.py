def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        hidden_name = "*" * len(name)
    else:
        hidden_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
    return f"{hidden_name}@{domain}"
