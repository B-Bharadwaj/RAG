"""
routers/auth.py
Authentication endpoints — register, login, Google OAuth, me.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional

from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)
from services.sql_engine import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    email_exists,
)

router  = APIRouter()
security = HTTPBearer()


# -- Schemas ----------------------------------------------------------------

class RegisterRequest(BaseModel):
    email:    str
    password: str
    name:     str


class LoginRequest(BaseModel):
    email:    str
    password: str


class GoogleAuthRequest(BaseModel):
    token: str      # Google ID token from frontend


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         dict


# -- Dependency -------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """JWT dependency — extract current user from token."""
    token   = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# -- Endpoints --------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register with email and password."""
    if email_exists(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(request.password)
    user   = create_user(
        email     = request.email,
        name      = request.name,
        password  = hashed,
        auth_type = "email",
    )

    token = create_access_token(user["user_id"], user["email"])
    return AuthResponse(access_token=token, user=user)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    user = get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user["user_id"], user["email"])
    return AuthResponse(
        access_token = token,
        user = {
            "user_id":   user["user_id"],
            "email":     user["email"],
            "name":      user["name"],
            "auth_type": user["auth_type"],
            "avatar":    user["avatar"],
        }
    )


@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    """Login or register with Google OAuth token."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    from config import GOOGLE_CLIENT_ID

    try:
        info = id_token.verify_oauth2_token(
            request.token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email  = info["email"]
    name   = info.get("name", email.split("@")[0])
    avatar = info.get("picture", "")

    user = get_user_by_email(email)
    if not user:
        user = create_user(
            email     = email,
            name      = name,
            auth_type = "google",
            avatar    = avatar,
        )
    else:
        user = {
            "user_id":   user["user_id"],
            "email":     user["email"],
            "name":      user["name"],
            "auth_type": user["auth_type"],
            "avatar":    user["avatar"],
        }

    token = create_access_token(user["user_id"], user["email"])
    return AuthResponse(access_token=token, user=user)


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current logged in user info."""
    return {
        "user_id":   current_user["user_id"],
        "email":     current_user["email"],
        "name":      current_user["name"],
        "auth_type": current_user["auth_type"],
        "avatar":    current_user["avatar"],
    }