#!/bin/bash
# SINator Service Manager — install/start/stop all launchd services
# Usage: ./manage_services.sh {install|start|stop|status|logs}
set -e

SINATOR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=$(which python3)

case "${1:-status}" in
    install)
        echo "→ Installing all SINator launchd services..."

        # Backend service
        cat > ~/Library/LaunchAgents/com.sinator.backend.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SINATOR_DIR}/agent_toolbox/start_toolbox.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SINATOR_DIR}</string>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-backend.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-backend.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # Watchdog service
        cat > ~/Library/LaunchAgents/com.sinator.watchdog.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SINATOR_DIR}/tools/key_watchdog.py</string>
        <string>--interval</string>
        <string>120</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SINATOR_DIR}</string>
    <key>StandardOutPath</key>
    <string>/tmp/key_watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/key_watchdog.err</string>
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

        # Tunnel service
        cat > ~/Library/LaunchAgents/com.sinator.tunnel.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which cloudflared)</string>
        <string>tunnel</string>
        <string>--url</string>
        <string>http://localhost:8000</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-tunnel.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        echo "→ Loading services..."
        for svc in backend watchdog tunnel; do
            launchctl load ~/Library/LaunchAgents/com.sinator.${svc}.plist 2>/dev/null || true
        done
        echo "✅ All services installed"
        ;;

    start)
        for svc in backend watchdog tunnel; do
            launchctl kickstart gui/$(id -u)/com.sinator.${svc} 2>/dev/null || \
                launchctl start com.sinator.${svc} 2>/dev/null || true
        done
        echo "✅ Services started"
        ;;

    stop)
        for svc in backend watchdog tunnel; do
            launchctl bootout gui/$(id -u)/com.sinator.${svc} 2>/dev/null || true
        done
        echo "✅ Services stopped"
        ;;

    status)
        echo "=== SINator Services ==="
        for svc in backend watchdog tunnel; do
            if launchctl print gui/$(id -u)/com.sinator.${svc} 2>/dev/null | grep -q "state = running"; then
                echo "  ✅ com.sinator.${svc} — running"
            else
                echo "  ❌ com.sinator.${svc} — not running"
            fi
        done
        if pgrep -f cloudflared &>/dev/null; then
            TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' /tmp/sinator-tunnel.log 2>/dev/null | head -1)
            echo ""
            echo "  Tunnel URL: ${TUNNEL_URL:-checking...}"
        fi
        ;;

    logs)
        echo "=== Backend ==="
        tail -5 /tmp/sinator-backend.log 2>/dev/null || echo "  (no log)"
        echo ""
        echo "=== Watchdog ==="
        tail -5 /tmp/key_watchdog.log 2>/dev/null || echo "  (no log)"
        echo ""
        echo "=== Tunnel ==="
        tail -3 /tmp/sinator-tunnel.log 2>/dev/null || echo "  (no log)"
        ;;

    *)
        echo "Usage: $0 {install|start|stop|status|logs}"
        ;;
esac
