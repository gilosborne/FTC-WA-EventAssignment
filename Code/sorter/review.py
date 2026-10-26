"""Manual-review rules: which output rows a person should look at, and why."""
import math
from dataclasses import dataclass

FALSE_WORDS = {"", "false", "no", "n", "0"}


@dataclass(frozen=True)
class Rules:
    small_zip: int = 3            # flag zips with this many teams or fewer
    large_zip: int = 30           # flag zips with this many teams or more
    assigned_miles: float = 40    # flag teams whose assigned event is farther than this
    nearest_miles: float = 75     # flag teams whose NEAREST event is farther than this
    travel: float = 90            # flag travel over this, in drive minutes (or straight-line miles)
    looks_closer_minutes: float = 30  # flag when a crow-flies-nearer event is this much longer by road
    underfilled_percent: float = 50   # flag events filled below this share of capacity


def truthy(value):
    """Spreadsheet-style boolean: blank, false, no, n and 0 are false; anything else is true."""
    return value.strip().lower() not in FALSE_WORDS


def review_reasons(zip_count, assigned_miles, nearest_miles, travel, unassigned_reason, unit, rules,
                   looks_closer=None):
    """Reasons a team row needs manual review, in a fixed order. Empty list = no review needed.

    Distances that are None (not computed) never trigger a rule; the unassigned reason covers them.
    unit is "drive" or "straight-line" and only changes the wording.
    looks_closer is (event_code, straight_miles, extra_minutes) from looks_closer_event(), or None.
    """
    miles_label = "drive miles" if unit == "drive" else "straight-line miles"
    travel_label = "drive minutes" if unit == "drive" else "straight-line miles"
    reasons = []
    if unassigned_reason:
        reasons.append(f"unassigned: {unassigned_reason}")
    if zip_count <= rules.small_zip:
        reasons.append(f"{rules.small_zip:g} or fewer teams in zip ({zip_count})")
    if zip_count >= rules.large_zip:
        reasons.append(f"{rules.large_zip:g} or more teams in zip ({zip_count})")
    if assigned_miles is not None and assigned_miles > rules.assigned_miles:
        reasons.append(f"assigned event over {rules.assigned_miles:g} {miles_label} ({assigned_miles})")
    if nearest_miles is not None and nearest_miles > rules.nearest_miles:
        reasons.append(f"nearest event over {rules.nearest_miles:g} {miles_label} ({nearest_miles})")
    if looks_closer:
        code, straight, extra = looks_closer
        reasons.append(f"looks closer on the map: {code} is {straight} mi straight-line "
                       f"but {extra} min farther by road")
    if travel is not None and travel > rules.travel:
        reasons.append(f"travel over {rules.travel:g} {travel_label} ({travel})")
    return reasons


def looks_closer_event(assigned_code, assigned_zip, events, straight_miles, drive_minutes, threshold):
    """An event that is nearer than the assigned one as the crow flies, but at least `threshold`
    drive minutes farther by road: the water or mountain case a map reviewer would question.

    straight_miles(zip) and drive_minutes(zip) measure from the team. Events at the assigned
    venue and events with no drive time are skipped. Returns the crow-flies-nearest such event
    as (code, straight_miles, extra_minutes), rounded to 0.1, or None.
    """
    base_miles, base_minutes = straight_miles(assigned_zip), drive_minutes(assigned_zip)
    if not math.isfinite(base_minutes):
        return None
    best = None
    for e in events:
        if e["code"] == assigned_code or e["zip"] == assigned_zip:
            continue
        miles, minutes = straight_miles(e["zip"]), drive_minutes(e["zip"])
        if miles < base_miles and math.isfinite(minutes) and minutes - base_minutes >= threshold:
            if best is None or miles < best[1]:
                best = (e["code"], round(miles, 1), round(minutes - base_minutes, 1))
    return best


def event_review(events, fill, rules):
    """One summary row per event: fill against capacity, flagged when empty or under-filled.

    events: [{"code", "zip", "cap"}]; fill: {event_code: teams placed}.
    """
    out = []
    for e in events:
        teams, cap = fill.get(e["code"], 0), e["cap"]
        percent = round(100 * teams / cap) if cap else 0
        if teams == 0:
            reason = "empty: no teams placed"
        elif percent < rules.underfilled_percent:
            reason = f"under-filled: {teams} of {cap} seats ({percent}%, below {rules.underfilled_percent:g}%)"
        else:
            reason = ""
        out.append({"event_id": e["code"], "event_zipCode": e["zip"], "capacity": cap, "teams": teams,
                    "fill_percent": percent, "flagged_for_manual_review": bool(reason),
                    "flagged_reason": reason})
    return out
