from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from pool_manager import (
    get_active_key,
    mark_key_long_cooldown,
    mark_key_short_cooldown,
    recover_expired_keys,
    init_db,
    get_pool_status,
)

init_db()
app = FastAPI(title="SINator-VercelPool", description="Intelligenter API Key Pool für Vercel AI Gateway")

# OPTIONAL: Wenn du IP-Rotation brauchst, trage hier eine Proxy-URL ein.
# Beispiel: OUTBOUND_PROXY = "http://user:pass@proxy-ip:port" oder "socks5://host:port"
# Wenn nicht nötig, auf None lassen. Vercel rate-limitet primär über den API-Key, nicht die IP.
# Hinweis: ab httpx 0.28 heißt das Argument 'proxy' (einzelne URL), nicht mehr 'proxies'.
import os
OUTBOUND_PROXY = os.getenv("OUTBOUND_PROXY") or None

# Ziel-URL anpassen (z.B. Vercel AI Gateway oder direkter OpenAI-Endpunkt über Vercel)
TARGET_BASE_URL = "https://api.vercel.ai"

# Wie lange ein Key bei einem transienten Rate-Limit kurz pausiert wird (Minuten).
RATE_LIMIT_COOLDOWN_MINUTES = 2

# --- Fehler-Klassifizierung -------------------------------------------------
# Wir müssen ZWEI Fälle sauber unterscheiden:
#
# 1) CREDITS AUFGEBRAUCHT  -> Key 31 Tage archivieren (mark_key_long_cooldown)
#    Typisch: Billing/Quota/Spending-Limit erreicht. Warten bringt kurzfristig nichts.
#
# 2) RATE-LIMIT / FREE-TIER WARTEN -> Key nur kurz pausieren (mark_key_short_cooldown)
#    Typisch: "Free tier requests are rate-limited", "retrying in 25s", "upgrade to paid".
#    Credits sind NICHT aufgebraucht – man müsste nur warten. Wir warten NICHT,
#    sondern swappen sofort den nächsten Key und holen diesen Key in 2 Min zurück.

# Phrasen, die eindeutig auf AUFGEBRAUCHTE CREDITS / BILLING hindeuten -> 31 Tage
CREDITS_EXHAUSTED_PHRASES = [
    "insufficient credits",
    "insufficient funds",
    "spending limit",
    "quota exceeded",
    "billing",
    "payment required",
    "exceeded your current quota",
    "out of credits",
    "no credits",
    "credit balance",
]

# Phrasen, die auf ein transientes RATE-LIMIT hindeuten (Credits noch da) -> kurz
RATE_LIMIT_PHRASES = [
    "rate-limited",
    "rate limited",
    "rate limit",
    "free tier",
    "free-tier",
    "upgrade to paid",
    "too many requests",
    "retry",
    "try again",
    "slow down",
    "temporarily",
]


def classify_error(status_code: int, body_text: str) -> str:
    """
    Liefert: 'credits' (31 Tage), 'rate_limit' (kurz) oder 'none' (kein Pool-Fehler).
    Reihenfolge ist wichtig: Credits werden VOR Rate-Limit geprüft, da eine
    Antwort beide Wörter enthalten kann (z.B. 'quota' + 'rate limit').
    """
    text = (body_text or "").lower()

    # 1) Credits/Billing zuerst -> langer Cooldown
    if any(p in text for p in CREDITS_EXHAUSTED_PHRASES):
        return "credits"

    # 2) 402 Payment Required ist fast immer ein echtes Billing-/Credit-Problem
    if status_code == 402:
        return "credits"

    # 3) Transientes Rate-Limit -> kurzer Cooldown
    if status_code == 429:
        return "rate_limit"
    if any(p in text for p in RATE_LIMIT_PHRASES):
        return "rate_limit"

    # 4) 403 ist mehrdeutig: oft gesperrter/abgelaufener Key -> sicherheitshalber lang
    if status_code == 403:
        return "credits"

    return "none"

@app.get("/")
async def root():
    status = get_pool_status()
    return {
        "service": "SINator-VercelPool",
        "status": "running",
        "pool": status,
        "info": "Intelligenter API Key Pool mit 31-Tage-Cooldown-Rotation"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/pool/status")
async def pool_status():
    recover_expired_keys()
    return get_pool_status()

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(path: str, request: Request):
    recover_expired_keys()  # Prüfe bei jedem Request, ob Keys aus der Wartebank zurückkehren dürfen
    
    body = await request.body()
    headers = dict(request.headers)
    
    # Bereinige Header, die wir selbst setzen
    headers.pop("host", None)
    headers.pop("authorization", None)
    headers.pop("content-length", None)
    
    max_retries = 10  # Versuche bis zu 10 verschiedene Keys nacheinander
    last_error = None
    
    for attempt in range(max_retries):
        api_key = get_active_key()
        if not api_key:
            return JSONResponse(
                content={
                    "error": "Keine aktiven API Keys im Pool verfügbar. Alle im 31-Tage-Cooldown.",
                    "pool_status": get_pool_status()
                }, 
                status_code=503
            )
        
        headers["authorization"] = f"Bearer {api_key}"
        target_url = f"{TARGET_BASE_URL}/v1/{path}"
        
        # Client wird NICHT mit 'async with' geschlossen, da er bei Erfolg
        # während des Streamings offen bleiben muss. Wir schließen ihn manuell:
        # - bei Fehler/Retry sofort
        # - bei Erfolg erst, wenn der Stream zu Ende ist (im Generator unten)
        client = httpx.AsyncClient(proxy=OUTBOUND_PROXY, timeout=120.0)
        try:
            # Streaming-Request öffnen: Header/Status kommen SOFORT, der Body wird
            # erst beim Durchlaufen geladen (kein Puffern der kompletten Antwort).
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
            resp = await client.send(req, stream=True)
            
            # Bei Fehler-Status den (kurzen) Body lesen, klassifizieren und ggf. retrien.
            if resp.status_code >= 400:
                error_body = (await resp.aread()).decode("utf-8", errors="replace")
                await resp.aclose()
                await client.aclose()
                
                error_kind = classify_error(resp.status_code, error_body)
                
                if error_kind == "credits":
                    # Credits aufgebraucht / Billing -> Key 31 Tage archivieren
                    mark_key_long_cooldown(api_key)
                    last_error = error_body
                    continue  # Sofortiger interner Retry mit dem nächsten Key!
                
                if error_kind == "rate_limit":
                    # Transientes Rate-Limit -> Key nur kurz pausieren, NICHT warten.
                    # Wir swappen sofort auf den nächsten Key, damit opencode weiterläuft.
                    mark_key_short_cooldown(api_key, minutes=RATE_LIMIT_COOLDOWN_MINUTES)
                    last_error = error_body
                    continue  # Sofortiger interner Retry mit dem nächsten Key!
                
                # Nicht retry-barer Fehler (z.B. 400 Bad Request) -> direkt zurückgeben
                response_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
                }
                return Response(
                    content=error_body.encode("utf-8"),
                    status_code=resp.status_code,
                    headers=response_headers,
                )
            
            # ERFOLG (2xx): Antwort Token-für-Token durchstreamen, ohne zu puffern.
            # opencode sieht die Antwort sofort fließen statt erst am Ende.
            response_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
            }
            
            async def stream_body():
                # Client + Response erst schließen, wenn der Stream komplett durch ist.
                try:
                    async for chunk in resp.aiter_raw():
                        yield chunk
                finally:
                    await resp.aclose()
                    await client.aclose()
            
            return StreamingResponse(
                stream_body(),
                status_code=resp.status_code,
                headers=response_headers,
                media_type=resp.headers.get("content-type"),
            )
                
        except httpx.TimeoutException:
            # Timeout liegt meist am Zielserver, nicht am Key -> kurzer Cooldown,
            # damit der Key bald wieder mitspielt.
            await client.aclose()
            mark_key_short_cooldown(api_key, minutes=RATE_LIMIT_COOLDOWN_MINUTES)
            last_error = "Request timeout"
            continue
        except Exception as e:
            # Netzwerkfehler ist kein Credit-Problem -> kurzer Cooldown, weitermachen
            await client.aclose()
            mark_key_short_cooldown(api_key, minutes=RATE_LIMIT_COOLDOWN_MINUTES)
            last_error = str(e)
            continue
            
    return JSONResponse(
        content={
            "error": "Alle verfügbaren Keys haben ihr Limit erreicht oder sind temporär gesperrt.",
            "last_error": last_error,
            "pool_status": get_pool_status()
        }, 
        status_code=503
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
