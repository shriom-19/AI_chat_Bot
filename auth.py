"""HTTP Basic auth for the JSON API.

Credentials come from environment variables (config.ADMIN_USERNAME /
config.ADMIN_PASSWORD) — never hardcoded. The Streamlit admin panel
collects a username/password at login and sends them as HTTP Basic auth
on every request; this dependency is the single place that validates them.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import config

security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    valid_username = secrets.compare_digest(credentials.username, config.ADMIN_USERNAME)
    valid_password = secrets.compare_digest(credentials.password, config.ADMIN_PASSWORD)

    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
