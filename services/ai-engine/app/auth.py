from fastapi import Security, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
from app.config import settings

security = HTTPBearer()

def verify_token(credentials: HTTPAuthCredentials = Security(security)) -> dict:
    """
    Verify JWT token from Authorization header.
    Used by both mobile clients and API service.
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"verify_exp": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def get_current_user(token_payload: dict = Depends(verify_token)) -> dict:
    """Extract user info from token payload"""
    return {
        "user_id": token_payload.get("sub"),
    }

