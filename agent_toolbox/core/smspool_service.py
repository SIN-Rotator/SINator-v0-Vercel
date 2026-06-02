"""
SINator v0+Vercel — SMSPool Service
Docs: smspool_service.doc.md

UK-Handynummer-Bestellung und OTP-Abfrage via SMSPool API.
Kosten: ~8 Cent pro UK-Nummer.

API-Dokumentation: https://www.smspool.net/articles/api-documentation
"""
import time
import logging
import asyncio
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

SMSPOOL_BASE_URL = "https://api.smspool.net"
# Default country ID for UK = 16 (verify via /country/16)
DEFAULT_COUNTRY_ID = "16"
# Default service ID for Vercel (need to check SMSPool services, generic "vercel" or other)
# If unknown, we can use a generic service or fetch available services.
DEFAULT_SERVICE = "vercel"  # May need adjustment based on SMSPool service list


class SMSPoolService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{SMSPOOL_BASE_URL}{endpoint}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            if method.upper() == "GET":
                r = await self.client.get(url, params=params, headers=headers)
            else:
                r = await self.client.post(url, data=data, params=params, headers=headers)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {"text": r.text, "status_code": r.status_code}
        except httpx.HTTPStatusError as e:
            logger.error(f"SMSPool HTTP error: {e.response.status_code} {e.response.text[:200]}")
            return {"error": f"HTTP {e.response.status_code}", "text": e.response.text}
        except Exception as e:
            logger.error(f"SMSPool request error: {e}")
            return {"error": str(e)}

    async def get_balance(self) -> Dict[str, Any]:
        """Check SMSPool account balance."""
        return await self._request("GET", "/request/balance")

    async def get_services(self) -> Dict[str, Any]:
        """List available SMSPool services."""
        return await self._request("GET", "/service/retrieve_all")

    async def order_uk_number(self, service: Optional[str] = None) -> Dict[str, Any]:
        """Order a UK phone number for receiving an OTP.

        Returns dict with keys: number, order_id, success
        """
        svc = service or DEFAULT_SERVICE
        logger.info(f"[SMSPool] Ordering UK number for service='{svc}'")
        data = {
            "country_id": DEFAULT_COUNTRY_ID,
            "service": svc,
        }
        if self.api_key:
            data["key"] = self.api_key
        result = await self._request("POST", "/purchase/sms", data=data)
        if "error" in result:
            logger.error(f"[SMSPool] Order failed: {result}")
            return {"success": False, "error": result.get("error"), "raw": result}
        # Expected response fields: order_id, number, country_id, service, expires_in, cost
        number = result.get("number") or result.get("phonenumber") or result.get("phone")
        order_id = result.get("order_id") or result.get("id")
        if not number or not order_id:
            logger.warning(f"[SMSPool] Unexpected response format: {result}")
            return {"success": False, "error": "unexpected_format", "raw": result}
        logger.info(f"[SMSPool] Ordered number {number}, order_id={order_id}")
        return {"success": True, "number": number, "order_id": str(order_id), "raw": result}

    async def get_sms(self, order_id: str) -> Dict[str, Any]:
        """Check SMS status for an order."""
        params = {"orderid": order_id}
        if self.api_key:
            params["key"] = self.api_key
        return await self._request("GET", "/sms/check", params=params)

    async def poll_otp(self, order_id: str, timeout: int = 120, interval: int = 5) -> Optional[str]:
        """Poll SMSPool for OTP code until timeout.

        Returns the 6-digit OTP code or None if timeout.
        """
        logger.info(f"[SMSPool] Polling OTP for order_id={order_id} (timeout={timeout}s)")
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = await self.get_sms(order_id)
            if "error" in result:
                logger.warning(f"[SMSPool] Poll error: {result}")
            else:
                status = result.get("status") or result.get("sms") or result.get("message")
                if status and str(status).lower() in ["completed", "done", "received"]:
                    otp = result.get("code") or result.get("otp") or result.get("sms")
                    if otp:
                        logger.info(f"[SMSPool] OTP received: {otp}")
                        return str(otp).strip()
                # Some APIs return the OTP in a message field
                msg = result.get("message") or result.get("sms_content") or ""
                # Extract 6-digit code from message
                import re
                m = re.search(r"\b\d{6}\b", str(msg))
                if m:
                    logger.info(f"[SMSPool] OTP extracted from message: {m.group(0)}")
                    return m.group(0)
            remaining = deadline - time.time()
            sleep_t = min(interval, max(1, remaining))
            logger.info(f"[SMSPool] No OTP yet, waiting {sleep_t:.0f}s...")
            await asyncio.sleep(sleep_t)
        logger.warning("[SMSPool] OTP poll timeout")
        return None

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an SMSPool order (if supported)."""
        params = {"orderid": order_id}
        if self.api_key:
            params["key"] = self.api_key
        return await self._request("GET", "/sms/cancel", params=params)

    async def close(self):
        await self.client.aclose()
