from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import httpx
from pool_manager import get_active_key, mark_key_cooldown, recover_expired_keys, init_db, get_pool_status

init_db()
app = FastAPI(title="SINator-VercelPool", description="Intelligenter API Key Pool für Vercel AI Gateway")

# OPTIONAL: Wenn du IP-Rotation brauchst, trage hier deine öffentlichen Proxies ein.
# Beispiel: OUTBOUND_PROXIES = {"http://": "http://user:pass@proxy-ip:port", "https://": "http://user:pass@proxy-ip:port"}
# Wenn nicht nötig, auf None lassen. Vercel rate-limitet primär über den API-Key, nicht die IP.
OUTBOUND_PROXIES = None 

# Ziel-URL anpassen (z.B. Vercel AI Gateway oder direkter OpenAI-Endpunkt über Vercel)
TARGET_BASE_URL = "https://api.vercel.ai"

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
        
        try:
            async with httpx.AsyncClient(proxies=OUTBOUND_PROXIES) as client:
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    timeout=120.0
                )
                
                response_text = resp.text
                
                # 402 (Payment Required), 429 (Too Many Requests), 403 (Forbidden) 
                # oder spezifische Credit-Fehlermeldungen
                is_credit_error = any(phrase in response_text.lower() for phrase in [
                    "insufficient credits",
                    "spending limit",
                    "rate limit",
                    "quota exceeded",
                    "billing",
                    "payment required"
                ])
                
                if resp.status_code in [402, 429, 403] or is_credit_error:
                    mark_key_cooldown(api_key)
                    last_error = response_text
                    continue  # Sofortiger interner Retry mit dem nächsten Key!
                
                # Erfolgreich oder nicht retry-barer Fehler -> direkt an Client zurückgeben
                # Filter response headers
                response_headers = {}
                for key, value in resp.headers.items():
                    if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']:
                        response_headers[key] = value
                
                return Response(
                    content=resp.content, 
                    status_code=resp.status_code, 
                    headers=response_headers
                )
                
        except httpx.TimeoutException:
            last_error = "Request timeout"
            continue
        except Exception as e:
            # Bei Netzwerkfehlern Key sicherheitshalber auch auf Cooldown setzen und weitermachen
            mark_key_cooldown(api_key)
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
