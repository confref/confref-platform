#!/usr/bin/env python3
"""The jobs of the application, run after a load (services/jobs.sh):

    python3 jobs.py index        the index (index.py) from the stable versions in the store, into CR_DB
"""

import sys

import config
import index


def main(args):
    if args[:1] == ["index"]:
        config.DB.parent.mkdir(parents=True, exist_ok=True)
        index.build(config.DB)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
