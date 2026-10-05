"""Offline versioned USGS event ingestion. USGS tsunami flag is not confirmation."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[4] / "data/emergency_response/usgs_events_v1.json"


def validate_snapshot(data):
    if data.get("schema_version") != "1.0" or not data.get("snapshot_id") or not data.get("events"):
        raise ValueError("Invalid event snapshot")
    seen = set()
    for event in data["events"]:
        if event["source"] != "USGS" or event["source_event_id"] in seen:
            raise ValueError("Invalid event provenance")
        seen.add(event["source_event_id"])
        if not event["source_url"].startswith("https://earthquake.usgs.gov/"):
            raise ValueError("Invalid source URL")
        for key, low, high in (("magnitude", -2, 10), ("latitude", -90, 90), ("longitude", -180, 180), ("depth_km", -10, 1000)):
            value = event[key]
            if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Invalid event coordinate or magnitude")
        if event["tsunami_flag"] not in (None, 0, 1) or not event["place"]:
            raise ValueError("Invalid event metadata")
        for key in ("snapshot_date", "event_timestamp"):
            if datetime.fromisoformat(event[key]).tzinfo is None: raise ValueError("Missing UTC offset")
    return data


def load_snapshot(path=DEFAULT):
    return validate_snapshot(json.loads(Path(path).read_text()))


def from_geojson(feed, snapshot_id, retrieved_at=None):
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    events = []
    for feature in feed["features"]:
        properties = feature["properties"]
        longitude, latitude, depth = feature["geometry"]["coordinates"]
        events.append({"source": "USGS", "source_event_id": feature["id"], "source_url": properties["url"],
            "snapshot_date": timestamp, "magnitude": properties["mag"], "latitude": latitude,
            "longitude": longitude, "depth_km": depth, "place": properties["place"],
            "tsunami_flag": properties.get("tsunami"), "source_time_ms": properties["time"],
            "event_timestamp": datetime.fromtimestamp(properties["time"]/1000, timezone.utc).isoformat()})
    return validate_snapshot({"schema_version": "1.0", "snapshot_id": snapshot_id,
        "retrieval_method": "GeoJSON ingestion", "synthetic": False, "events": events})
