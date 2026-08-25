from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from laptop.app.config import laptop_settings

security_scheme = HTTPBearer(auto_error=False)


def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> bool:
    """
    Validates Bearer token in the Authorization header.
    Ensures public tunnels (e.g. Cloudflare Quick Tunnel) do not expose an open LLM.
    """
    configured_token = laptop_settings.LAPTOP_API_TOKEN

    # If no token configured, permit for local testing
    if not configured_token:
        return True

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != configured_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
