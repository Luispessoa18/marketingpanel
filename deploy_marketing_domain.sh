#!/usr/bin/env bash
set -euo pipefail

DOMAIN="marketing.incorporacao.digital"
APP_DIR="/root/.openclaw/workspace/projects/meta-connection-panel"
APP_PORT="8400"
APP_HOST="127.0.0.1"
SERVICE_NAME="meta-connection-panel"
EMAIL=""

if [[ "${1:-}" == "--email" && -n "${2:-}" ]]; then
  EMAIL="$2"
fi

echo "==> Deploying $DOMAIN -> $APP_HOST:$APP_PORT"
cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  echo "==> Creating virtualenv"
  python3 -m venv .venv
fi

echo "==> Installing Python dependencies"
. .venv/bin/activate
pip install -r requirements.txt

echo "==> Writing systemd service"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Meta Connection Panel
After=network.target

[Service]
User=root
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host ${APP_HOST} --port ${APP_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 4

echo "==> Testing local app"
curl -i "http://${APP_HOST}:${APP_PORT}/health"

echo "==> Ensuring nginx/certbot present"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx

echo "==> Writing temporary HTTP nginx config"
cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 25M;

    location / {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
nginx -t
systemctl reload nginx

if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "==> SSL certificate not found; issuing with certbot"
  if [[ -n "$EMAIL" ]]; then
    certbot --nginx -d "$DOMAIN" --redirect -m "$EMAIL" --agree-tos -n
  else
    certbot --nginx -d "$DOMAIN"
  fi
else
  echo "==> SSL certificate already exists; writing HTTPS nginx config"
  cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    client_max_body_size 25M;

    location / {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }
}
EOF
  nginx -t
  systemctl reload nginx
fi

echo "==> Final checks"
set +e
curl -Ik "https://${DOMAIN}"
systemctl status "$SERVICE_NAME" --no-pager
journalctl -u "$SERVICE_NAME" -n 50 --no-pager
set -e

echo "==> Done"
