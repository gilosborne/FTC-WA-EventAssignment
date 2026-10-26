#!/usr/bin/env python3
"""Build the zip centroid tables for the states in sorter.toml.

Reads the uszipcode project's public zip database (US Census / USPS centroids,
MIT-licensed) with the standard-library sqlite3 module. The uszipcode Python
package itself is not used: its sqlalchemy_mate dependency breaks on Python 3.12.

Writes:
  .data/zips.csv        zip,lat,lon,city,county,state,type for the configured states
  .data/zip_states.csv  zip,state for every US zip, so the sorter can tell a zip in
                        an unconfigured state (add it to sorter.toml) from a zip that
                        does not exist (likely a typo)

The 10.7 MB database is downloaded once to ~/.cache/uszipcode/ and checked
against a pinned SHA-256.

Usage: python3 tools/build_zip_table.py [--states WA,OR] [--db PATH]
"""
import argparse
import csv
import hashlib
import sqlite3
import sys
import tomllib
import urllib.request
from pathlib import Path

if __package__:
    from .region import CONFIG_FILE, parse_states, region_states
else:
    from region import CONFIG_FILE, parse_states, region_states

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / ".data"
DB_URL = "https://github.com/MacHu-GWU/uszipcode-project/releases/download/1.0.1.db/simple_db.sqlite"
DB_SHA256 = "43383f108ef14dccd925107bc77705f622b1014111ad5c9e5e2a6837bb7f64ff"
DB_CACHE = Path.home() / ".cache" / "uszipcode" / "simple_db.sqlite"
COLS = ["zip", "lat", "lon", "city", "county", "state", "type"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_db(dest=DB_CACHE):
    if dest.exists() and sha256(dest) == DB_SHA256:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    print(f"Downloading the zip database (10.7 MB) from {DB_URL} ...")
    urllib.request.urlretrieve(DB_URL, tmp)
    if sha256(tmp) != DB_SHA256:
        tmp.unlink()
        raise SystemExit("Downloaded zip database failed its SHA-256 check; not using it.")
    tmp.replace(dest)
    return dest


def load_overrides(path=CONFIG_FILE):
    """The [zip_overrides] section of sorter.toml as {zip: (lat, lon)}. Stops on a malformed entry.

    Each entry replaces a zip's centre point, e.g.
        "98027" = { lat = 47.5221, lon = -122.0280, note = "Issaquah High School" }
    """
    try:
        with open(path, "rb") as f:
            section = tomllib.load(f).get("zip_overrides", {})
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise SystemExit(f"Cannot read {path}: {e}")
    overrides = {}
    for z, entry in section.items():
        if not (isinstance(entry, dict) and len(z) == 5 and z.isdigit()):
            raise SystemExit(f"{path}: zip_overrides.{z} must be a 5-digit zip with {{ lat = ..., lon = ... }}")
        lat, lon = entry.get("lat"), entry.get("lon")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lon)) \
                or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise SystemExit(f"{path}: zip_overrides.{z} needs numeric lat and lon")
        overrides[z] = (float(lat), float(lon))
    return overrides


def export(db_path, states, out_dir=DATA_DIR, overrides=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(states))
        rows = con.execute(
            f"SELECT zipcode, lat, lng, major_city, county, state, zipcode_type FROM simple_zipcode "
            f"WHERE state IN ({marks}) AND lat IS NOT NULL AND lng IS NOT NULL ORDER BY zipcode",
            states).fetchall()
        everywhere = con.execute(
            "SELECT zipcode, state FROM simple_zipcode WHERE state IS NOT NULL ORDER BY zipcode").fetchall()
    finally:
        con.close()

    found = {r[5] for r in rows}
    missing = [s for s in states if s not in found]
    if missing:
        raise SystemExit(f"No zips found for {', '.join(missing)}. Check states in sorter.toml.")

    overrides = overrides or {}
    rows = [(z, *overrides[z], *rest) if z in overrides else (z, lat, lon, *rest)
            for z, lat, lon, *rest in rows]

    with open(out_dir / "zips.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    with open(out_dir / "zip_states.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zip", "state"])
        w.writerows(everywhere)
    counts = {s: sum(1 for r in rows if r[5] == s) for s in states}
    return counts


def main():
    ap = argparse.ArgumentParser(description="Build .data/zips.csv for the states in sorter.toml")
    ap.add_argument("--states", help="Comma-separated USPS codes (default: states in sorter.toml)")
    ap.add_argument("--db", type=Path, help="Use a local copy of simple_db.sqlite instead of downloading")
    a = ap.parse_args()
    states = parse_states(a.states) if a.states else region_states()
    try:
        db = a.db or fetch_db()
    except OSError as e:
        sys.exit(f"Could not download the zip database: {e}")
    counts = export(db, states, overrides=load_overrides())
    detail = ", ".join(f"{s} {n}" for s, n in counts.items())
    print(f"Wrote .data/zips.csv: {sum(counts.values())} zips ({detail}).")
    for z, (lat, lon) in load_overrides().items():
        print(f"  zip {z} centre replaced with {lat}, {lon} (zip_overrides in sorter.toml)")


if __name__ == "__main__":
    main()
