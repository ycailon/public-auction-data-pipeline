"""Offline CLI, data fixtures only."""

import argparse
import json
from pathlib import Path

from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an offline fictional auction-listings ingestion demo")
    parser.add_argument("command", choices=["demo"])
    parser.add_argument("--manifest", default="fixtures/sources.json")
    parser.add_argument("--out", default="output")
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.out), indent=2))


if __name__ == "__main__":
    main()
