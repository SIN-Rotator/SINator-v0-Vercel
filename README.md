# SINator-VercelPool

Intelligenter API Key Pool Router für Vercel AI Gateway mit automatischer 31-Tage-Cooldown-Rotation.

## Architektur

```
opencode CLI / Client
  ↓ (sendet Request an lokale/öffentliche URL)
Cloudflare Tunnel (cloudflared)
  ↓ (leitet weiter an lokalen Port)
SINator-VercelPool Router (FastAPI, Port 17341)
  ↓ 1. Holt aktiven Key aus SQLite-Datenbank (LRU)
  ↓ 2. Sendet Request an Vercel AI Gateway
  ↓ 3. Bei 429/402/403: Markiert Key als "Cooldown (31 Tage)" und retryt SOFORT
  ↓ (gibt erfolgreiche Antwort zurück – Client merkt nichts)
SQLite Datenbank (vercel_pool.db)
  └── Zustände: 'active' oder 'cooldown' (mit Ablaufdatum)
```

## Features

- ✅ **Transparenter Auto-Failover**: Client wartet nicht bei erschöpften Keys
- ✅ **31-Tage-Wartebank**: Automatische Reaktivierung nach Credit-Reset
- ✅ **Kein Löschen**: Keys werden nie gelöscht, nur rotiert
- ✅ **LRU-Strategie**: Gleichmäßige Verteilung über alle aktiven Keys
- ✅ **Optional: Outbound Proxies** für IP-Rotation

## Installation

```bash
pip install -r requirements.txt
```

## Keys hinzufügen

```bash
# Aus Datei (ein Key pro Zeile)
python add_keys.py keys.txt

# Einzelner Key
python add_keys.py --key YOUR_VERCEL_API_KEY

# Status anzeigen
python add_keys.py --status
```

## Starten

```bash
# Entwicklung
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Produktion
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Cloudflare Tunnel (für öffentlichen Zugriff)

```bash
# Temporär (für Tests)
cloudflared tunnel --url http://localhost:17341

# Dauerhaft (nach Tunnel-Setup in Cloudflare Dashboard)
cloudflared tunnel run your-tunnel-name
```

## API Endpoints

| Endpoint | Beschreibung |
|----------|-------------|
| `GET /` | Service-Info und Pool-Status |
| `GET /health` | Health Check |
| `GET /pool/status` | Detaillierter Pool-Status |
| `* /v1/*` | Proxy zu Vercel AI Gateway |

## Verfügbare Modelle

Siehe `known_models.py` für die vollständige Liste mit Preisen, Context-Limits
und Prompt-Tipps pro Modell.

### ✅ Free Tier — funktioniert sofort

| SINator-Vercel | Vercel Model ID | Context | Input $/M | Output $/M | Stärken |
|---|---|---|---:|---:|---|
| `minimax-m3` | `minimax/minimax-m3` | 1M | $0.30 | $1.20 | Bestes Preis/Leistung, Vision+PDF |
| `grok-build` | `xai/grok-build-0.1` | 256K | $1.00 | $2.00 | Agentic Coding, Tool-Use |
| `grok-4` | `xai/grok-4.3` | 1M | $1.25 | $2.50 | xAI Flagship, Reasoning+Vision+Files |
| `nano-banana-2` | `google/gemini-3.1-flash-image` | 131K | $0.50 | — | Text→/Image→Image, 4K Edit |

### ❌ Free Tier Block — Paid Only

| Vercel Model ID | Grund |
|---|---|
| `alibaba/qwen3.7-plus` | 403 RestrictedModelsError |
| `alibaba/qwen3.7-max` | 403 RestrictedModelsError |
| `anthropic/claude-opus-4.8` | 403 RestrictedModelsError |
| `openai/gpt-5.5` | 403 RestrictedModelsError |

### Nutzung

```bash
# Über Pool (alle Models)
curl -s http://localhost:17341/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"xai/grok-4.3","messages":[{"role":"user","content":"Hi"}]}'

# Pool-Status
curl -s http://localhost:17341/pool/status | python3 -m json.tool
```

---

## Client-Konfiguration (opencode)

```json
{
  "provider": {
    "vercel-pool": {
      "type": "openai",
      "baseURL": "https://your-tunnel.trycloudflare.com/v1",
      "apiKey": "dummy"
    }
  }
}
```

## Konfiguration

In `main.py`:

```python
# Ziel-API (Standard: Vercel AI Gateway)
TARGET_BASE_URL = "https://api.vercel.ai"

# Optional: Outbound Proxies für IP-Rotation
OUTBOUND_PROXIES = {
    "http://": "http://user:pass@proxy:port",
    "https://": "http://user:pass@proxy:port"
}
```

## Lizenz

MIT
