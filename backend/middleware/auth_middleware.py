"""
middleware/auth_middleware.py
JWT dependency for protecting FastAPI endpoints.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.auth_service import decode_token
from services.sql_engine import get_user_by_id

security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Extract and verify current user from JWT token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict | None:
    """Return user if token provided, None otherwise."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    return get_user_by_id(payload.get("sub"))