#!/bin/bash
# SINator Install Script — one command to rule them all
# curl -fsSL https://raw.githubusercontent.com/SIN-Rotator/SINator-FireworksAI/main/tools/install.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}══════════════════════════════════════${NC}"
echo -e "${CYAN}  SINator Fireworks AI — Installer   ${NC}"
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo ""

SINATOR_DIR="${HOME}/sinator-fireworksai"

# 1. Clone repos
if [ ! -d "$SINATOR_DIR" ]; then
    echo -e "${GREEN}→${NC} Cloning SINator-FireworksAI..."
    git clone https://github.com/SIN-Rotator/SINator-FireworksAI "$SINATOR_DIR"
else
    echo -e "${GREEN}→${NC} SINator already exists, updating..."
    cd "$SINATOR_DIR" && git pull
fi

# 2. Install Python deps
echo -e "${GREEN}→${NC} Installing Python dependencies..."
cd "$SINATOR_DIR"
pip3 install -q fastapi uvicorn httpx playwright 2>/dev/null
python3 -m playwright install chromium 2>/dev/null || true

# 3. Start backend
echo -e "${GREEN}→${NC} Starting backend on port 8000..."
nohup python3 agent_toolbox/start_toolbox.py > /tmp/sinator-backend.log 2>&1 &
sleep 3

# 4. Get auth token
TOKEN=$(grep "Auth-Token" /tmp/sinator-backend.log | tail -1 | awk '{print $NF}')
echo -e "${GREEN}→${NC} Auth Token: ${TOKEN}"
echo ""

# 5. Install & start dashboard
DASHBOARD_DIR="${HOME}/sinator-dashboard"
if [ ! -d "$DASHBOARD_DIR" ]; then
    echo -e "${GREEN}→${NC} Cloning SINator-dashboard..."
    git clone https://github.com/SIN-Rotator/SINator-dashboard "$DASHBOARD_DIR"
fi

echo -e "${GREEN}→${NC} Installing dashboard dependencies..."
cd "$DASHBOARD_DIR"
pnpm install --silent 2>/dev/null || npm install --silent 2>/dev/null

# 6. Start Cloudflare Tunnel
echo -e "${GREEN}→${NC} Starting Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://localhost:3000 > /tmp/sinator-tunnel.log 2>&1 &
sleep 5
TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' /tmp/sinator-tunnel.log | head -1)

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ SINator ist bereit!              ${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Local:    ${CYAN}http://localhost:3000${NC}"
if [ -n "$TUNNEL_URL" ]; then
    echo -e "  Public:   ${CYAN}${TUNNEL_URL}${NC}"
fi
echo -e "  Auth:     ${CYAN}${TOKEN}${NC}"
echo ""
echo -e "  Öffne die URL und gib den Auth-Token ein."
echo ""
</sparameter>
<zparameter name="filePath" string="true">/Users/jeremy/dev/SINator-fireworksai/tools/install.sh