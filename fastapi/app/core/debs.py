from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from app.core.security import decode_access_token

# This tells FastAPI: "expect a Bearer token, and document it in /docs"
# tokenUrl is just for Swagger's "Authorize" button — doesn't affect logic
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT sent in the Authorization header.
    Returns {"user_id": ..., "role": ...} if valid.
    Raises 401 if missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return {"user_id": user_id, "role": role}


def require_role(allowed_roles: list[str]):
    """
    A dependency FACTORY — returns a dependency function customised
    with whichever roles are allowed for that specific endpoint.
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only {allowed_roles} can perform this action"
            )
        return current_user
    return role_checker