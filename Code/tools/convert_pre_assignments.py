#!/usr/bin/env python3
"""Convert an old-format pre-assignments file to event,team_id,is_host_team,notes.

The old format put comments on '#' lines above the rows they describe:

    #
    #COACH REQUESTS
    LeagueA,1003

Each comment becomes the note for every row below it, until the next '#' line; a bare '#'
clears it. A note already in a row's third column is kept after the comment. is_host_team
is left blank, because the old format had no way to say it.

Usage: python3 tools/convert_pre_assignments.py OLD.csv NEW.csv
"""
import argparse
import csv
import sys
from pathlib import Path

HEADER = ["event", "team_id", "is_host_team", "notes"]


def convert(lines):
    """Rows (event, team_id, is_host_team, notes) from the old format's lines."""
    rows, comment = [], ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comment = line[1:].strip()
            continue
        fields = [f.strip() for f in next(csv.reader([line]))]
        own_note = ",".join(fields[2:]).strip()
        notes = "; ".join(n for n in (comment, own_note) if n)
        rows.append((fields[0], fields[1] if len(fields) > 1 else "", "", notes))
    return rows


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Convert an old '#'-comment pre-assignments file")
    ap.add_argument("old", help="Old-format file")
    ap.add_argument("new", help="File to write; must not exist yet")
    a = ap.parse_args()
    if Path(a.new).exists():
        sys.exit(f"{a.new} already exists; choose another name or move it first.")
    with open(a.old, encoding="utf-8-sig", newline="") as f:
        rows = convert(f.read().splitlines())
    write(a.new, rows)
    noted = sum(1 for r in rows if r[3])
    print(f"Wrote {a.new}: {len(rows)} rows, {noted} with notes. Check it, then point "
          f"[files] pre_assignments in sorter.toml at it.")


if __name__ == "__main__":
    main()
