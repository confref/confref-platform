#!/usr/bin/env bash
# Build a new Fuseki database from the data index of confref-data, check it, switch the endpoint to it, and run
# the jobs (jobs.sh: the index of the application from the same store, the map).
#   services/load.sh            (as the deploy user, on the VM)
# The new database is $DATA/fuseki/db-<date>; the previous one stays until it is removed by hand. It is compacted
# after the check (each upload leaves old copies of the changed blocks behind), unless the
# files have numbers of 19 or more digits, which tdb2.tdbcompact 6.2.0 would wrap like the bulk loader (load.py).
# Downloaded files stay in $DATA/store (also read by the index job), so a reload downloads only what is new.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a

new=$DATA/fuseki/db-$(date +%F)
n=1; while [ -e "$new" ]; do n=$((n + 1)); new=$DATA/fuseki/db-$(date +%F)-$n; done
mkdir -p "$new" && chmod 2775 "$new"

wait_for() { for _ in $(seq 300); do curl -sf -o /dev/null "http://127.0.0.1:$1/\$/ping" && return 0; sleep 1; done; return 1; }
count() { curl -sf "http://127.0.0.1:$1/confref/query" -H 'Accept: text/csv' \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?triples) { GRAPH ?g { ?s ?p ?o } }' | tail -1 | tr -d '\r'; }

echo "== loading into $new"
docker compose build -q fuseki
FUSEKI_LOAD_DB=$new docker compose --profile load up -d fuseki-load
wait_for 3031
status=0
python3 fuseki/load.py --store "$DATA/store" --fuseki http://127.0.0.1:3031/confref ${LOAD_SKIP:+--skip "$LOAD_SKIP"} "$@" | tee "$new.log" || status=$?
[ $status = 0 ] && loaded=$(count 3031)
FUSEKI_LOAD_DB=$new docker compose --profile load rm -sf fuseki-load
if [ $status != 0 ]; then
  echo "load failed or the check found differences (see $new.log); the endpoint is unchanged"
  exit 1
fi

if grep -qx 'long numbers: 0' "$new.log"; then
  echo "== compacting $new ($(du -sh "$new" | cut -f1))"
  FUSEKI_LOAD_DB=$new docker compose --profile load run --rm --no-deps --entrypoint java fuseki-load \
    "-Xmx${FUSEKI_HEAP:-8g}" -cp /opt/fuseki/fuseki-server.jar tdb2.tdbcompact --loc /fuseki/database --deleteOld
  FUSEKI_LOAD_DB=$new docker compose --profile load up -d fuseki-load
  wait_for 3031
  compacted=$(count 3031)
  FUSEKI_LOAD_DB=$new docker compose --profile load rm -sf fuseki-load
  if [ "$compacted" != "$loaded" ]; then
    echo "after compacting: $compacted triples, before: $loaded; the endpoint is unchanged"
    exit 1
  fi
  echo "$compacted triples, $(du -sh "$new" | cut -f1)"
else
  echo "== not compacted: the files have numbers of 19 or more digits (see $new.log)"
fi

echo "== switching the endpoint to $new"
sed -i "s#^FUSEKI_DB=.*#FUSEKI_DB=$new#" .env
export FUSEKI_DB=$new           # the value read from .env above would win over the file
docker compose up -d fuseki
wait_for 3030
echo "$(count 3030) triples in the endpoint"
echo "previous databases:"; ls -d "$DATA"/fuseki/db-* | grep -vx "$new" || true

echo "== the jobs: the index of the application, the map (jobs.sh)"
docker compose up -d --build graph
./jobs.sh
