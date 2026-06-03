#!/bin/bash
# Start Bot Chrome on port 9230 for SINator v0+Vercel rotator
# Uses a clean temp profile — no User Chrome tabs, no GMX session assumptions.

PORT=9230
PROFILE="/tmp/sinator-vercel-chrome-$(date +%s)"

mkdir -p "$PROFILE"

echo "Starting Bot Chrome on port $PORT (profile: $PROFILE)..."

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins="*" \
  --no-first-run \
  --no-default-browser-check \
  --disable-sync \
  --no-experiments \
  --user-data-dir="$PROFILE" \
  "https://www.gmx.net" &>/tmp/sinator-bot-chrome.log &

BOT_PID=$!
echo "Bot Chrome PID: $BOT_PID"

# Wait for CDP to be ready
for i in $(seq 1 15); do
  if curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
    echo "✅ Chrome ready on port $PORT"
    echo "export CDP_PORT=$PORT"
    echo "export BOT_CHROME_PID=$BOT_PID"
    exit 0
  fi
  sleep 1
done

echo "❌ Chrome did not start within 15s"
exit 1
