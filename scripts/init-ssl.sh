#!/bin/bash
# First-time SSL certificate setup for gw.kodass.ru
# Run this ONCE on the server before starting the full stack.
#
# Usage:
#   chmod +x scripts/init-ssl.sh
#   ./scripts/init-ssl.sh your@email.com

set -e

EMAIL=${1:-""}
DOMAIN="gw.kodass.ru"

if [ -z "$EMAIL" ]; then
  echo "Usage: $0 your@email.com"
  exit 1
fi

echo "==> Creating temporary nginx config for ACME challenge..."
cat > /tmp/nginx-init.conf << 'EOF'
server {
    listen 80;
    server_name gw.kodass.ru;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'ok';
    }
}
EOF

echo "==> Starting temporary nginx (HTTP only) and certbot volumes..."
docker compose -f docker-compose.prod.yml run --rm \
  -v /tmp/nginx-init.conf:/etc/nginx/conf.d/default.conf:ro \
  -p 80:80 \
  nginx nginx -g 'daemon off;' &
NGINX_PID=$!
sleep 3

echo "==> Obtaining certificate for ${DOMAIN}..."
docker compose -f docker-compose.prod.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  --email "${EMAIL}" \
  --agree-tos --no-eff-email \
  -d "${DOMAIN}"

echo "==> Stopping temporary nginx..."
kill $NGINX_PID 2>/dev/null || true
sleep 2

echo "==> Certificate obtained. Starting full stack..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "Done! Run the following to initialise the database (first deploy only):"
echo "  docker compose -f docker-compose.prod.yml exec web flask init-db"
