"""``python -m surprise.theory {constants|manifest}``."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="surprise.theory")
    parser.add_argument("command", choices=("constants", "manifest"))
    args = parser.parse_args(argv)
    if args.command == "constants":
        from surprise.theory.constants import as_dict

        payload = as_dict()
    else:
        from surprise.theory.manifest import theory_manifest

        payload = theory_manifest()
    json.dump(payload, sys.stdout, sort_keys=True, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
