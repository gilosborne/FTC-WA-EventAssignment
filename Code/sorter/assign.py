"""Team assignment algorithms: greedy zip-bucket sorting with multiple ordering strategies."""
import math
from collections import Counter, defaultdict


def greedy(events, teams, zips, distance_fn, order="bump", locks=None):
    """Assign teams to events using zip-bucket greedy.
    
    Args:
        events: List of dicts with keys: code, zip, cap
        teams: List of dicts with keys: num, zip
        zips: Dict of {zip: (lat, lon, city, county)} from geo.load_zips()
        distance_fn: Function(zip_a, zip_b) -> travel cost (miles or minutes)
        order: "bump" (default), "largest", or "regret"
        locks: Optional {team_num: event_code} for pre-assigned teams
    
    Returns:
        {team_num: event_code or None}. None = unassigned (unknown zip or no capacity).
    """
    fill = Counter()
    out = {}
    
    # Place locked teams first
    for team_num, event_code in (locks or {}).items():
        out[team_num] = event_code
        fill[event_code] += 1
    
    # Group teams by zip
    buckets = defaultdict(list)
    for team in teams:
        if team["num"] in out:
            continue
        if team["zip"] not in zips:
            out[team["num"]] = None  # Unknown zip
            continue
        buckets[team["zip"]].append(team["num"])
    
    # Track remaining buckets to place
    left = dict(buckets)
    
    def has_room(event, count):
        """Check if event has room for count teams."""
        return event["cap"] - fill[event["code"]] >= count
    
    def options_for_bucket(zip_code, count):
        """Get sorted list of (distance, event_index, event) for buckets that fit.

        Events with no computed distance (inf) are not options: placing a team there
        would hide a missing drive time behind a fake assignment.
        """
        opts = []
        for i, event in enumerate(events):
            if has_room(event, count):
                dist = distance_fn(zip_code, event["zip"])
                if math.isfinite(dist):
                    opts.append((dist, i, event))
        return sorted(opts)
    
    # Order buckets for placement
    pending = sorted(left.items(), key=lambda kv: len(kv[1]), reverse=True)
    
    if order == "bump":
        # Static bump cost: difference between nearest and 2nd-nearest venue
        venue_zips = sorted({e["zip"] for e in events})
        
        def bump_cost(zip_code):
            distances = sorted(d for d in (distance_fn(zip_code, vz) for vz in venue_zips)
                               if math.isfinite(d))
            return distances[1] - distances[0] if len(distances) > 1 else float("inf")
        
        # Sort by bump cost (highest first), then by bucket size (largest first)
        pending.sort(key=lambda kv: (bump_cost(kv[0]), len(kv[1])), reverse=True)
    
    # Place buckets
    while pending:
        if order == "regret":
            # Dynamic regret: recalculate before each placement
            def regret(kv):
                opts = options_for_bucket(kv[0], len(kv[1]))
                if not opts:
                    return -1
                if len(opts) < 2:
                    return float("inf")
                return opts[1][0] - opts[0][0]
            
            pending.sort(key=lambda kv: (regret(kv), len(kv[1])), reverse=True)
        
        zip_code, team_nums = pending.pop(0)
        opts = options_for_bucket(zip_code, len(team_nums))
        
        if not opts:
            # No room anywhere, leave unassigned
            continue
        
        # Pick the nearest event
        chosen_event = opts[0][2]
        fill[chosen_event["code"]] += len(team_nums)
        
        for team_num in team_nums:
            out[team_num] = chosen_event["code"]
        
        del left[zip_code]
    
    # Mark remaining teams as unassigned
    for team_nums in left.values():
        for team_num in team_nums:
            out[team_num] = None
    
    return out


def improve(events, teams, zips, distance_fn, initial, max_swaps=100):
    """Local search improvement on an initial assignment.
    
    Tries swapping team groups between events to reduce total travel.
    Not used by default but available as an option.
    
    Args:
        events: List of event dicts
        teams: List of team dicts
        zips: Zip lookup dict
        distance_fn: Distance function
        initial: Initial assignment from greedy()
        max_swaps: Maximum number of swap attempts
    
    Returns:
        Improved {team_num: event_code or None}
    """
    # Create reverse index: event -> [team_nums]
    by_event = defaultdict(list)
    for team in teams:
        event_code = initial.get(team["num"])
        if event_code:
            by_event[event_code].append(team["num"])
    
    # Group teams by zip within each event
    def event_buckets(event_code):
        """Return {zip: [team_nums]} for teams assigned to this event."""
        result = defaultdict(list)
        for team_num in by_event[event_code]:
            team = next(t for t in teams if t["num"] == team_num)
            if team["zip"] in zips:
                result[team["zip"]].append(team_num)
        return result
    
    def total_distance():
        """Calculate total travel for current assignment."""
        total = 0.0
        event_zips = {e["code"]: e["zip"] for e in events}
        for team in teams:
            event_code = initial.get(team["num"])
            if event_code and team["zip"] in zips:
                total += distance_fn(team["zip"], event_zips[event_code])
        return total
    
    current_distance = total_distance()
    swaps_made = 0
    
    # Try swapping buckets between event pairs
    event_codes = [e["code"] for e in events]
    for _ in range(max_swaps):
        improved = False
        
        for i, event_a in enumerate(event_codes):
            for event_b in event_codes[i+1:]:
                buckets_a = event_buckets(event_a)
                buckets_b = event_buckets(event_b)
                
                # Try swapping each zip bucket pair
                for zip_a in buckets_a:
                    for zip_b in buckets_b:
                        # Calculate delta
                        # (Simplified: this would need full capacity checking)
                        pass  # Implementation stub
        
        if not improved:
            break
        swaps_made += 1
    
    return initial  # Return initial for now (stub implementation)


def groups_of(assignment, teams, size):
    """Split large zip groups that exceed venue capacity.
    
    Helper for handling overflow when a single zip has more teams than
    the largest event can hold.
    
    Args:
        assignment: Current assignment dict
        teams: List of team dicts
        size: Maximum group size
    
    Returns:
        Modified assignment with groups split
    """
    # Stub implementation - would split buckets by team number or other criteria
    return assignment
