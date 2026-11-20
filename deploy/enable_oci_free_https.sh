#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Usage: enable_oci_free_https.sh PUBLIC_IPV4' >&2
  exit 2
fi

public_ip=$1
studio_domain="studio.${public_ip}.sslip.io"
gateway_domain="gateway.${public_ip}.sslip.io"
cd /home/ubuntu/avaxagent-studio

for domain in "$studio_domain" "$gateway_domain"; do
  if ! getent ahostsv4 "$domain" | awk '{print $1}' | grep -Fxq "$public_ip"; then
    echo "DNS does not point $domain to $public_ip" >&2
    exit 1
  fi
done

set_env() {
  local file=$1 key=$2 value=$3
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

set_env .env STUDIO_SITE "$studio_domain"
set_env .env GATEWAY_SITE "$gateway_domain"
set_env .env GATEWAY_PORT '127.0.0.1:8001'
set_env apps/backend/.env AUTH_DOMAIN "$studio_domain"
set_env apps/backend/.env CORS_ORIGINS "[\"https://${studio_domain}\"]"
set_env apps/backend/.env PUBLIC_GATEWAY_URL "https://${gateway_domain}"

sudo docker compose --profile apps config --quiet
sudo docker compose --profile apps up -d --no-build api gateway web
echo "Studio: https://${studio_domain}"
echo "Gateway: https://${gateway_domain}"
