"""Password Hashing and Cryptographic Verification for Investiga.

This module implements enterprise-grade password security using the Argon2id
algorithm (with automatic fallback and migration for Bcrypt hashes) via Passlib.
It provides both synchronous functions and non-blocking asynchronous helpers to
prevent CPU-intensive hashing from stalling FastAPI's async event loop.
"""

import asyncio
from passlib.context import CryptContext

# Configure Passlib with Argon2 as the primary scheme and bcrypt for legacy compatibility
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MB memory hardness
    argon2__time_cost=3,        # 3 iterations
    argon2__parallelism=4,      # 4 parallel threads
)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Args:
        password: The plaintext password string to hash.

    Returns:
        str: The generated cryptographic hash string with salt and parameters.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored cryptographic hash.

    Args:
        plain_password: The plaintext password provided during authentication.
        hashed_password: The stored Argon2id or Bcrypt hash string.

    Returns:
        bool: True if password matches the hash, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """Check if a stored password hash was computed with deprecated schemes or older parameters.

    Args:
        hashed_password: The stored hash to inspect.

    Returns:
        bool: True if the hash should be updated upon successful login.
    """
    return pwd_context.needs_update(hashed_password)


async def async_get_password_hash(password: str) -> str:
    """Asynchronously compute password hash in a separate thread pool.

    Prevents blocking the AsyncIO event loop during high-throughput user onboarding.

    Args:
        password: The plaintext password to hash.

    Returns:
        str: Cryptographic hash string.
    """
    return await asyncio.to_thread(get_password_hash, password)


async def async_verify_password(plain_password: str, hashed_password: str) -> bool:
    """Asynchronously verify a password in a separate thread pool.

    Prevents CPU-bound hashing verification from blocking concurrent HTTP requests.

    Args:
        plain_password: The plaintext password to check.
        hashed_password: The stored hash string.

    Returns:
        bool: True if verified, False otherwise.
    """
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)
