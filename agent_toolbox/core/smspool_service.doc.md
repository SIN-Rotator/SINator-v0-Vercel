# smspool_service.py

Docs: smspool_service.doc.md

## What
SMSPool integration for temporary UK phone numbers and OTP polling. ~8 cents per UK number.

## Dependencies
- `httpx`

## API Endpoints
- `POST /purchase/sms` — order number
- `GET /sms/check` — poll SMS status
- `GET /sms/cancel` — cancel order

## Key Methods
- `order_uk_number(service)` — orders UK number for a given service
- `poll_otp(order_id, timeout, interval)` — polls until OTP arrives or timeout

## Configuration
- `SMSPOOL_API_KEY` env var or constructor parameter
- `DEFAULT_COUNTRY_ID = "16"` (UK)
- `DEFAULT_SERVICE = "vercel"` (may need adjustment based on SMSPool service list)

## Response Format
Expected JSON fields from SMSPool:
- `order_id` / `id`
- `number` / `phonenumber` / `phone`
- `status` / `sms` / `message`
- `code` / `otp` / `sms_content`

## Known Issues
- SMSPool service name for Vercel may differ (verify via `get_services()`)
- Some APIs return OTP in `message` field instead of `code`
