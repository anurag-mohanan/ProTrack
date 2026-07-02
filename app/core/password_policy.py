import re

PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$"
)

PASSWORD_REQUIREMENTS_MESSAGE = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, number, and special character."
)


def validate_password_strength(password: str) -> None:
    if not PASSWORD_PATTERN.match(password):
        raise ValueError(PASSWORD_REQUIREMENTS_MESSAGE)
