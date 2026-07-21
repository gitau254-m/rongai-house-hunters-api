from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuth
import uuid

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.models.profile import Profile
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse
from app.core.email import send_signup_welcome_email
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# ── Google OAuth client setup ────────────────────────────────────────
# This runs once when the file loads — sets up the Google connection
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ════════════════════════════════════════════════
# MANUAL AUTH — email + password (what you built)
# ════════════════════════════════════════════════

@router.post("/signup", status_code=201)
async def signup(data: SignupRequest, background_tasks: BackgroundTasks,db: AsyncSession = Depends(get_db)):
    """
    Creates a new user account with email and password.
    Password is hashed before saving — never stored as plain text.
    """
    existing = await db.execute(
        select(Profile).where(Profile.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists"
        )

    new_user = Profile(
        id=uuid.uuid4(),
        full_name=data.full_name,
        email=data.email,
        phone_number=data.phone_number,
        role=data.role,
        password_hash=hash_password(data.password),
        status="active",
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    background_tasks.add_task(
        send_signup_welcome_email,
        to_email=data.email,
        full_name=data.full_name,
        role=data.role,
    )

    return {
        "message": "Account created successfully",
        "user_id": str(new_user.id),
        "role": new_user.role
    }


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Logs in a user and returns a JWT token.
    Same error for wrong email OR wrong password — intentional security practice.
    """
    result = await db.execute(
        select(Profile).where(Profile.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        # user.password_hash is None for Google-auth users who have no password
        # We don't tell them that — same generic error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended"
        )

    token = create_access_token(user_id=str(user.id), role=user.role)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id
    )


# ════════════════════════════════════════════════
# GOOGLE AUTH — Continue with Google button
# ════════════════════════════════════════════════

@router.get("/google/login")
async def google_login(request: Request):
    """
    Step 1 of Google login.
    Your frontend "Continue with Google" button calls this URL.
    This redirects the user to Google's login page.
    Your app doesn't handle anything until Google sends them back.
    """
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Step 2 of Google login — Google redirects HERE after user approves.

    What happens:
    1. We receive a temporary code from Google
    2. We swap it for the user's real Google profile info
    3. We find or create their account in OUR database
    4. We issue OUR own JWT — from here it works like normal login
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="Google login failed or was cancelled")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Could not retrieve profile from Google")

    google_email = user_info["email"]
    google_name = user_info["name"]

    # Check if this Google email already has an account
    existing_result = await db.execute(
        select(Profile).where(Profile.email == google_email)
    )
    user = existing_result.scalar_one_or_none()

    if user is None:
        # First time signing in with Google — create their profile
        # Default to customer. They can apply to become a caretaker separately.
        user = Profile(
            id=uuid.uuid4(),
            full_name=google_name,
            email=google_email,
            role="customer",
            status="active",
            password_hash=None,  # Google users have no password — perfectly valid
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Issue our standard JWT — same token format as manual login
    jwt_token = create_access_token(user_id=str(user.id), role=user.role)

    # Redirect to frontend with token
    # The frontend JavaScript reads this token from the URL and stores it
    frontend_url = "http://localhost:3000/auth/callback"
    return RedirectResponse(
        url=f"{frontend_url}?token={jwt_token}&role={user.role}"
    )