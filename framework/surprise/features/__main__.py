"""Command line for the feature package."""
from __future__ import annotations

import argparse
import sys

from .registry import default_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m surprise.features")
    parser.add_argument("command", choices=["vocab"], help="print the base vocabulary digest and entry count")
    args = parser.parse_args(argv)
    if args.command == "vocab":
        registry = default_registry()
        print(f"{registry.digest()} {len(registry.ids())}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
