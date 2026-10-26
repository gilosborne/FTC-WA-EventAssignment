"""Geographic utilities for team sorting: distance calculations and zip lookups."""
import csv
import math


def load_zips(path):
    """Load zip code centroids from CSV.
    
    Returns: {zip: (lat, lon, city, county)}
    City and county are optional and default to empty strings.
    """
    zips = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            zips[row["zip"]] = (
                float(row["lat"]),
                float(row["lon"]),
                row.get("city", ""),
                row.get("county", "")
            )
    return zips


def load_zip_states(path):
    """Load the zip-to-state index written by tools/build_zip_table.py.

    Returns {zip: state}, or {} if the index does not exist (offline fallback setup).
    """
    try:
        with open(path) as f:
            return {row["zip"]: row["state"] for row in csv.DictReader(f)}
    except FileNotFoundError:
        return {}


def table_states(path):
    """States covered by a zip table, read from its state column ({} for older tables)."""
    with open(path) as f:
        return {row["state"] for row in csv.DictReader(f) if row.get("state")}


def miles_straight_line(zip_a, zip_b, zips):
    """Straight-line miles between zip centroids using haversine formula.
    
    Returns float('inf') if either zip is not in the database.
    """
    if zip_a not in zips or zip_b not in zips:
        return float('inf')
    
    (lat1, lon1), (lat2, lon2) = zips[zip_a][:2], zips[zip_b][:2]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2 - p1) / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def load_drive_matrix(path):
    """Load pre-computed drive times from CSV.
    
    Returns: {(team_zip, event_zip): (min_ferry_ok, min_no_ferry or None)}
    """
    return _load_pairs(path, "min_ferry_ok", "min_no_ferry")


def load_drive_miles(path):
    """Load pre-computed drive distances from the same CSV.

    Returns: {(team_zip, event_zip): (mi_ferry_ok, mi_no_ferry or None)}
    """
    return _load_pairs(path, "mi_ferry_ok", "mi_no_ferry")


def _load_pairs(path, ferry_col, no_ferry_col):
    pairs = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            pairs[(row["team_zip"], row["event_zip"])] = (
                float(row[ferry_col]) if row[ferry_col] else None,
                float(row[no_ferry_col]) if row[no_ferry_col] else None
            )
    return pairs


def drive_minutes(zip_a, zip_b, drive_matrix, ferry_wait=30.0):
    """Drive minutes between zips, charging dock wait to ferry routes.
    
    Args:
        zip_a: Origin zip code
        zip_b: Destination zip code
        drive_matrix: Pre-loaded drive matrix from load_drive_matrix()
        ferry_wait: Minutes to add to routes that use a ferry (default 30)
    
    Returns:
        Drive time in minutes. Same zip = 0. float('inf') if pair not in matrix.
    """
    if zip_a == zip_b:
        return 0.0
    
    if (zip_a, zip_b) not in drive_matrix:
        return float('inf')
    
    ferry_ok, no_ferry = drive_matrix[(zip_a, zip_b)]
    if ferry_ok is None:  # OSRM found no route at all
        return float('inf')
    uses_ferry = no_ferry is None or ferry_ok < no_ferry - 0.5
    
    if uses_ferry and no_ferry is not None:
        return min(no_ferry, ferry_ok + ferry_wait)
    elif uses_ferry:
        return ferry_ok + ferry_wait
    else:
        return ferry_ok


def drive_miles(zip_a, zip_b, drive_matrix, miles_matrix, ferry_wait=30.0):
    """Drive miles for the same route drive_minutes() picks (ferry or road).

    Same zip = 0. float('inf') if the pair or its distance is missing.
    """
    if zip_a == zip_b:
        return 0.0
    pair = (zip_a, zip_b)
    if pair not in drive_matrix or pair not in miles_matrix:
        return float('inf')
    ferry_ok, no_ferry = drive_matrix[pair]
    mi_ferry_ok, mi_no_ferry = miles_matrix[pair]
    if ferry_ok is None:
        return float('inf')
    uses_ferry = no_ferry is None or ferry_ok < no_ferry - 0.5
    takes_ferry = uses_ferry and (no_ferry is None or ferry_ok + ferry_wait < no_ferry)
    miles = mi_ferry_ok if (takes_ferry or not uses_ferry) else mi_no_ferry
    return float('inf') if miles is None else miles
