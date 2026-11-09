#!/usr/bin/env bash
# Copy the labs site to the VM (rsync over ssh; the files of the VM are replaced).
#   host/deploy.sh <ssh-host>                      build the Hugo site for https://labs.confref.org/ and copy it
#   host/deploy.sh <ssh-host> <base URL>           a test VM: links to that address (e.g. https://localhost/)
# The local test VM (host/local-vm.yaml) is the ssh host lima-confref.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
host=${1:?ssh host}; base=${2:-}
ssh_cmd=ssh
lima_cfg=~/.lima/${host#lima-}/ssh.config
[[ $host == lima-* && -f $lima_cfg ]] && ssh_cmd="ssh -F $lima_cfg"
out=$(mktemp -d)                  # built apart from site/public, which stays as it is
trap 'rm -rf "$out"' EXIT
"$REPO/site/build.sh" "$base" "$out"
chmod -R a+rX "$out"
rsync -a --delete --exclude map/ -e "$ssh_cmd" "$out/" "$host:/data/confref/www/site/"
echo "copied to $host:/data/confref/www/site/"
