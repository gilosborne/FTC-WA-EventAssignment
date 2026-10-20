## FTC Washington Event Assignment

All of the code in this repo is meant to be used for assigning FTC teams to leagues according to the methodology laid out for FTC in Washington. There are two main steps in that as currently planned.

## Setup

### Prerequisites
- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip

### Option 1: GitHub Codespaces (Recommended)

Launch a pre-configured development environment directly in your browser:

1. **Create a codespace:**
   - Go to https://github.com/eastmk-goblin-mode/FTC-WA-EventAssignment
   - Click the green **Code** button
   - Select the **Codespaces** tab
   - Click **Create codespace on main** (or your working branch)

2. **Wait for setup to complete:**
   - The codespace installs Python 3.12 and the dependencies, then runs `setup.sh`, which creates `.data/` and builds the zip table
   - Setup typically takes 1-2 minutes
   - You'll see "Running postCreateCommand..." in the terminal

3. **Add your input files to `.data/`** (git-ignored, so team data never reaches the repository):
   - `.data/teams.csv` and `.data/events.csv`, in the formats under [File Formats](#file-formats)

4. **Check `sorter.toml`, then run the sorter:**
   ```bash
   python3 -m sorter.cli
   ```

**Cost management:**
- Free tier: 120 core-hours/month (60 hours on the default 2-core machine)
- Codespaces auto-stop after 30 minutes of inactivity (configurable in [Settings → Codespaces](https://github.com/settings/codespaces))
- Storage is free for the default dev container configuration

For detailed Codespaces setup and troubleshooting, see [CODESPACES.md](CODESPACES.md).

### Option 2: Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/eastmk-goblin-mode/FTC-WA-EventAssignment.git
   cd FTC-WA-EventAssignment
   ```

2. Create and activate a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt setuptools
   ```

4. Run setup file:
   ```bash
   bash setup.sh
   ```
5. Above step will generate a folder called .data where we will store input/output files.
   - Open the current directory to find the .data folder: ```open .``` for mac, or ```explorer .``` for windows
   - By default computer will hide files and folders that start with a dot.
      - For mac, Press (Command + Shift + .)
      - For windows, Open File Explorer -> Click View in the top menu bar -> Hover over Show, then click and check Hidden items.
7. For input files, we just used what were given

Kevin's original scripts (`assign_home_leagues.py`, `process_event_preferences.py`) read hardcoded paths under `./data/` and need the `uszipcode` package, which `requirements.txt` leaves out because it fails on Python 3.12. The `sorter/` package below replaces them.

## Assignment Methodology

1. Given a list of leagues and teams, assign teams to leagues based solely on event proximity. The goal here is to determine an optimal set of "Home League" assignments to reduce the overall travel requirements we ask of teams. At least on the initial pass it's unlikely that this will consider inter-team relationships or impassable boundaries (asking teams to drive over water), so manual adjustments may be required. In the given output all teams must have a home-league assignment.

2. Given a list of leagues, teams, home-league asignments, and submitted event preferences (priortized 1->N for a subset of teams), assign teams to their final event assignments. If a team doesn't submit event preferences they will be assigned to their home league. After that, we will go through the event-preference submissions in a deterministic-but-random order to assign teams to their highest-available preference, bypassing any leagues that are full. The edge case where a team doesn't get assigned to an event after submitted preferences needs to be considered, and if the algorithm doesn't assign a team one option could be to fall back on a team's home event.

In addition to the above functionality, there will likely be a script to ensure any submitted event preferences are valid against the public criteria.

## Drive-Time Sorter (FLL)

A zip-bucket greedy assignment algorithm for FLL with support for drive-time routing, covering the states listed in `sorter.toml` (Washington and Oregon by default). Located in the `sorter/` package.

### Quick Start

1. Put `teams.csv` and `events.csv` (and optionally `pre-assignments.csv`) in `.data/`. Notes: please make sure file names match exactly as `teams.csv` and `events.csv` and optionally `pre-assignments.csv` 
3. Check the settings in `sorter.toml`: the program, the file names, and the review thresholds. Every setting has a comment.
4. Run:
   ```bash
   python3 -m sorter.cli
   ```

The run starts by printing the settings it used. Without `.data/drive_matrix.csv` it uses straight-line miles; to add drive times (optional, one-time setup):
```bash
bash tools/enable_drive_times.sh
python3 -m sorter.cli
```

### Settings

`sorter.toml` holds every setting, grouped into `[files]`, `[sorting]` and `[review]`. To change a setting for one run without editing the file, pass the matching flag; `python3 -m sorter.cli --help` lists them. For example:
```bash
python3 -m sorter.cli --method largest --ferry-wait 60
python3 -m sorter.cli --config ftc.toml        # a second settings file, e.g. for FTC
```
A misspelled setting or a value of the wrong type stops the run with the setting named.

- **Program:** `program` = `FLL`, `FTC` or `FRC`. It fills the `program` column the map team needs.
- **Ordering:** `method` = `bump` (default; places zip groups with poor fallback options first), `largest` (Kevin's largest-zip-first) or `regret`.
- **Distance:** straight-line miles with no setup, or OSRM drive minutes with ferry handling once `enable_drive_times.sh` has run. `ferry_wait` adds dock time to ferry trips.
- **Pre-assignments:** used if the file exists. The run stops if it names a team or event that is not in this season's files.
- **Output:** a CSV in the column layout agreed with the map team, with travel times, distances and manual-review flags.

### Algorithm

Zip-bucket greedy: groups teams by zip code and assigns whole groups to events, keeping related teams together. The bump-cost ordering places teams with poor fallback options first, reducing travel for geographically constrained groups.

For methodology details and trade-offs, see the algorithm comparison analysis (to be added).

### File Formats

**Input CSVs:**
- `teams.csv`: `team_number,team_name,zip_code[,host]` (a non-blank `host` other than false/no/0 marks a host team)
- `events.csv`: `event_code,event_zip,capacity`
- `pre-assignments.csv` (optional): `event_code,team_number[,notes]`

**Output CSV** (one row per input team):
- **Required by the map team:** `team_id, team_name, team_zipCode, team_coordinates, event_id, event_zipCode, event_coordinates, program`
- **Sorting team columns:** `is_host_team`, `from_manual_override`, `manual_override_notes`, `drive_minutes`, `drive_distance`, `flagged_for_manual_review`, `flagged_reason`
- Booleans are written as `true` / `false`. `drive_minutes` and `drive_distance` are blank in straight-line runs.
- An unassigned team has an empty `event_id` and is always flagged.
- `flagged_reason` lists every rule the row hits, separated by `; `:

| Rule | `[review]` setting in sorter.toml (default) | Flag |
|---|---|---|
| Unassigned, with the reason (see below) | — | — |
| 3 or fewer teams in the zip | `small_zip` (3) | `--small-zip` |
| 30 or more teams in the zip | `large_zip` (30) | `--large-zip` |
| Assigned event over 40 miles | `assigned_miles` (40) | `--flag-miles` |
| Nearest event over 75 miles | `nearest_miles` (75) | `--flag-nearest-miles` |
| Travel over 90 drive minutes (straight-line miles without a matrix) | `travel_minutes` (90) | `--flag-over` |
| Looks closer on the map: an event nearer as the crow flies is 30+ minutes longer by road (water or mountains in the way; drive-matrix runs only) | `looks_closer_minutes` (30) | `--flag-looks-closer` |

Miles are drive miles for the route the sorter chose (ferry or road) when `.data/drive_matrix.csv` exists, straight-line miles otherwise.

**Event summary** (`.data/event_summary.csv`, set by `event_summary` in `[files]`): one row per event with `event_id, event_zipCode, capacity, teams, fill_percent, flagged_for_manual_review, flagged_reason`. An event with no teams is flagged `empty`; one filled below `underfilled_percent` of capacity (in `[review]`, default 50; flag `--flag-underfilled`) is flagged `under-filled`. The run summary lists the flagged events.
- Coordinates use WKT format: `POINT (longitude latitude)`

### Drive-Time Setup

**Requirements for OSRM routing:**
- Docker (Linux/Codespaces) or Homebrew osrm-backend (macOS)
- `osmium-tool` to merge state maps when `sorter.toml` lists more than one state (installed by the devcontainer)
- About 2 GB of disk per state for map data and the routing graph
- RAM: the graph build peaked at 4.7 GB for Washington alone, and more states need more. A 2-core/8 GB Codespace is borderline; see `CODESPACES.md` before choosing a larger machine, which costs more.

**What happens:**
1. Downloads the OpenStreetMap extract for each state in `sorter.toml` from Geofabrik (WA about 350 MB, OR about 240 MB)
2. Merges them into one map so routes that cross a state line exist
3. Builds the routing graph and starts a local OSRM server on port 5055
4. Pre-computes the drive matrix for every team zip × event zip in `.data/teams.csv` and `.data/events.csv`

**Privacy:** All routing happens locally. No team data leaves your machine.

### Region (which states are covered)

The `states` setting in `sorter.toml` (`states = ["WA", "OR"]`) controls both the zip table and the road map, so they always cover the same states. To add a state (for example Idaho), set `states = ["WA", "OR", "ID"]`, then rerun `bash setup.sh` and, for drive times, `bash tools/enable_drive_times.sh`.

### Zip overrides (when a zip centre routes badly)

Locations come from each zip's centre point. In a large zip that centre can land in a forest or on water, and every drive into the zip then comes out far too long. The `[zip_overrides]` section of `sorter.toml` replaces the centre with a public point you choose:

```toml
[zip_overrides]
"98027" = { lat = 47.5221, lon = -122.0280, note = "Issaquah High School" }
```

The repository ships with this one: the 98027 centre sits in Tiger Mountain State Forest and snapped to a gravel forest road, adding 50-60 minutes to every drive there. After adding or changing an override, rerun `bash setup.sh` (it prints each override it applied), then rebuild the drive matrix with `bash tools/enable_drive_times.sh`. A sign that a zip needs one: drives into it are much slower than drives into other venues, or many teams are flagged "looks closer on the map" toward the same event.

### Review map

`tools/make_map.py` turns the sorter's output into a one-page map for reviewing flags before handing off:

```bash
python3 -m sorter.cli
python3 tools/make_map.py --serve      # then open http://127.0.0.1:8765/map.html
```

- Each team is a dot colored by its event; flagged teams have a red outline and a dashed line to their event. Click a team for its event, drive time and flag reasons; event names in the popup are links that jump to that event's pin.
- The card on the right explains each review rule with its threshold and count, filters the map by rule, and lists the events with empty or under-filled ones first. Each section collapses: click its title. The Unassigned filter also shows or hides the card for teams with no location.
- Teams whose zip could not be located are listed in a card at the bottom left.

`--serve` writes `.data/map.html` and serves it on `127.0.0.1:8765` until Ctrl+C. The page has to come from a web server: opened as a file, OpenStreetMap blocks the map tiles because no HTTP Referer is sent. In a Codespace, open the forwarded **Review map** port from the Ports tab and keep its visibility **Private**. The page loads Leaflet (pinned by hash) and OpenStreetMap tiles; those servers see which area is viewed, not team data.

The map contains team names, which is why it is written to `.data/`. Do not commit or share it publicly.

### When teams come back unassigned

Each unassigned team's `flagged_reason` starts with `unassigned:` and one of these causes, and the run summary lists the zips under each:

| Cause (after `unassigned:`) | Meaning | Fix |
|---|---|---|
| `zip is in ID, not one of the states in sorter.toml` | The zip is real but outside the configured states | Add the state to `states` in `sorter.toml`, rerun setup |
| `zip code not found` | The zip is not in the US zip database | Check the team's zip for a typo |
| `missing drive times; rebuild the drive matrix` | The drive matrix was built from different team or event files | Start OSRM (`bash tools/osrm_setup.sh`), then run the `build_drive_matrix.py` command the sorter prints |
| `no event with room` | Every reachable event is full | Add capacity or place the team by hand |

The drive matrix only holds the zip pairs from the files it was built from. Rebuild it whenever the teams or events change; the map download and graph build are cached, so a rebuild takes seconds once OSRM is running.

### Setup Details

`setup.sh` (run automatically in Codespaces) builds `.data/zips.csv` for the states in `sorter.toml` with `tools/build_zip_table.py`. It downloads a 10.7 MB public zip database (US Census/USPS centroids) once and checks its SHA-256. Without network access, setup falls back to the committed `reference/wa_zips.csv`, which covers Washington only.

### Testing

```bash
python3 -m unittest discover -s tests -t .
```

The tests use only the standard library. One test compares a fresh Washington export with `reference/wa_zips.csv`; it is skipped until the zip database has been downloaded by `setup.sh`.

Smoke test on your own data:
```bash
python3 -m sorter.cli
```

Every input team appears once in the output. Placed teams have an `event_id`; `flagged_for_manual_review` marks rows to check, and unassigned teams are always flagged. The command exits 1 when any team is unassigned, so the run is not mistaken for complete.
