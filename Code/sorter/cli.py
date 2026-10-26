"""Command-line interface for team sorting with map output."""
import argparse
import csv
import math
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from . import geo, assign, review, config


def load_events(path):
    """Load events from CSV: code, zip, capacity."""
    events = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0]:  # Skip empty rows and header if present
                events.append({
                    "code": row[0],
                    "zip": row[1],
                    "cap": int(row[2])
                })
    return events


def load_teams(path):
    """Load teams from CSV: number, name, zip, [optional_host_team]."""
    teams = []
    team_names = {}
    team_host = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                teams.append({
                    "num": row[0],
                    "zip": row[2]
                })
                if len(row) > 1:
                    team_names[row[0]] = row[1]
                if len(row) > 3:
                    team_host[row[0]] = row[3]
    return teams, team_names, team_host


class Override(NamedTuple):
    """One row of the pre-assignments file: where the team goes, and what staff wrote about it."""
    event: str
    is_host_team: bool
    notes: str


class PreAssignmentError(ValueError):
    pass


PRE_ASSIGNMENT_HEADER = ["event", "team_id", "is_host_team", "notes"]
HOST_WORDS = {"is_host_team", "host", "true", "yes", "y", "1"}


def load_pre_assignments(path):
    """Load pre-assignments from CSV: event, team_id[, is_host_team[, notes]].

    The event column holds an event code (FLL) or a league name (FTC). Spaces around values are
    ignored, a header row is optional, and unquoted commas after the third comma stay in the notes.
    With exactly three columns the third is a note unless it is a host word or a false word, so
    "SOUTH-SAT,1002,because I asked" keeps its note. Returns {team_id: Override}.
    """
    if not path or not Path(path).exists():
        return {}

    overrides = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line, raw in enumerate(csv.reader(f), start=1):
            row = [c.strip() for c in raw]
            if not any(row):
                continue
            if row[0].startswith("#"):
                raise PreAssignmentError(
                    f"line {line}: '#' comment lines are the old format; put the comment in the notes "
                    f"column instead ({','.join(PRE_ASSIGNMENT_HEADER)}). To convert a whole file: "
                    f"python3 tools/convert_pre_assignments.py OLD.csv NEW.csv")
            if [c.lower() for c in row[:2]] in (["event", "team_id"], ["league", "team_id"]):
                continue
            if len(row) < 2 or not row[0] or not row[1]:
                raise PreAssignmentError(f"line {line}: needs an event and a team_id, got {','.join(row)!r}")
            host, notes = (row[2], "") if len(row) > 2 else ("", "")
            if len(row) == 3 and host.lower() not in HOST_WORDS | review.FALSE_WORDS:
                host, notes = "", host
            elif len(row) > 3:
                notes = ",".join(raw[3:]).strip()
            if host.lower() not in HOST_WORDS | review.FALSE_WORDS:
                raise PreAssignmentError(
                    f"line {line}: is_host_team is {host!r}; leave it blank or write is_host_team")
            overrides[row[1]] = Override(row[0], review.truthy(host), notes)
    return overrides


def check_pre_assignments(overrides, teams, events):
    """Problems that make a pre-assignment file unusable: unknown teams or unknown events."""
    team_nums = {t["num"] for t in teams}
    event_codes = {e["code"] for e in events}
    problems = []
    unknown_teams = sorted(t for t in overrides if t not in team_nums)
    unknown_events = sorted({o.event for o in overrides.values() if o.event not in event_codes})
    if unknown_teams:
        problems.append(f"{len(unknown_teams)} team number(s) not in the teams file: {', '.join(unknown_teams)}")
    if unknown_events:
        problems.append(f"event code(s) not in the events file: {', '.join(unknown_events)}")
    return problems


def unassigned_reason(zip_code, zips, zip_states, region, mode, missing_drive_time):
    """Why a team was left unassigned, phrased as what the operator should do next.

    missing_drive_time: in drive mode, at least one event has no drive time for this zip.
    That is checked before capacity because a complete matrix might have placed the team.
    """
    if zip_code not in zips:
        state = zip_states.get(zip_code)
        if state and state not in region:
            return f"zip is in {state}, not one of the states in sorter.toml"
        return "zip code not found"
    if mode == "drive" and missing_drive_time:
        return "missing drive times; rebuild the drive matrix"
    return "no event with room"


def summary_key(reason):
    """The rule a flagged_reason entry belongs to, without its per-team figures."""
    if reason.startswith("looks closer on the map"):
        return "looks closer on the map"
    return reason.split(" (")[0]


OUTPUT_COLUMNS = [
    # Required by the map team
    "team_id", "team_name", "team_zipCode", "team_coordinates",
    "event_id", "event_zipCode", "event_coordinates", "program",
    # Sorting team columns (the map team ignores these)
    "is_host_team", "from_manual_override", "manual_override_notes",
    "drive_minutes", "drive_distance", "flagged_for_manual_review", "flagged_reason",
]


EVENT_COLUMNS = ["event_id", "event_zipCode", "capacity", "teams", "fill_percent",
                 "flagged_for_manual_review", "flagged_reason"]


def write_event_summary(path, events, assignment, rules):
    """Write one row per event and return the rows that were flagged."""
    fill = Counter(code for code in assignment.values() if code)
    rows = review.event_review(events, fill, rules)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, EVENT_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "flagged_for_manual_review": "true" if r["flagged_for_manual_review"] else "false"})
    return [r for r in rows if r["flagged_for_manual_review"]]


def write_map_output(output_path, teams, team_names, team_host, assignment, events, zips,
                     distance_fn, mode, program, rules, miles_fn, overrides=None,
                     zip_states=None, region=()):
    """Write one row per input team, in OUTPUT_COLUMNS order.

    distance_fn is the travel cost the sorter used (drive minutes, or straight-line miles);
    miles_fn gives the distance in miles for the same route (drive miles, or straight-line).
    overrides is {team_id: Override} from the pre-assignments file; those rows are marked
    from_manual_override with the file's notes, and its host flag adds to the teams file's.
    Returns (counts, unassigned_zips, reason_counts).
    """
    event_zips = {e["code"]: e["zip"] for e in events}
    overrides = overrides or {}
    zip_counts = Counter(t["zip"] for t in teams)
    unit = "drive" if mode == "drive" else "straight-line"
    counts = Counter()
    unassigned_zips = {}  # reason -> set of zips
    reason_counts = Counter()
    
    def wkt(zip_code):
        """Return WKT POINT string for a zip centroid."""
        if zip_code not in zips:
            return ""
        lat, lon = zips[zip_code][:2]
        return f"POINT ({lon} {lat})"

    def finite(value):
        return round(value, 1) if value is not None and math.isfinite(value) else None

    def blank(value):
        return "" if value is None else value

    def boolean(value):
        return "true" if value else "false"
    
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(OUTPUT_COLUMNS)
        
        for team in teams:
            zip_code = team["zip"]
            event_code = assignment.get(team["num"])
            reachable = [miles_fn(zip_code, e["zip"]) for e in events]
            nearest_miles = finite(min((m for m in reachable if math.isfinite(m)), default=None))
            
            if not event_code:
                event_zip = event_wkt = ""
                travel = assigned_miles = None
                missing_drive_time = any(not math.isfinite(distance_fn(zip_code, e["zip"])) for e in events)
                why = unassigned_reason(zip_code, zips, zip_states or {}, set(region), mode,
                                        missing_drive_time)
                unassigned_zips.setdefault(why, set()).add(zip_code)
                counts["unassigned"] += 1
            else:
                event_zip = event_zips[event_code]
                event_wkt = wkt(event_zip)
                travel = finite(distance_fn(zip_code, event_zip))
                assigned_miles = finite(miles_fn(zip_code, event_zip))
                why = None

            looks_closer = None
            if event_code and mode == "drive":
                looks_closer = review.looks_closer_event(
                    event_code, event_zip, events,
                    lambda z: geo.miles_straight_line(zip_code, z, zips),
                    lambda z: distance_fn(zip_code, z),
                    rules.looks_closer_minutes)
            reasons = review.review_reasons(zip_counts[zip_code], assigned_miles, nearest_miles, travel,
                                            why, unit, rules, looks_closer=looks_closer)
            if event_code:
                counts["flagged" if reasons else "assigned"] += 1
            for r in reasons:
                reason_counts[summary_key(r)] += 1

            override = overrides.get(team["num"])
            writer.writerow([
                team["num"],
                team_names.get(team["num"], ""),
                zip_code,
                wkt(zip_code),
                event_code or "",
                event_zip,
                event_wkt,
                program,
                boolean(review.truthy(team_host.get(team["num"], "")) or (override and override.is_host_team)),
                boolean(override),
                override.notes if override else "",
                blank(travel) if mode == "drive" else "",
                blank(assigned_miles) if mode == "drive" else "",
                boolean(reasons),
                "; ".join(reasons),
            ])
    
    return counts, unassigned_zips, reason_counts


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Assign teams to events using zip-bucket greedy assignment. Settings come from "
                    "sorter.toml; any flag below overrides the file for this run."
    )
    parser.add_argument("--config", help="Settings file (default: ./sorter.toml if present)")
    
    # Inputs and output (defaults: [files] in sorter.toml)
    parser.add_argument("--program", choices=config.PROGRAMS, help="Competition program")
    parser.add_argument("--teams", help="Teams CSV (number,name,zip[,host])")
    parser.add_argument("--events", help="Events CSV (code,zip,capacity)")
    parser.add_argument("--pre-assignments", help="Pre-assigned teams CSV (event,team_id[,is_host_team[,notes]])")
    parser.add_argument("--out", help="Output CSV")
    parser.add_argument("--drive-matrix", help="Drive matrix CSV; without it, straight-line miles are used")
    parser.add_argument("--zips",
                       help="Zip centroids CSV (default: .data/zips.csv, falls back to reference/wa_zips.csv)")
    parser.add_argument("--zip-states", default=".data/zip_states.csv",
                       help="Zip-to-state index for out-of-region flags (default: .data/zip_states.csv)")
    
    # Sorting and review (defaults: [sorting] and [review] in sorter.toml)
    parser.add_argument("--method", choices=config.METHODS, help="Ordering strategy")
    parser.add_argument("--ferry-wait", type=float, help="Minutes added to trips that use a ferry")
    parser.add_argument("--flag-over", type=float,
                       help="Flag travel over this: drive minutes, or straight-line miles without a matrix")
    parser.add_argument("--flag-miles", type=float, help="Flag teams whose assigned event is farther than this")
    parser.add_argument("--flag-nearest-miles", type=float, help="Flag teams whose nearest event is farther than this")
    parser.add_argument("--small-zip", type=int, help="Flag zips with this many teams or fewer")
    parser.add_argument("--large-zip", type=int, help="Flag zips with this many teams or more")
    parser.add_argument("--flag-looks-closer", type=float,
                       help="Flag when an event nearer as the crow flies is this many minutes longer by road")
    parser.add_argument("--flag-underfilled", type=float,
                       help="Flag events filled below this percent of capacity (empty events always)")
    parser.add_argument("--event-summary", help="Event summary CSV to write")
    
    parsed = vars(parser.parse_args())
    try:
        settings, config_path = config.resolve({k: parsed[k] for k in config.DEFAULTS}, parsed["config"])
    except config.ConfigError as e:
        parser.exit(2, f"Error: {e}\n")
    args = argparse.Namespace(**{**parsed, **settings})
    print(f"Settings from {config_path or 'built-in defaults'}: program={args.program}, method={args.method}, "
          f"ferry_wait={args.ferry_wait:g}, review small_zip={args.small_zip} large_zip={args.large_zip} "
          f"assigned_miles={args.flag_miles:g} nearest_miles={args.flag_nearest_miles:g} "
          f"travel={args.flag_over:g} looks_closer={args.flag_looks_closer:g} "
          f"underfilled={args.flag_underfilled:g}%")
    
    # Load data
    try:
        # Resolve zips path with fallback
        if args.zips:
            zips_path = Path(args.zips)
        else:
            # Default: the generated table, then the committed Washington-only table
            if Path(".data/zips.csv").exists():
                zips_path = Path(".data/zips.csv")
            elif Path("reference/wa_zips.csv").exists():
                zips_path = Path("reference/wa_zips.csv")
                print("Warning: .data/zips.csv not found; using reference/wa_zips.csv (Washington only). "
                      "Run setup.sh to build the table for the states in sorter.toml.", file=sys.stderr)
            else:
                print("Error: no zip table in .data/zips.csv or reference/wa_zips.csv. Run setup.sh first.", file=sys.stderr)
                sys.exit(2)
        
        zips = geo.load_zips(zips_path)
        zip_states = geo.load_zip_states(args.zip_states)
        region = geo.table_states(zips_path) or {"WA"}  # reference/wa_zips.csv has no state column
        events = load_events(args.events)
        teams, team_names, team_host = load_teams(args.teams)
        try:
            overrides = load_pre_assignments(args.pre_assignments)
        except PreAssignmentError as e:
            print(f"Error: {args.pre_assignments} {e}", file=sys.stderr)
            sys.exit(2)
        problems = check_pre_assignments(overrides, teams, events)
        if problems:
            print(f"Error: {args.pre_assignments} does not match this season's files:", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            print("Fix or remove the file, or point [files] pre_assignments in sorter.toml at the right one.",
                  file=sys.stderr)
            sys.exit(2)
        rules = review.Rules(small_zip=args.small_zip, large_zip=args.large_zip,
                             assigned_miles=args.flag_miles, nearest_miles=args.flag_nearest_miles,
                             travel=args.flag_over, looks_closer_minutes=args.flag_looks_closer,
                             underfilled_percent=args.flag_underfilled)
        
        # Determine distance function
        drive_matrix_path = Path(args.drive_matrix)
        if drive_matrix_path.exists():
            print(f"Using drive times from {args.drive_matrix}")
            drive_matrix = geo.load_drive_matrix(args.drive_matrix)
            miles_matrix = geo.load_drive_miles(args.drive_matrix)
            distance_fn = lambda a, b: geo.drive_minutes(a, b, drive_matrix, ferry_wait=args.ferry_wait)
            miles_fn = lambda a, b: geo.drive_miles(a, b, drive_matrix, miles_matrix, ferry_wait=args.ferry_wait)
            mode = "drive"
        else:
            print(f"Drive matrix not found at {args.drive_matrix}, using straight-line miles")
            distance_fn = lambda a, b: geo.miles_straight_line(a, b, zips)
            miles_fn = distance_fn
            mode = "miles"
        
        # Run assignment
        print(f"Assigning {len(teams)} teams to {len(events)} events using '{args.method}' method...")
        if overrides:
            print(f"Pre-assigned {len(overrides)} teams")
        
        assignment = assign.greedy(
            events=events,
            teams=teams,
            zips=zips,
            distance_fn=distance_fn,
            order=args.method,
            locks={team: o.event for team, o in overrides.items()}
        )
        
        # Write output
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        status_count, unassigned_zips, reason_counts = write_map_output(
            output_path=args.out,
            teams=teams,
            team_names=team_names,
            team_host=team_host,
            assignment=assignment,
            events=events,
            zips=zips,
            distance_fn=distance_fn,
            mode=mode,
            program=args.program,
            rules=rules,
            miles_fn=miles_fn,
            overrides=overrides,
            zip_states=zip_states,
            region=region
        )
        
        # Report
        print(f"\nResults: {sum(status_count.values())} teams")
        for status, count in sorted(status_count.items()):
            print(f"  {status}: {count}")
        if reason_counts:
            print("\nFlagged for manual review, by reason (teams):")
            for reason, count in reason_counts.most_common():
                print(f"  {reason}: {count}")
        if unassigned_zips:
            print("\nUnassigned, by reason (zips):")
            for reason, zip_set in sorted(unassigned_zips.items()):
                print(f"  {reason}: {', '.join(sorted(zip_set))}")
            if "missing drive times; rebuild the drive matrix" in unassigned_zips:
                print("\nThese zips are in the zip table but not the drive matrix. With OSRM running, rebuild it:")
                print(f"  python3 tools/build_drive_matrix.py --source osrm --teams {args.teams} --events {args.events}")
            if any(r.startswith("zip is in ") for r in unassigned_zips):
                print("\nTo cover another state, add it to states in sorter.toml, then rerun setup.sh "
                      "and tools/enable_drive_times.sh.")
        print(f"\nWrote {args.out}")
        flagged_events = write_event_summary(args.event_summary, events, assignment, rules)
        if flagged_events:
            print(f"\nEvents flagged for review ({len(flagged_events)} of {len(events)}):")
            for r in flagged_events:
                print(f"  {r['event_id']}: {r['flagged_reason']}")
        print(f"Wrote {args.event_summary}")
        
        # Exit with error if any teams are unassigned
        if status_count.get("unassigned", 0) > 0:
            sys.exit(1)
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
