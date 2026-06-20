from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.profile import Profile
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/signup", status_code=201)
async def signup(data: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Creates a new user account.
    Password is hashed before saving — never stored as plain text.
    """
    # Check if email already exists
    existing = await db.execute(
        select(Profile).where(Profile.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists"
        )

    # Create the profile with hashed password
    new_user = Profile(
        id=uuid.uuid4(),
        full_name=data.full_name,
        email=data.email,
        phone_number=data.phone_number,
        role=data.role,
        password_hash=hash_password(data.password),   # ← NEVER save plain password
        status="active",
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "message": "Account created successfully",
        "user_id": str(new_user.id),
        "role": new_user.role
    }


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Logs in a user and returns a JWT token.
    The token must be sent with every protected request.
    """
    # Find user by email
    result = await db.execute(
        select(Profile).where(Profile.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    # We give the SAME error whether email is wrong or password is wrong.
    # This is intentional — telling an attacker "email not found" leaks information.
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended"
        )

    # Generate JWT token
    token = create_access_token(
        user_id=str(user.id),
        role=user.role
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id
    )