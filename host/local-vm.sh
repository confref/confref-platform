#!/usr/bin/env bash
# The local test VM (Lima, host/local-vm.yaml), set up and loaded like the real VM; then https://localhost:8543/
# (self-signed certificate). The pages link to that address (CR_ID_BASE, CR_LABS_BASE, the base URL of the site).
#   host/local-vm.sh             create or start the VM, install it (host/install.sh), load the stable versions of the
#                                data index on GitHub from the dumps location (services/load.sh), copy the site
#   host/local-vm.sh update      copy this checkout and confref-map again, rebuild the application, copy the site
#                                (no new load; services/jobs.sh in the VM rebuilds the index and the map)
#   limactl stop confref / limactl delete confref
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
MAP=$(cd "$REPO/../confref-map" && pwd)
NAME=confref
BASE=https://localhost:8543
vm() { limactl shell "$NAME" -- "$@"; }

if ! limactl list -q | grep -qx "$NAME"; then
  limactl start -y --name="$NAME" "$REPO/host/local-vm.yaml"
elif [ "$(limactl list --format '{{.Status}}' "$NAME")" != Running ]; then
  limactl start "$NAME"
fi

echo "== the code (this checkout and confref-map, read-only in the VM at the same paths) to /data/confref/src"
vm bash -c 'sudo mkdir -p /data/confref/src && sudo chown $USER: /data/confref /data/confref/src'
vm rsync -a --delete --exclude services/.env --exclude site/public/ "$REPO/" /data/confref/src/confref-platform/
vm rsync -a --delete --exclude dist/ "$MAP/" /data/confref/src/confref-map/

if [ "${1:-}" = update ]; then
  vm bash -c 'sudo -iu $USER bash -c "cd /data/confref/src/confref-platform/services && docker compose up -d --build graph"'
else
  vm bash -c 'cd /data/confref/src/confref-platform && sudo TLS=self-signed DATA_ON_ROOT=1 DEPLOY_USER=$USER host/install.sh'
  vm bash -c "cd /data/confref/src/confref-platform/services && [ -f .env ] || { cp .env.example .env &&
    printf 'CR_ID_BASE=$BASE\nCR_LABS_BASE=$BASE\n' >> .env; }"
  vm bash -c 'sudo -iu $USER /data/confref/src/confref-platform/services/load.sh'   # a new login: groups docker, fuseki
fi

"$REPO/host/deploy.sh" "lima-$NAME" "$BASE/"
echo "https://localhost:8543/"
