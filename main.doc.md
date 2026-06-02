# main.py — Vercel AI Gateway Key-Pool Proxy

## Was diese Datei tut

FastAPI-App, die als intelligenter Reverse-Proxy vor der Vercel AI Gateway läuft. Sie verwaltet einen Pool von Vercel API-Keys (SQLite-backed) und rotiert automatisch bei Rate-Limits oder erschöpften Credits. Clients (z.B. opencode) sehen den Pool als normalen OpenAI-kompatiblen Endpunkt — der Pool injiziert den realen Key transparent pro Request.

## Dependency Map

| Importiert von | Was |
|---|---|
| `pool_manager` | Key-Lookup (LRU), Cooldown-Markierung, DB-Init, Status |
| `fastapi` | HTTP-Framework (app, Request, Response, Streaming) |
| `httpx` | Async HTTP-Client für Upstream-Calls zu Vercel |

Wird konsumiert von: opencode (Provider `vercel-pool` → `http://localhost:8001/v1`)

## Wichtige Konfiguration

| Konstante | Wert | Bedeutung |
|---|---|---|
| `TARGET_BASE_URL` | `https://ai-gateway.vercel.sh` | Vercel AI Gateway Endpunkt (**NICHT** `api.vercel.ai` — das ist für Deployments und antwortet mit `DEPLOYMENT_NOT_FOUND`) |
| `RATE_LIMIT_COOLDOWN_MINUTES` | `2` | Wie lange ein Key bei transientem Rate-Limit pausiert wird, bevor er wieder in den Pool rotiert |
| `OUTBOUND_PROXY` | `os.getenv("OUTBOUND_PROXY") or None` | Optional: HTTP/SOCKS Proxy für IP-Rotation (Vercel rate-limitet primär über API-Key, nicht IP) |

## Design-Entscheidungen

### 1. `aiter_bytes()` statt `aiter_raw()`
- `aiter_raw()` yieldet rohe HTTP-Chunks inkl. gzip-Binary
- `aiter_bytes()` dekodiert automatisch via httpx
- Mit `aiter_raw()` sah der Client `0x1f8b08...` Magic-Bytes statt JSON

### 2. Streaming statt Buffering
- `aiter_bytes()` in `stream_body()` yieldet Chunk-für-Chunk
- opencode sieht Tokens sofort fließen, nicht erst am Ende
- Response + Client werden erst geschlossen wenn Stream komplett durch ist

### 3. Max 10 Retries
- Bei 402/403/429 wird der aktuelle Key in Cooldown geschickt und sofort der nächste probiert
- Client wartet NICHT auf Retry-After — Pool swapt transparent
- 10 Versuche decken selbst Worst-Case (alle Keys in Cooldown) ab

### 4. Zwei Cooldown-Modi
- **Long (31 Tage):** Credits aufgebraucht (`402 Payment Required`, "insufficient credits", "quota exceeded")
- **Short (2 Min):** Transientes Rate-Limit ("rate-limited", "upgrade to paid") — Key ist nicht tot, nur überlastet

## API Endpoints

| Endpoint | Methode | Zweck |
|---|---|---|
| `/` | GET | Service-Info + Pool-Status (compact) |
| `/health` | GET | Health-Check |
| `/pool/status` | GET | Detaillierter Pool-Status (active, cooldown, by reason) |
| `/v1/{path:path}` | ANY | Proxy zu `https://ai-gateway.vercel.sh/v1/{path}` |

## Fehler-Klassifizierung (`classify_error`)

Reihenfolge ist wichtig (Credits werden VOR Rate-Limit geprüft):
1. **Credits** (`insufficient_credits`, `spending_limit`, `quota_exceeded`, `402`) → 31 Tage
2. **Rate-Limit** (`rate_limited`, `free_tier`, `429`) → 2 Min
3. **403** (mehrdeutig: Key gesperrt oder abgelaufen) → konservativ 31 Tage

## Usage

```bash
# Lokal starten (Port 8001)
uvicorn main:app --host 0.0.0.0 --port 8001

# Mit Cloudflare Tunnel exponieren
cloudflared tunnel run sinator
# → https://sinatorpool-router.delqhi.com → :8001
```

Client (opencode) Konfiguration:
```json
{
  "provider": {
    "vercel-pool": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8001/v1",
        "apiKey": "dummy"
      }
    }
  }
}
```

## Bekannte Footguns

- **Port 8000 belegt:** SINator-fireworksai Backend läuft dort. SINator-Vercel **MUSS** auf 8001.
- **Gzip im Stream:** Siehe `aiter_bytes` Entscheidung oben — niemals zurück auf `aiter_raw()`.
- **`api.vercel.ai` vs `ai-gateway.vercel.sh`:** Ersteres ist Vercel-Deployments, gibt `DEPLOYMENT_NOT_FOUND` für Chat. Letzteres ist AI Gateway.
- **Verifizierung via Pool:** Bei `503` immer zuerst `/pool/status` checken — wenn alle 64 Keys in Cooldown sind, ist der Pool "leer".
