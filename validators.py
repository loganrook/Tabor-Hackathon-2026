"""
validators.py — Password and other validation helpers.

Purpose: Reusable validation (e.g. password strength) without touching DB.
"""

import re


def validate_password(password: str) -> list[str]:
    """
    Check password against security requirements.
    Returns a list of error messages for any requirements not met.
    Empty list means the password is valid.
    """
    errors = []
    if not password or len(password) < 8:
        errors.append("At least 8 characters")
    if password and not re.search(r"[A-Z]", password):
        errors.append("At least one uppercase letter")
    if password and not re.search(r"[a-z]", password):
        errors.append("At least one lowercase letter")
    if password and not re.search(r"\d", password):
        errors.append("At least one number")
    return errors
