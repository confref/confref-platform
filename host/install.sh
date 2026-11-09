#!/usr/bin/env bash
# Set up a fresh Ubuntu VM (24.04 or 26.04 LTS) for labs.confref.org and id.confref.org. Idempotent: run again after
# changes.
#   sudo host/install.sh                       (from the checkout of this repository on the VM)
#   sudo CERTBOT_EMAIL=... host/install.sh     (an address for Let's Encrypt expiry notices; optional)
#   sudo TLS=self-signed host/install.sh       (a local test VM, host/local-vm.yaml: no Let's Encrypt)
#   sudo TLS=self-signed TLS_EXTRA=IP:<address> DATA_ON_ROOT=1 host/install.sh
#                                              (a server not yet reachable by its names; /data on the root volume)
#   sudo PROXY=<address> host/install.sh       (behind a reverse proxy that holds the public certificates, e.g. bart:
#                                              http and https only from that address, the client address from its
#                                              X-Forwarded-For; the VM keeps a self-signed certificate, which the
#                                              proxy checks; README.md, 'Behind a proxy')
# What it does: packages, Docker (storage on /data), firewall, directories under /data/confref, TLS certificates,
# nginx. It does not load data or start services: see README.md (services/load.sh, docker compose).
set -euo pipefail

HOSTS=(labs.confref.org id.confref.org)
DATA=/data/confref
DEPLOY_USER=${DEPLOY_USER:-${SUDO_USER:-}}
PROXY=${PROXY:-}
TLS=${TLS:-$([ -n "$PROXY" ] && echo self-signed || echo letsencrypt)}
REPO=$(cd "$(dirname "$0")/.." && pwd)
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
[ -n "$DEPLOY_USER" ] || { echo "set DEPLOY_USER (the account that deploys)"; exit 1; }
if [ ! -d /data ]; then
  [ "${DATA_ON_ROOT:-0}" = 1 ] || { echo "/data is missing (the data disk of the VM; DATA_ON_ROOT=1 makes it on the root volume)"; exit 1; }
  mkdir -p /data
fi

echo "== packages"
apt-get update -q
apt-get install -y -q ca-certificates curl git rsync python3 nginx certbot python3-certbot-nginx ufw unattended-upgrades

echo "== Docker (from Docker's repository; images and volumes on /data/docker)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
fi
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
mkdir -p /etc/docker /data/docker
if ! cmp -s "$REPO/host/docker-daemon.json" /etc/docker/daemon.json; then
  cp "$REPO/host/docker-daemon.json" /etc/docker/daemon.json
  systemctl restart docker
fi

echo "== firewall: ssh, http, https only${PROXY:+ (http and https from $PROXY only)} (containers publish on 127.0.0.1 only: Docker bypasses ufw)"
ufw allow OpenSSH >/dev/null
if [ -n "$PROXY" ]; then
  ufw delete allow 'Nginx Full' >/dev/null 2>&1 || true
  ufw allow from "$PROXY" to any app 'Nginx Full' >/dev/null
else
  ufw delete allow from "$(ufw status | sed -n "s/^Nginx Full .*ALLOW *\([0-9.]*\)$/\1/p" | head -1)" to any app 'Nginx Full' >/dev/null 2>&1 || true
  ufw allow 'Nginx Full' >/dev/null
fi
ufw --force enable >/dev/null
ufw status | head -8

echo "== accounts and directories"
getent group fuseki >/dev/null || groupadd --gid 9030 fuseki     # the user id of the Fuseki container
usermod -aG docker,fuseki "$DEPLOY_USER"
mkdir -p "$DATA"/www/site "$DATA"/www/map "$DATA"/www/generated "$DATA"/store "$DATA"/fuseki "$DATA"/src
chown -R "$DEPLOY_USER": "$DATA"/www "$DATA"/store "$DATA"/src
chown 9030:fuseki "$DATA"/fuseki && chmod 2775 "$DATA"/fuseki    # new databases: made by the deploy user, written by Fuseki
chown 9090:"$DEPLOY_USER" "$DATA"/www/generated && chmod 2775 "$DATA"/www/generated   # the application and its jobs

echo "== TLS certificate ($TLS) for ${HOSTS[*]}, linked as /etc/nginx/tls-confref"
if [ "$TLS" = self-signed ]; then
  dir=/etc/nginx/tls-self-signed-confref
  if [ ! -e "$dir/fullchain.pem" ]; then
    mkdir -p "$dir"
    openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=${HOSTS[0]}" \
      -addext "subjectAltName=$(printf 'DNS:%s,' "${HOSTS[@]}")DNS:localhost,IP:127.0.0.1${TLS_EXTRA:+,$TLS_EXTRA}" \
      -keyout "$dir/privkey.pem" -out "$dir/fullchain.pem" 2>/dev/null
  fi
  ln -sfn "$dir" /etc/nginx/tls-confref
else
  if [ ! -e "/etc/letsencrypt/live/${HOSTS[0]}/fullchain.pem" ]; then
    if [ -n "${CERTBOT_EMAIL:-}" ]; then contact=(-m "$CERTBOT_EMAIL"); else contact=(--register-unsafely-without-email); fi
    certbot certonly --nginx --cert-name "${HOSTS[0]}" $(printf -- '-d %s ' "${HOSTS[@]}") --agree-tos -n "${contact[@]}"
  fi
  ln -sfn "/etc/letsencrypt/live/${HOSTS[0]}" /etc/nginx/tls-confref
fi

echo "== nginx (labs is the default server; Ubuntu's default site is removed)"
rm -f /etc/nginx/sites-enabled/default
cp "$REPO/host/nginx/confref-labs.conf" /etc/nginx/sites-available/confref-labs.conf
if [ -n "$PROXY" ]; then     # the client address in the logs and for the application: the proxy's X-Forwarded-For
  printf '# written by host/install.sh (PROXY)\nset_real_ip_from %s;\nreal_ip_header X-Forwarded-For;\n' "$PROXY" \
    > /etc/nginx/conf.d/confref-proxy.conf
else
  rm -f /etc/nginx/conf.d/confref-proxy.conf
fi
ln -sf /etc/nginx/sites-available/confref-labs.conf /etc/nginx/sites-enabled/confref-labs.conf
nginx -t && systemctl reload nginx

echo "Done. $DEPLOY_USER must log in again for the groups docker and fuseki. Next: README.md, 'Data and services'."
