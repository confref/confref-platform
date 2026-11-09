#!/usr/bin/env bash
# The jobs after a load: the index of the application (apps/graph/jobs.py index: SQLite from the store) and the map
# (confref-map/build.py, from the index, into $DATA/www/map; the checkout of confref-map in $DATA/src).
#   services/jobs.sh            both;   services/jobs.sh index|map   one of them
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a
what=${1:-all}
if [[ $what == all || $what == index ]]; then
  docker compose build -q graph       # the code is in the image: build it from this checkout
  docker compose run --rm -T graph python3 jobs.py index
  docker compose up -d graph          # the application opens the new index at the next request
fi
if [[ $what == all || $what == map ]]; then
  python3 "$DATA/src/confref-map/build.py" "$DATA/www/generated/confref.sqlite" "$DATA/www/map.new"
  rm -rf "$DATA/www/map.old"; [ -d "$DATA/www/map" ] && mv "$DATA/www/map" "$DATA/www/map.old"
  mv "$DATA/www/map.new" "$DATA/www/map"
fi
