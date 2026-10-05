"""Explicit ingestion only; tests and demos consume the committed offline snapshot."""
import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.domains.emergency_response.snapshot import from_geojson


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Previously retrieved USGS GeoJSON")
    parser.add_argument("--fetch", action="store_true", help="Explicitly fetch the official USGS significant-month feed")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Never overwrite an existing snapshot")
    if bool(args.input) == args.fetch: parser.error("Choose exactly one input or fetch")
    if args.input: feed = json.loads(args.input.read_text())
    else:
        with urlopen("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson", timeout=30) as response:
            feed = json.load(response)
    snapshot = from_geojson(feed, args.snapshot_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target: json.dump(snapshot, target, indent=2)


if __name__ == "__main__": main()
