#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Usage: run_oci_ip_smoke.sh PUBLIC_IPV4' >&2
  exit 2
fi

public_ip=$1
cd /home/ubuntu/avaxagent-studio
umask 077

if [[ ! -e .env ]]; then
  postgres_password=$(openssl rand -hex 24)
  cat > .env <<EOF
POSTGRES_PASSWORD=$postgres_password
STUDIO_SITE=:80
GATEWAY_SITE=:8001
EOF
fi

if [[ ! -e apps/backend/.env ]]; then
  jwt_secret=$(openssl rand -hex 32)
  cat > apps/backend/.env <<EOF
ENVIRONMENT=production
NETWORK=avalanche-fuji
CORS_ORIGINS=["http://$public_ip"]
PUBLIC_GATEWAY_URL=http://$public_ip:8001
AUTH_DOMAIN=$public_ip
AUTH_JWT_SECRET=$jwt_secret
EOF
fi

sudo docker compose --profile apps config --quiet
sudo docker compose --profile apps up -d --build postgres redis migrate api gateway web
sudo docker compose --profile apps ps
