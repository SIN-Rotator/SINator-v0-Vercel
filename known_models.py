"""
Vercel AI Gateway — Known Models Reference (via SINator-Vercel Pool)

Dieses Modul ist PURE DOKUMENTATION. Der Pool selbst erzwingt keine Allowlist —
er proxied jede Model-ID 1:1 an Vercel. Vercel validiert und antwortet mit 403
wenn das Modell für den jeweiligen Key nicht verfügbar ist.

Diese Datei dient drei Zwecken:
  1. Single Source of Truth für bekannte/testete Models
  2. Prompt-Engineering-Empfehlungen pro Model
  3. Recovery-Leitfaden (warum 403, was tun?)

Nicht für Runtime-Checks verwenden!
"""

# ── Verfügbarkeit ─────────────────────────────────────────────
# ✅  = Funktioniert auf Free Tier (getestet)
# ❌  = Blockiert auf Free Tier (403 RestrictedModelsError)
# 💰  = Paid-Only (funktioniert, kostet aber Credits)

STATUS = {
    "free":        "✅ Verfügbar auf Free Tier",
    "restricted":  "❌ Free-Tier-Block (403) — Paid Credits nötig",
    "paid_only":   "💰 Paid-Modell (funktioniert, kostet Credits)",
}

# ── Modelle ───────────────────────────────────────────────────
KNOW_N_MODELS = {
    # --- SIN-Vercel Codename: ID auf Vercel ---

    "minimax-m3": {
        "id": "minimax/minimax-m3",
        "name": "MiniMax M3",
        "status": "free",
        "context": 1_048_576,
        "output": 65_536,
        "input_price_per_m": 0.0003,      # $0.30 / 1M tokens
        "output_price_per_m": 0.0012,     # $1.20 / 1M tokens
        "modalities": ["text", "image", "pdf"],
        "reasoning": True,
        "vision": True,
        "best_for": "General-purpose, long documents, PDF understanding, vision tasks",
        "notes": "Beste Preis/Leistung im Pool. 1M Context. Für Coding + Vision + PDF.",
    },

    "grok-build": {
        "id": "xai/grok-build-0.1",
        "name": "Grok Build 0.1",
        "status": "free",
        "context": 256_000,
        "output": 256_000,
        "input_price_per_m": 0.001,       # $1.00 / 1M tokens
        "output_price_per_m": 0.002,      # $2.00 / 1M tokens
        "modalities": ["text", "image"],
        "reasoning": True,
        "vision": True,
        "tool_use": True,
        "best_for": "Agentic coding, tool-use workflows, code generation",
        "notes": "Spezialisiert auf Coding-Agenten. Weniger teuer als Flagship-Grok.",
    },

    "grok-4": {
        "id": "xai/grok-4.3",
        "name": "Grok 4.3",
        "status": "free",
        "context": 1_000_000,
        "output": 1_000_000,
        "input_price_per_m": 0.00125,     # $1.25 / 1M tokens
        "output_price_per_m": 0.0025,     # $2.50 / 1M tokens
        "modalities": ["text", "image", "file"],
        "reasoning": True,
        "vision": True,
        "tool_use": True,
        "file_input": True,
        "web_search": True,
        "best_for": "Complex reasoning, research, coding, 1M context tasks",
        "notes": "xAI Flagship. Stärkstes kostenloses Modell im Pool. 1M Context.",
    },

    "nano-banana-2": {
        "id": "google/gemini-3.1-flash-image",
        "name": "Gemini 3.1 Flash Image (Nano Banana 2)",
        "status": "free",
        "context": 131_072,
        "output": 32_768,
        "input_price_per_m": 0.0005,      # $0.50 / 1M tokens
        "image_prices": {
            "512": 0.045,
            "1K": 0.067,
            "2K": 0.101,
            "4K": 0.151,
        },
        "modalities": ["text", "image"],
        "output_modalities": ["text", "image"],
        "reasoning": True,
        "vision": True,
        "best_for": "Text-to-Image, Image-to-Image, multi-turn editing, 4K",
        "notes": (
            "NICHT über /v1/images/generations (400 Error)! "
            "Nutze /v1/chat/completions mit modalities=['text','image']. "
            "SynthID Watermark automatisch. Bis 14 Reference-Images."
        ),
    },

    # --- Known Restricted (nicht verfügbar auf Free Tier) ---
    "qwen3.7-plus": {
        "id": "alibaba/qwen3.7-plus",
        "name": "Qwen 3.7 Plus",
        "status": "restricted",
        "context": 1_000_000,
        "output": 64_000,
        "input_price_per_m": 0.0004,
        "output_price_per_m": 0.0016,
        "notes": "403 RestrictedModelsError auf Free Tier. Paid Credits nötig.",
    },

    "qwen3.7-max": {
        "id": "alibaba/qwen3.7-max",
        "name": "Qwen 3.7 Max",
        "status": "restricted",
        "context": 991_000,
        "output": 64_000,
        "input_price_per_m": 0.00125,
        "output_price_per_m": 0.00375,
        "notes": "403 RestrictedModelsError auf Free Tier. Paid Credits nötig.",
    },

    "claude-opus-4.8": {
        "id": "anthropic/claude-opus-4.8",
        "name": "Claude Opus 4.8",
        "status": "restricted",
        "context": 1_000_000,
        "output": 128_000,
        "input_price_per_m": 0.005,
        "output_price_per_m": 0.025,
        "notes": "403 RestrictedModelsError auf Free Tier. Flagship Reasoning, Paid Only.",
    },

    "gpt-5.5": {
        "id": "openai/gpt-5.5",
        "name": "GPT 5.5",
        "status": "restricted",
        "context": 1_000_000,
        "output": 128_000,
        "input_price_per_m": 0.005,
        "output_price_per_m": 0.03,
        "notes": "403 RestrictedModelsError auf Free Tier. OpenAI Flagship, Paid Only.",
    },
}

# ── Reverse Lookup: ID → Codename ──────────────────────────
ID_TO_CODENAME = {v["id"]: k for k, v in KNOW_N_MODELS.items()}


def get_model_info(codename: str) -> dict | None:
    """Get model info by SINator-Vercel codename (e.g. 'grok-4')."""
    return KNOW_N_MODELS.get(codename)


def get_model_info_by_id(model_id: str) -> dict | None:
    """Get model info by full Vercel model ID (e.g. 'xai/grok-4.3')."""
    codename = ID_TO_CODENAME.get(model_id)
    return KNOW_N_MODELS.get(codename) if codename else None


def list_available() -> list[dict]:
    """Return all models available on Free Tier (status='free')."""
    return [v for v in KNOW_N_MODELS.values() if v["status"] == "free"]


def list_restricted() -> list[dict]:
    """Return all models blocked on Free Tier."""
    return [v for v in KNOW_N_MODELS.values() if v["status"] == "restricted"]
