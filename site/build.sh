#!/usr/bin/env bash
# Build the labs site into public/: the kit stylesheet from the stylesheet of www.confref.org (kit-src/www.css, a copy
# of confref-site/assets/css/main.css with the font paths of the kit) and the labs additions, then Hugo.
#   site/build.sh                      (production: https://labs.confref.org/)
#   site/build.sh http://localhost:8091/   (a local test: links to this address)
set -euo pipefail
cd "$(dirname "$0")"
cat kit-src/www.css kit-src/labs.css > static/kit/1/confref.css
hugo --quiet ${1:+--baseURL "$1"} -d public
