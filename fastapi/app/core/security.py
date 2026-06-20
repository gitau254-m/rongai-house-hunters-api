from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

# bcrypt is the hashing algorithm — industry standard for passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Converts a plain password into a hash.
    "password123" → "$2b$12$eImiTXuWVxfM37uY4JANjO..."
    The original password is unrecoverable from the hash.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain password matches a stored hash.
    Used during login — never compare passwords directly.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, role: str) -> str:
    """
    Creates a JWT token containing user_id and role.
    This token is what we give back after successful login.
    """
    payload = {
        "sub": user_id,           # sub = subject = who this token is for
        "role": role,             # their role in RHH
        "exp": datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decodes a JWT token and returns the payload.
    Raises JWTError if token is invalid or expired.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])