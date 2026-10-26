#!/usr/bin/env python3
"""The configured region: the `states` list in sorter.toml, shared by every setup tool.

Shell scripts call it to get the same answer the Python tools use:
  python3 tools/region.py states   ->  WA,OR
  python3 tools/region.py tag      ->  or-wa         (names the OSRM build and container)
  python3 tools/region.py urls     ->  one Geofabrik extract URL per state, one per line
"""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "sorter.toml"
GEOFABRIK = "https://download.geofabrik.de/north-america/us/{}-latest.osm.pbf"

# Geofabrik's file name for each state. All 51 were checked to resolve on 2026-10-15.
GEOFABRIK_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "DC": "district-of-columbia",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho", "IL": "illinois",
    "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york",
    "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina", "SD": "south-dakota",
    "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia",
    "WA": "washington", "WV": "west-virginia", "WI": "wisconsin", "WY": "wyoming",
}


def parse_states(text):
    """Accepts 'WA,OR' (a --states flag) or ['WA', 'OR'] (sorter.toml)."""
    items = text if isinstance(text, list) else str(text).split(",")
    states = [str(s).strip().upper() for s in items if str(s).strip()]
    bad = [s for s in states if s not in GEOFABRIK_NAMES]
    if not states or bad:
        raise SystemExit(f"States must be USPS codes like WA,OR (got {text!r})")
    return states


def region_states(path=CONFIG_FILE):
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise SystemExit(f"Cannot read {path}: {e}")
    if "states" not in data:
        raise SystemExit(f"{path} has no states = [...] setting")
    return parse_states(data["states"])


def tag(states):
    return "-".join(sorted(s.lower() for s in states))


def extract_urls(states):
    return [GEOFABRIK.format(GEOFABRIK_NAMES[s]) for s in states]


def main(argv):
    states = region_states()
    commands = {"states": lambda: ",".join(states), "tag": lambda: tag(states),
                "urls": lambda: "\n".join(extract_urls(states))}
    if len(argv) != 1 or argv[0] not in commands:
        sys.exit(f"usage: python3 tools/region.py {{{'|'.join(commands)}}}")
    print(commands[argv[0]]())


if __name__ == "__main__":
    main(sys.argv[1:])
