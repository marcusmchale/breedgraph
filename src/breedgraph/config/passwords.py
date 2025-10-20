import os
from password_strength import PasswordPolicy


def get_password_policy() -> PasswordPolicy:
    return PasswordPolicy.from_names(
        length = os.environ.get('PASSWORD_MIN_LENGTH', 8),
        uppercase=os.environ.get('PASSWORD_MIN_UPPERCASE', 1),
        numbers=os.environ.get('PASSWORD_MIN_NUMBERS', 1),
        special=os.environ.get('PASSWORD_MIN_SPECIAL', 1)
    )

