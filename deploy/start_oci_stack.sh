#!/usr/bin/env bash
# Run on the existing Ubuntu VM; an optional public IP refreshes sslip.io names.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

if [[ ! -f .env || ! -f apps/backend/.env ]]; then
  echo "Deployment .env files are missing in $repo_root" >&2
  exit 1
fi

if ! sudo systemctl is-active --quiet docker; then
  sudo systemctl start docker
fi

read_site() {
  local value
  value=$(sed -n "s/^$1=//p" .env | tail -n 1)
  value=${value%\"}
  value=${value#\"}
  printf '%s' "$value"
}

studio_site=$(read_site STUDIO_SITE)
gateway_site=$(read_site GATEWAY_SITE)
if [[ -z "$studio_site" || -z "$gateway_site" ]]; then
  echo 'STUDIO_SITE or GATEWAY_SITE is missing from .env' >&2
  exit 1
fi

public_ip=${1:-}
if [[ -n "$public_ip" && "$studio_site" == studio.*.sslip.io && \
  "$studio_site" != "studio.$public_ip.sslip.io" ]]; then
  bash deploy/enable_oci_free_https.sh "$public_ip"
  studio_site=$(read_site STUDIO_SITE)
  gateway_site=$(read_site GATEWAY_SITE)
fi

sudo docker compose --profile apps up -d --no-build

for service in postgres redis api gateway indexer worker settler web; do
  if [[ -z "$(sudo docker compose --profile apps ps -q "$service")" ]]; then
    echo "Service is not running: $service" >&2
    sudo docker compose --profile apps ps
    exit 1
  fi
done

for site in "$studio_site" "$gateway_site"; do
  url="https://$site/health"
  ready=false
  for attempt in {1..12}; do
    if curl -fs --max-time 5 "$url" >/dev/null; then
      ready=true
      break
    fi
    sleep 3
  done
  if [[ "$ready" != true ]]; then
    echo "Health check failed: $url" >&2
    exit 1
  fi
  echo "Healthy: $url"
done

sudo docker compose --profile apps ps
echo "Studio: https://$studio_site"
echo "Gateway: https://$gateway_site"
