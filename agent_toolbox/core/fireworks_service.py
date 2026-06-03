"""Fireworks AI E2E flow — Facade module.

Re-exports all functions from sub-modules for backward compatibility.
All imports `from agent_toolbox.core.fireworks_service import X` continue to work.
New clear aliases (signup_vercel, login_vercel, etc.) also available.

Docs: fireworks_service.doc.md
"""
# Browser handle and launch
from agent_toolbox.core.browser_handle import _BrowserHandle
from agent_toolbox.core.browser_launch import launch, cleanup_bot

# Vercel account lifecycle (legacy names + clear aliases)
from agent_toolbox.core.vercel_account import (
    signup_fireworks, verify_account, login_fireworks,
    signup_vercel, verify_vercel, login_vercel,
)

# Onboarding (legacy name + clear alias)
from agent_toolbox.core.vercel_onboarding import _playwright_onboarding, vercel_onboarding

# API key extraction (legacy name + clear alias)
from agent_toolbox.core.vercel_apikey import create_api_key, create_vercel_api_key

__all__ = [
    # Browser
    "_BrowserHandle",
    "launch",
    "cleanup_bot",
    # Legacy names (backward compat)
    "signup_fireworks",
    "verify_account",
    "login_fireworks",
    "_playwright_onboarding",
    "create_api_key",
    # Clear aliases (preferred)
    "signup_vercel",
    "verify_vercel",
    "login_vercel",
    "vercel_onboarding",
    "create_vercel_api_key",
]
