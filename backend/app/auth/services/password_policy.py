"""Password Policy Validator for Enterprise Identity Management in Investiga.

This module enforces enterprise-grade password complexity rules (length, casing,
digits, special characters) to prevent weak credential vulnerabilities.
"""

import re

from app.exceptions.domain import ValidationException


class PasswordPolicy:
    """Configurable enterprise password complexity policy validator.

    Attributes:
        min_length: Minimum number of characters required.
        require_uppercase: Whether at least one uppercase letter (A-Z) is mandatory.
        require_lowercase: Whether at least one lowercase letter (a-z) is mandatory.
        require_digits: Whether at least one numerical digit (0-9) is mandatory.
        require_special: Whether at least one special character is mandatory.
        special_characters: Permitted set of special symbol characters.
    """

    def __init__(
        self,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = True,
        require_special: bool = True,
        special_characters: str = r"!@#$%^&*()_+-=[]{}|;:,.<>?",
    ) -> None:
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special
        self.special_characters = special_characters

    def validate(self, password: str) -> None:
        """Validate a plaintext password against active complexity constraints.

        Args:
            password: The plaintext password string to inspect.

        Raises:
            ValidationException: If one or more complexity rules are violated.
        """
        violations: list[str] = []

        if len(password) < self.min_length:
            violations.append(
                f"Password must be at least {self.min_length} characters long."
            )

        if self.require_uppercase and not any(c.isupper() for c in password):
            violations.append(
                "Password must contain at least one uppercase letter (A-Z)."
            )

        if self.require_lowercase and not any(c.islower() for c in password):
            violations.append(
                "Password must contain at least one lowercase letter (a-z)."
            )

        if self.require_digits and not any(c.isdigit() for c in password):
            violations.append(
                "Password must contain at least one numerical digit (0-9)."
            )

        if self.require_special:
            escaped_specials = re.escape(self.special_characters)
            if not re.search(f"[{escaped_specials}]", password):
                violations.append(
                    f"Password must contain at least one special character: {self.special_characters}"
                )

        if violations:
            raise ValidationException(
                message="Password does not meet enterprise security requirements.",
                details={"policy_violations": violations},
            )


# Default enterprise password policy instance
default_password_policy = PasswordPolicy(min_length=8)
