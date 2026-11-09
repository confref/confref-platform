#!/usr/bin/env python3
"""A data index from the catalogue of a confref-data checkout, for a test VM that loads versions not yet on the dumps
location: the stable version of every dataset with its files (path, bytes, sha256), in the format of
catalog/dataindex.json. The files must be in the store of the VM already (load.py does not download a file that is
there with the right size and checksum).

    python3 host/catalog-dataindex.py <confref-data>/catalog [skip,…] > dataindex.json

skip: datasets left out, as on the dumps location (tuwien-pc: not published until TU Wien's written OK).
"""

import json
import sys
import tomllib
from pathlib import Path


def main(catalog, skip=()):
    out = {"checked": "catalogue", "locations": {"dumps": {"archive": "https://archive.confref.org/store/"}},
           "datasets": {}}
    for p in sorted(Path(catalog).glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if not text.startswith("+++"):
            continue
        d = tomllib.loads(text.split("+++")[1])
        stable = d.get("stable")
        if not stable or d["slug"] in skip:
            continue
        v = next((v for v in d.get("versions", []) if v.get("version") == stable), None)
        if not v:
            continue
        out["datasets"][d["slug"]] = {
            "title": d.get("title", d["slug"]), "stable": stable, "replaces": [], "replaced_by": [], "withdrawn": None,
            "versions": [{"version": stable, "status": "stable",
                          "files": [{"path": f["path"], "bytes": f["bytes"], "sha256": f["sha256"]}
                                    for f in v.get("files", [])]}]}
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main(sys.argv[1], set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set())
