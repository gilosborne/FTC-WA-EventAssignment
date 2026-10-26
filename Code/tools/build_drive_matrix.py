"""Build the zip-to-event drive-time table, degrading gracefully across sources.

Sources:
  osrm      Self-hosted OSRM (127.0.0.1). Setup: scripts/osrm_setup.sh (macOS or Codespaces).
            Nothing leaves the machine. Default first choice.
  cache     Keep the existing data/drive_matrix.csv and list any zips it lacks. Used when
            no live source answers.
  valhalla  Public FOSSGIS Valhalla server. Opt-in only (--source valhalla), and not in the
            auto chain: the public server caps a matrix at 100 cells and rejects any request
            containing a pair more than 150 km apart, and 613 of the 2026-27 season's 1,482
            pairs exceed that. It suits small regional checks, or a self-hosted Valhalla
            with raised limits (--valhalla-url). Terms: max 1 request/second
            (https://www.fossgis.de/arbeitsgruppen/osm-server/nutzungsbedingungen/).
            It sends zip centroids to a third party: open question D1.

--source auto (the default) tries osrm, then cache.

Every source writes the same columns, so compare_variants.py does not care which ran:
  min_ferry_ok / mi_ferry_ok   fastest route, ferries allowed
  min_no_ferry / mi_no_ferry   fastest route without a ferry; BLANK if no road route exists
Only zip centroids from .data/zips.csv are sent. No team names, numbers or counts.

Ferry handling differs by engine:
  osrm      exclude=ferry is a hard exclusion; an unreachable pair comes back null.
  valhalla  use_ferry=0 is not a reliable exclusion: for some islands it returns no path,
            for others a route that still uses a ferry. Each team zip is therefore routed
            once, ferries avoided, to a mainland anchor (Olympia). If that finds no path or
            a route with has_ferry=true, the zip is ferry-only and its no-ferry columns are
            left blank, matching OSRM.

Usage: python3 scripts/build_drive_matrix.py [--source auto|valhalla|osrm|cache]
Writes data/drive_matrix.csv and data/drive_matrix.meta.json. Standard library only.
"""
import argparse, csv, json, math, sys, time, urllib.error, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / ".data"
OUT = DATA_DIR / "drive_matrix.csv"
META = DATA_DIR / "drive_matrix.meta.json"
COLS = ["team_zip", "event_zip", "min_ferry_ok", "mi_ferry_ok", "min_no_ferry", "mi_no_ferry", "snap_m"]
MAINLAND_ANCHOR = (47.0379, -122.9007)  # Olympia, on the I-5 road network (Valhalla island test only)
VALHALLA_MAX_CELLS = 100  # public server: "Exceeded max locations: 100" = sources x targets per request


class SourceUnavailable(Exception):
    pass


def post(url, body, timeout=60):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def snap_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return round(6371000 * 2 * math.asin(math.sqrt(h)))


def from_valhalla(url, team, event):
    """Return {(team_zip, event_zip): row} from the public Valhalla server, 1 request/second."""
    loc = lambda p: {"lat": p[0], "lon": p[1]}
    rows, last = {}, [0.0]

    def call(endpoint, body):
        wait = 1.05 - (time.monotonic() - last[0])
        if wait > 0: time.sleep(wait)
        last[0] = time.monotonic()
        try:
            return post(f"{url}/{endpoint}", body)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 400 and "No path could be found" in detail:
                return None  # a valid answer: no route under these costing options
            raise SourceUnavailable(f"valhalla {endpoint}: HTTP {e.code} {detail[:200]}")
        except Exception as e:
            raise SourceUnavailable(f"valhalla {endpoint}: {e}")

    tz, ez = list(team), list(event)
    step = max(1, VALHALLA_MAX_CELLS // len(ez))
    for use_ferry, key in ((1, "ok"), (0, "no")):
        for i in range(0, len(tz), step):
            chunk = tz[i:i + step]
            r = call("sources_to_targets", {
                "sources": [loc(team[z]) for z in chunk], "targets": [loc(event[z]) for z in ez],
                "costing": "auto", "costing_options": {"auto": {"use_ferry": use_ferry}}, "units": "miles"})
            for si, line in enumerate(r["sources_to_targets"]):
                for cell in line:
                    a, b = chunk[si], ez[cell["to_index"]]
                    row = rows.setdefault((a, b), {"team_zip": a, "event_zip": b})
                    t, d = cell.get("time"), cell.get("distance")
                    row[f"min_{'ferry_ok' if key == 'ok' else 'no_ferry'}"] = "" if t is None else round(t / 60, 1)
                    row[f"mi_{'ferry_ok' if key == 'ok' else 'no_ferry'}"] = "" if d is None else round(d, 1)
                    if key == "ok":
                        s = r.get("sources", [{}])[si] if si < len(r.get("sources", [])) else {}
                        row["snap_m"] = snap_m(*team[a], s["lat"], s["lon"]) if "lat" in s else ""
    ferry_only = []
    for z in tz:  # island test: does avoiding ferries still need one to reach the mainland?
        r = call("route", {"locations": [loc(team[z]), loc(MAINLAND_ANCHOR)], "costing": "auto",
                           "costing_options": {"auto": {"use_ferry": 0}}})
        # No path with ferries avoided, or a path that still uses one: the zip is ferry-only.
        if r is None or r["trip"]["summary"].get("has_ferry"):
            ferry_only.append(z)
            for b in ez:
                rows[(z, b)]["min_no_ferry"] = rows[(z, b)]["mi_no_ferry"] = ""
    return rows, {"ferry_only_zips": ferry_only}


def from_osrm(url, team, event):
    """Return {(team_zip, event_zip): row} from a self-hosted OSRM server."""
    tz, ez = list(team), list(event)
    pts = [team[z] for z in tz] + [event[z] for z in ez]
    coords = ";".join(f"{lon},{lat}" for lat, lon in pts)
    base = (f"{url}/table/v1/driving/{coords}?sources={';'.join(map(str, range(len(tz))))}"
            f"&destinations={';'.join(map(str, range(len(tz), len(pts))))}&annotations=duration,distance")

    def table(extra=""):
        try:
            r = json.load(urllib.request.urlopen(base + extra, timeout=60))
        except Exception as e:
            raise SourceUnavailable(f"osrm: {e}")
        if r.get("code") != "Ok": raise SourceUnavailable(f"osrm: {r}")
        return r

    yes, no = table(), table("&exclude=ferry")
    m = lambda r, k, i, j, s: "" if r[k][i][j] is None else round(r[k][i][j] / s, 1)
    rows = {}
    for i, a in enumerate(tz):
        for j, b in enumerate(ez):
            rows[(a, b)] = {"team_zip": a, "event_zip": b,
                            "min_ferry_ok": m(yes, "durations", i, j, 60), "mi_ferry_ok": m(yes, "distances", i, j, 1609.34),
                            "min_no_ferry": m(no, "durations", i, j, 60), "mi_no_ferry": m(no, "distances", i, j, 1609.34),
                            "snap_m": round(yes["sources"][i]["distance"])}
    return rows, {}


def inputs(teams_csv, events_csv, zips_csv):
    """Load team and event zips from CSV files.
    
    Args:
        teams_csv: Path to teams CSV
        events_csv: Path to events CSV  
        zips_csv: Path to zip centroids CSV
    
    Returns:
        (team_zips, event_zips) where each is {zip: (lat, lon)}
    """
    zips = {r["zip"]: (float(r["lat"]), float(r["lon"])) 
            for r in csv.DictReader(open(zips_csv))}
    
    # Extract event zips from column 1 (code, zip, capacity)
    ev = sorted({r[1] for r in csv.reader(open(events_csv, encoding="utf-8-sig")) 
                 if r and len(r) > 1 and r[0]})
    
    # Extract team zips from column 2 (number, name, zip)
    tz = sorted({r[2] for r in csv.reader(open(teams_csv, encoding="utf-8-sig"))
                 if r and len(r) > 2} & zips.keys())
    
    return {z: zips[z] for z in tz}, {z: zips[z] for z in ev}


def check_cache(team, event):
    if not OUT.exists():
        raise SystemExit("No source reachable and no cached data/drive_matrix.csv. Nothing to fall back to.")
    have = {(r["team_zip"], r["event_zip"]) for r in csv.DictReader(open(OUT))}
    have_t, have_e = {t for t, _ in have}, {e for _, e in have}
    missing = sorted((set(team) - have_t) | (set(event) - have_e))
    meta = json.loads(META.read_text()) if META.exists() else {}
    print(f"Kept cached {OUT.name} (source {meta.get('source', 'unknown')}, built {meta.get('built', 'unknown')}).")
    if missing:
        print(f"WARNING: the cache lacks {len(missing)} zips in this season's files: {', '.join(missing)}. "
              "Teams in those zips will fail to place until a live source rebuilds the table.")
    return 0 if not missing else 2


def main():
    ap = argparse.ArgumentParser(description="Build drive-time matrix between team and event zips using OSRM")
    ap.add_argument("--teams", default=".data/teams.csv", help="Teams CSV (default: .data/teams.csv)")
    ap.add_argument("--events", default=".data/events.csv", help="Events CSV (default: .data/events.csv)")
    ap.add_argument("--zips", default=".data/zips.csv", help="Zip centroids CSV (default: .data/zips.csv)")
    ap.add_argument("--source", choices=["auto", "valhalla", "osrm", "cache"], default="auto")
    ap.add_argument("--valhalla-url", default="https://valhalla1.openstreetmap.de")
    ap.add_argument("--osrm-url", default="http://127.0.0.1:5055")
    a = ap.parse_args()
    
    # Resolve paths relative to repo root
    teams_path = Path(a.teams) if Path(a.teams).is_absolute() else ROOT / a.teams
    events_path = Path(a.events) if Path(a.events).is_absolute() else ROOT / a.events
    zips_path = Path(a.zips) if Path(a.zips).is_absolute() else ROOT / a.zips
    
    team, event = inputs(teams_path, events_path, zips_path)
    order = {"auto": ["osrm", "cache"], "valhalla": ["valhalla"], "osrm": ["osrm"], "cache": ["cache"]}[a.source]
    for src in order:
        if src == "cache":
            sys.exit(check_cache(team, event))
        try:
            fn, url = (from_valhalla, a.valhalla_url) if src == "valhalla" else (from_osrm, a.osrm_url)
            rows, extra = fn(url, team, event)
        except SourceUnavailable as e:
            print(f"{src} unavailable ({e}); trying next source." if src != order[-1] else f"{src} unavailable ({e}).")
            continue
        with open(OUT, "w", newline="") as f:
            w = csv.DictWriter(f, COLS); w.writeheader()
            for key in sorted(rows): w.writerow(rows[key])
        meta = {"source": src, "url": url, "built": date.today().isoformat(),
                "team_zips": len(team), "event_zips": len(event), **extra}
        META.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"Wrote {OUT.name}: {len(team)} team zips x {len(event)} event zips from {src} ({url}).")
        return
    sys.exit("No live source reachable. Run with --source cache to keep the existing table.")


if __name__ == "__main__":
    main()
