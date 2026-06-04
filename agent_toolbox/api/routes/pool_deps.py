"""
Shared pool route dependencies — auth, common imports.

Docs: pool_deps.doc.md
"""
import os
import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)
AUTH_TOKEN = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()
logger = logging.getLogger(__name__)

def verify_auth_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Require Bearer token for mutating endpoints. Allow localhost bypass."""
    token = (credentials.credentials if credentials else "").strip()
    if not AUTH_TOKEN:
        return True  # No auth configured — open (backward compat)
    if token == AUTH_TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing Bearer token")
