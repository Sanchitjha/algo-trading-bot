#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VPS Setup Script for Algo Trading Bot
# Run on a fresh Ubuntu 22.04 / 24.04 LTS server
#
# Usage:
#   chmod +x deploy/setup_vps.sh
#   sudo ./deploy/setup_vps.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

echo "=========================================="
echo "  Algo Trading Bot — VPS Setup"
echo "=========================================="

# ─── SYSTEM UPDATE ───────────────────────────────────────────
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# ─── INSTALL PYTHON ──────────────────────────────────────────
echo "[2/8] Installing Python 3.12..."
apt install -y python3 python3-pip python3-venv git curl ufw nginx certbot python3-certbot-nginx

# ─── FIREWALL ────────────────────────────────────────────────
echo "[3/8] Configuring firewall (UFW)..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable
echo "Firewall configured: SSH + HTTP + HTTPS only"

# ─── CLONE REPO ──────────────────────────────────────────────
echo "[4/8] Cloning repository..."
DEPLOY_DIR="/home/ubuntu/algo-trading-bot"
if [ -d "$DEPLOY_DIR" ]; then
    echo "Directory exists, pulling latest..."
    cd "$DEPLOY_DIR" && git pull
else
    echo "Enter your GitHub repo URL:"
    read -r REPO_URL
    git clone "$REPO_URL" "$DEPLOY_DIR"
fi
cd "$DEPLOY_DIR"

# ─── PYTHON VENV ─────────────────────────────────────────────
echo "[5/8] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ─── ENVIRONMENT FILE ────────────────────────────────────────
echo "[6/8] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  IMPORTANT: Edit .env with your credentials:"
    echo "  nano $DEPLOY_DIR/.env"
    echo ""
fi

# Create logs directory
mkdir -p logs

# ─── SYSTEMD SERVICE ────────────────────────────────────────
echo "[7/8] Installing systemd service..."
cp deploy/algobot.service /etc/systemd/system/algobot.service

# Update service file paths for venv
sed -i "s|/usr/bin/gunicorn|$DEPLOY_DIR/venv/bin/gunicorn|g" /etc/systemd/system/algobot.service

systemctl daemon-reload
systemctl enable algobot
echo "Service installed (not started yet — configure .env first)"

# ─── NGINX ───────────────────────────────────────────────────
echo "[8/8] Configuring nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/algobot

echo ""
echo "  IMPORTANT: Edit nginx config with your domain:"
echo "  nano /etc/nginx/sites-available/algobot"
echo "  Replace 'your-domain.com' with your actual domain"
echo ""
echo "  Then:"
echo "  ln -s /etc/nginx/sites-available/algobot /etc/nginx/sites-enabled/"
echo "  nginx -t && systemctl reload nginx"
echo ""
echo "  For SSL certificate:"
echo "  certbot --nginx -d your-domain.com"
echo ""

echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  Next steps:"
echo "  1. Edit .env:           nano $DEPLOY_DIR/.env"
echo "  2. Edit nginx config:   nano /etc/nginx/sites-available/algobot"
echo "  3. Enable nginx site:   ln -sf /etc/nginx/sites-available/algobot /etc/nginx/sites-enabled/"
echo "  4. Test nginx:          nginx -t && systemctl reload nginx"
echo "  5. Get SSL cert:        certbot --nginx -d your-domain.com"
echo "  6. Start the bot:       systemctl start algobot"
echo "  7. Check status:        systemctl status algobot"
echo "  8. View logs:           journalctl -u algobot -f"
echo ""
echo "  Your webhook URL will be: https://your-domain.com/webhook"
echo "=========================================="
