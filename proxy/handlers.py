"""
Pool Proxy request handlers — proxy forwarding, SSE streaming, model list.

Docs: handlers.doc.md
"""
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import web

logger = logging.getLogger("pool-proxy")


class ProxyHandlersMixin:
    """Mixin for HTTP request handling and Fireworks proxying."""

    MODEL_CACHE_PATH = Path.home() / ".hermes" / "models_dev_cache.json"

    async def _handle_proxy(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _handle_proxy_v1(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    def _load_all_model_ids(self) -> list[str]:
        """Load all Fireworks model IDs from the models.dev cache (or fallback)."""
        try:
            raw = self.MODEL_CACHE_PATH.read_text()
            registry = json.loads(raw)
            fw = registry.get("fireworks-ai", {})
            return list(fw.get("models", {}).keys())
        except Exception:
            return [
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/deepseek-v4-pro",
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/gpt-oss-20b",
                "accounts/fireworks/models/kimi-k2p5",
                "accounts/fireworks/models/kimi-k2p6",
                "accounts/fireworks/models/minimax-m2p5",
                "accounts/fireworks/models/minimax-m2p7",
                "accounts/fireworks/models/qwen3p6-plus",
                "accounts/fireworks/routers/glm-5p1-fast",
                "accounts/fireworks/routers/kimi-k2p6-turbo",
            ]

    @staticmethod
    def _build_model_alias_map(model_ids: list[str]) -> dict[str, str]:
        """Build short_name → full_path lookup for all model IDs."""
        m = {}
        for mid in model_ids:
            parts = mid.split("/")
            short = parts[-1]  # e.g. "glm-5p1-fast", "deepseek-v4-flash"
            m[short] = mid
        return m

    async def _normalize_request_body(self, body: Optional[bytes]) -> Optional[bytes]:
        """Normalize model name in request body — expand short names to full paths."""
        if not body:
            return body
        try:
            parsed = json.loads(body)
        except Exception:
            return body
        model = parsed.get("model", "")
        if not model or "/" in model:
            return body
        model_ids = self._load_all_model_ids()
        alias_map = self._build_model_alias_map(model_ids)
        full = alias_map.get(model)
        if full and full != model:
            parsed["model"] = full
            logger.debug(f"Normalized model: {model} → {full}")
            return json.dumps(parsed).encode()
        return body

    async def _handle_v1_models(self, request: web.Request) -> web.Response:
        """Return all Fireworks models from the models.dev cache.

        Reads the community-maintained models.dev registry on disk
        (``~/.hermes/models_dev_cache.json``) to list ALL Fireworks
        models and routers — not just the subset the current pool key
        can access.

        Falls back to a curated subset if the cache is unavailable.
        """
        model_ids = self._load_all_model_ids()
        now = int(time.time())
        data = [
            {"id": m, "object": "model", "created": now, "owned_by": "fireworks"}
            for m in sorted(model_ids)
        ]
        return web.json_response({"object": "list", "data": data})

    async def _do_proxy(self, request: web.Request, fw_url: str) -> web.Response:
        # V19.14 Phase 2: Per-session key assignment via x-agent-id header
        session_agent_id = request.headers.get("x-agent-id", self.agent_id)
        key_info = await self._ensure_key_with_retry(agent_id=session_agent_id)
        if not key_info:
            return web.json_response(
                {"error": "no_api_key", "message": "No API key available in pool"},
                status=503,
            )

        headers = self._build_forward_headers(request, key_info)
        is_sse = self._is_streaming_request(request, fw_url)
        consecutive_swaps = 0

        for attempt in range(self.max_retries):
            try:
                req_body = await request.read() if request.method in ("POST", "PUT", "PATCH") else None
                req_body = await self._normalize_request_body(req_body)

                async with self._make_fw_request(request.method, fw_url, headers, req_body, request.query) as fw_resp:
                    status = fw_resp.status

                    if status in getattr(self, "DEAD_KEY_CODES", set()):
                        error_body_bytes = await fw_resp.read()
                        error_text = error_body_bytes.decode(errors="replace").lower()

                        consecutive_swaps += 1
                        max_consecutive = getattr(self, "MAX_CONSECUTIVE_SWAPS", 2)
                        if consecutive_swaps > max_consecutive:
                            logger.error(f"Cascade stop: {consecutive_swaps} swaps, returning error")
                            return web.Response(body=error_body_bytes, status=status,
                                                content_type=fw_resp.headers.get("Content-Type", "application/json"))
                        reason = getattr(self, "SWAP_REASONS", {}).get(status, "unknown")
                        if status in getattr(self, "MAYBE_DEAD_CODES", set()):
                            # Prüfe Response-Body auf echte Dead-Keywords
                            permanent_error_keywords = getattr(self, "PERMANENT_ERROR_KEYWORDS", ())
                            is_confirmed_dead = any(kw in error_text for kw in permanent_error_keywords)
                            if is_confirmed_dead:
                                logger.info(f"Confirmed dead via error body: {status} ({reason}) — matched keyword in response, swapping immediately")
                                new_key = await self._swap_key(reason)
                                if new_key and attempt < self.max_retries - 1:
                                    headers["Authorization"] = f"Bearer {new_key['api_key']}"
                                    return web.Response(
                                        body=b'{"error":"key_swapped","message":"Pool key rotated, please retry","retry_after":1}',
                                        status=503,
                                        content_type="application/json",
                                        headers={"Retry-After": "1"},
                                    )
                                return web.Response(body=error_body_bytes, status=status,
                                                    content_type=fw_resp.headers.get("Content-Type", "application/json"))
                            # Body-Keywords matchten nicht — zusätzlich via /models verifizieren
                            models_dead = await self._verify_key_dead(key_info['api_key'])
                            if not models_dead:
                                logger.warning(f"Key got {status} but error body + /models don't confirm dead — retrying same key")
                                await asyncio.sleep(2)
                                continue
                        logger.warning(f"Dead key: {status} ({reason}), swapping (attempt {attempt+1})...")
                        new_key = await self._swap_key(reason)
                        if new_key and attempt < self.max_retries - 1:
                            headers["Authorization"] = f"Bearer {new_key['api_key']}"
                            # Key wurde intern getauscht — sag dem Client er soll retryen
                            return web.Response(
                                body=b'{"error":"key_swapped","message":"Pool key rotated, please retry","retry_after":1}',
                                status=503,
                                content_type="application/json",
                                headers={"Retry-After": "1"},
                            )
                        return web.Response(body=error_body_bytes, status=status,
                                            content_type=fw_resp.headers.get("Content-Type", "application/json"))

                    if status == 429:
                        error_text = await fw_resp.text()
                        permanent_429_keywords = getattr(self, "PERMANENT_429_KEYWORDS", ())
                        is_permanent = any(kw in error_text.lower() for kw in permanent_429_keywords)
                        if is_permanent:
                            consecutive_swaps += 1
                            if consecutive_swaps > max_consecutive:
                                logger.error(f"Cascade stop: {consecutive_swaps} swaps for permanent 429")
                                return web.Response(body=error_text.encode(), status=429,
                                                    content_type="application/json")
                            logger.warning(f"Permanent 429 (spending limit matched: {[kw for kw in permanent_429_keywords if kw in error_text.lower()]}), swapping...")
                            new_key = await self._swap_key("rate_limited_permanent")
                            if new_key and attempt < self.max_retries - 1:
                                headers["Authorization"] = f"Bearer {new_key['api_key']}"
                                # Intern getauscht — Client retryen
                                return web.Response(
                                    body=b'{"error":"key_rotated","message":"Rate limit reached, key rotated. Retry now.","retry_after":1}',
                                    status=503,
                                    content_type="application/json",
                                    headers={"Retry-After": "1"},
                                )
                            return web.Response(body=error_text.encode(), status=429,
                                                content_type="application/json")
                        # Transientes 429 — SOFORT an Client zurückgeben mit Retry-After
                        # (nicht intern warten — verhindert Client-Timeouts + InvalidHTTPResponse)
                        retry_after = fw_resp.headers.get("Retry-After", "5")
                        try:
                            wait = min(int(retry_after), 30)
                        except ValueError:
                            wait = 5
                        logger.info(f"Temporary 429, returning to client with Retry-After: {wait}s")
                        return web.Response(
                            body=error_text.encode(),
                            status=429,
                            content_type=fw_resp.headers.get("Content-Type", "application/json"),
                            headers={"Retry-After": str(wait)},
                        )

                    if status >= 500:
                        logger.warning(f"Fireworks server error: {status}, retrying (attempt {attempt+1})...")
                        await asyncio.sleep(2)
                        continue

                    if is_sse and status == 200:
                        return await self._stream_sse(request, fw_resp)

                    body = await fw_resp.read()
                    resp = web.Response(body=body, status=status)
                    for k, v in fw_resp.headers.items():
                        kl = k.lower()
                        if kl not in ("transfer-encoding", "content-encoding", "connection"):
                            resp.headers[k] = v
                    return resp

            except asyncio.TimeoutError:
                logger.warning(f"Fireworks timeout (attempt {attempt+1})")
                continue
            except aiohttp.ClientError as e:
                logger.warning(f"Fireworks connection error: {e}")
                await asyncio.sleep(2)
                continue

        return web.json_response(
            {"error": "max_retries_exceeded", "message": f"Failed after {self.max_retries} attempts"},
            status=502,
        )

    @staticmethod
    def _build_forward_headers(request: web.Request, key_info: dict) -> dict:
        headers = {}
        for k, v in request.headers.items():
            kl = k.lower()
            if kl in ("host", "authorization", "content-length", "transfer-encoding", "x-api-key"):
                continue
            headers[k] = v
        headers["Authorization"] = f"Bearer {key_info['api_key']}"
        headers["Host"] = "api.fireworks.ai"
        return headers

    def _make_fw_request(self, method: str, url: str, headers: dict,
                         body: Optional[bytes], query: dict):
        if method == "GET":
            return self.fw_session.get(url, headers=headers, params=query)
        elif method == "POST":
            return self.fw_session.post(url, headers=headers, data=body)
        elif method == "PUT":
            return self.fw_session.put(url, headers=headers, data=body)
        elif method == "PATCH":
            return self.fw_session.patch(url, headers=headers, data=body)
        elif method == "DELETE":
            return self.fw_session.delete(url, headers=headers)
        return self.fw_session.get(url, headers=headers)

    @staticmethod
    def _is_streaming_request(request: web.Request, path: str) -> bool:
        accept = request.headers.get("Accept", "")
        if "text/event-stream" in accept:
            return True
        if "/chat/completions" in path or "/completions" in path:
            return True
        return False

    async def _stream_sse(self, request: web.Request, fw_resp) -> web.Response:
        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": fw_resp.headers.get("Content-Type", "text/event-stream"),
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)
        try:
            async for chunk in fw_resp.content.iter_chunked(4096):
                await resp.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        await resp.write_eof()
        return resp
