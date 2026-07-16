#!/bin/bash
# Generates Caddyfile from DOMAIN in .env. Run once before `docker compose up`.
set -e

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and set DOMAIN first."
  exit 1
fi

DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2)

if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "contoh-domain.com" ]; then
  echo "ERROR: Set your actual domain in .env (DOMAIN=your-domain.com)"
  exit 1
fi

cat > Caddyfile <<EOF
${DOMAIN} {
    reverse_proxy app:8000
}
EOF

echo "Caddyfile generated with domain: ${DOMAIN}"
echo "Next steps:"
echo "  1. Point DNS A record of ${DOMAIN} to this VPS IP"
echo "  2. Run: docker compose up -d --build"
