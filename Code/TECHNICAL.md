## FTC Washington Event Assignment

> Technical reference. Run the commands below from inside the `Code` folder. For step-by-step directions, see the README in the main folder.

This repository sorts FIRST teams into events or leagues so that teams drive as little as possible. You give it a list of teams with their zip codes and a list of events with their zip codes and seat counts. It places each team at a nearby event with room, writes the results to a spreadsheet file, and marks the placements a person should double-check.

It started as Kevin Emery's scripts for FTC leagues in Washington (see [FTC assignment plan](#ftc-assignment-plan)). The team sorter in the `sorter/` folder is the newer tool and works for FLL, FTC and FRC.

Team data never goes into this repository. Your files stay in a hidden folder called `.data`, which git is set to ignore.

## Running the sorter

The easiest way is GitHub Codespaces: a computer in the cloud that opens in your web browser, with everything already installed. Nothing has to be installed on your own computer. To set up your own computer instead, see [Installing on your own computer](#installing-on-your-own-computer).

1. **Create a codespace.**
   - Go to [github.com/eastmk-goblin-mode/FTC-WA-EventAssignment](https://github.com/eastmk-goblin-mode/FTC-WA-EventAssignment).
   - Click the green **Code** button, open the **Codespaces** tab, and click **Create codespace on main**.

2. **Wait for setup to finish.** This takes 1-2 minutes. The terminal at the bottom shows "Running postCreateCommand..." while it works. Setup creates the `.data` folder and a table of zip code locations.

3. **Add your files to the `.data` folder.** In the file list on the left, right-click `.data`, choose **Upload...**, and pick your files. Their names must be exactly `teams.csv` and `events.csv`, plus `pre-assignments.csv` if you are placing some teams by hand. [Your input files](#your-input-files) describes what goes in each.

4. **Check the settings.** Open `sorter.toml`. It sets the program (FLL, FTC or FRC), the file names, and when to flag a placement for review. Every setting has a comment next to it explaining what it does.

5. **Run the sorter.** Click in the terminal, type this and press Enter:
   ```bash
   python3 -m sorter.cli
   ```
   It first prints the settings it used, then a summary of how many teams were placed and flagged.

6. **Look at the results** in `.data/team_assignments.csv` and `.data/event_summary.csv`. See [Reading the results](#reading-the-results).

Codespaces are free for up to 120 core-hours a month on a personal account. That is about 60 hours on the default machine. A codespace stops on its own after 30 minutes without use; you can change that in your [Codespaces settings](https://github.com/settings/codespaces). [CODESPACES.md](CODESPACES.md) has more on cost, machine sizes and troubleshooting.

### Finding the hidden `.data` folder on your own computer

Computers hide files and folders whose names start with a dot, so `.data` may not show up when you look for it or when you pick files to upload.
- **Mac:** press Command + Shift + . (period) in Finder or in a file picker. Hidden folders, including `.data`, appear right away.
- **Windows:** open File Explorer, click **View** in the top menu bar, point to **Show**, and check **Hidden items**. The `.data` folder appears right away.

## Your input files

All input files are plain CSV files: one line per row, with values separated by commas. You can save them from Excel or Google Sheets with "Save as CSV". `teams.csv` and `events.csv` must not have a header row.

**`teams.csv`** has one line per team: team number, team name, zip code, and optionally a fourth value marking a host team.
```
1001,Example Robotics,98101
1002,Another Team,98402,host
```
Anything in the fourth column other than blank, false, no or 0 marks the team as a host.

**`events.csv`** has one line per event: event code (or league name), the venue's zip code, and how many teams it holds.
```
NORTH-SUN,98101,32
```

**`pre-assignments.csv`** is optional. Use it to place specific teams by hand. Each line has four columns, `event,team_id,is_host_team,notes`:
- **event:** the event code (FLL) or league name (FTC).
- **team_id:** the team number.
- **is_host_team:** write `is_host_team` (or yes/true) for a host team, or leave it blank.
- **notes:** why you placed the team there. The note is copied into the results.

For example:
```
NORTH-SUN,1001,is_host_team,testing host preassignment notes
SOUTH-SAT, 1002, because I am a chaos gremlin
LeagueA,1003, ,COACH REQUESTS
```
A header row is optional, and spaces around values are ignored. A line with only three values, like the second one above, also works: the third value is read as the note.

In the results, each of these teams has `from_manual_override` set to true and its note in `manual_override_notes`. A host mark here counts the same as one in `teams.csv`. The run stops if the file names a team or event that is not in this season's files.

Older pre-assignment files put comments on lines starting with `#` above the entries. That format now stops the run. To convert an old file, run this in the terminal:
```bash
python3 tools/convert_pre_assignments.py OLD.csv NEW.csv
```
Each comment becomes the note for the lines below it.

## Reading the results

**`.data/team_assignments.csv`** has one row for every team in `teams.csv`:
- **Placed, nothing to check:** `event_id` is filled in and `flagged_for_manual_review` is `false`.
- **Placed, worth a look:** `flagged_for_manual_review` is `true`, and `flagged_reason` lists every rule the placement hit, separated by semicolons.
- **Not placed:** `event_id` is empty. `flagged_reason` starts with `unassigned:` and says why; see [When teams come back unassigned](#when-teams-come-back-unassigned).

When any team is not placed, the sorter finishes with an error code (1), so an incomplete run isn't mistaken for a finished one.

These are the rules that flag a placement. Each limit can be changed in the `[review]` section of `sorter.toml`:

| A placement is flagged when | Setting (default) |
|---|---|
| The team was not placed (the reason follows) | none |
| Its zip code has 3 or fewer teams | `small_zip` (3) |
| Its zip code has 30 or more teams | `large_zip` (30) |
| Its event is more than 40 miles away | `assigned_miles` (40) |
| Even the nearest event is more than 75 miles away | `nearest_miles` (75) |
| The trip takes more than 90 minutes | `travel_minutes` (90) |
| Another event looks closer on a map but takes 30+ minutes longer to drive to, because of water or mountains (drive times only) | `looks_closer_minutes` (30) |

Without drive times, distances are straight-line miles, and the 90 limit applies to straight-line miles instead of minutes.

**`.data/event_summary.csv`** has one row per event: how many teams it got and how full it is. An event with no teams is flagged `empty`. An event filled below half its seats is flagged `under-filled`; change that share with `underfilled_percent` in `[review]`. The summary the sorter prints lists the flagged events too.

### When teams come back unassigned

| Reason after `unassigned:` | What it means | What to do |
|---|---|---|
| `zip is in ID, not one of the states in sorter.toml` | The zip code is real but in a state the sorter doesn't cover | Add the state to `states` in `sorter.toml` and rerun setup; see [Which states are covered](#which-states-are-covered) |
| `zip code not found` | The zip code doesn't exist | Check the team's zip code for a typo, or place the team with a pre-assignment |
| `missing drive times; rebuild the drive matrix` | The drive times were made from different team or event files | Rebuild them with `bash tools/enable_drive_times.sh`; the sorter also prints the exact command for rebuilding only the drive times. See [Drive times](#drive-times) |
| `no event with room` | Every event the team could reach is full | Add seats, or place the team with a pre-assignment |

## Review map

The review map shows every placement on a map so you can spot odd ones before handing off. In the terminal, after running the sorter:
```bash
python3 tools/make_map.py --serve
```
In a codespace, a notice offers to open **Review map**. Click **Open in Browser**, or open it from the **Ports** tab. Leave the port set to **Private**, because the map shows team names. On your own computer, open [http://127.0.0.1:8765/map.html](http://127.0.0.1:8765/map.html). Press Ctrl+C in the terminal when you're done.

- Each team is a dot, colored by its event. Flagged teams have a red outline and a dashed line to their event.
- Click a team to see its event, drive time and flags. Event names in the popup are links that jump to that event on the map.
- The card on the right explains each flag with its limit and how many teams it caught. Its checkboxes filter the map, and it lists the events, with empty and under-filled ones first. Click any section title to fold it away. The Unassigned checkbox also shows or hides the card for teams that couldn't be located.
- Teams whose zip code couldn't be found are listed in a card at the bottom left.

The map is saved as `.data/map.html`. It contains team names, so don't commit it or share it publicly. It has to be opened through the command above: opened directly as a file, the background map is blocked. The map's background images come from OpenStreetMap, which sees which area is being viewed but no team data.

## Technical reference

### Settings

`sorter.toml` holds every setting, grouped into `[files]`, `[sorting]` and `[review]`. To change a setting for one run without editing the file, add the matching option to the command; `python3 -m sorter.cli --help` lists them. For example:
```bash
python3 -m sorter.cli --method largest --ferry-wait 60
python3 -m sorter.cli --config ftc.toml        # use a second settings file, e.g. for FTC
```
A misspelled setting or a value of the wrong type stops the run and names the setting.

- **Program:** `program` = `FLL`, `FTC` or `FRC`. It fills the `program` column the map project needs.
- **Ordering:** `method` = `bump` (the default; places zip groups with poor second choices first), `largest` (Kevin's largest-zip-first) or `regret`.
- **Distance:** straight-line miles with no setup, or drive minutes with ferry handling once drive times are set up. `ferry_wait` adds dock time to trips that use a ferry.

Option names for the review limits: `--small-zip`, `--large-zip`, `--flag-miles`, `--flag-nearest-miles`, `--flag-over` (travel), `--flag-looks-closer` and `--flag-underfilled`.

### How teams are placed

Teams are grouped by zip code, and each group is placed together at the nearest event with room, which keeps teams from the same area together. With the `bump` method, groups that would be hurt most by missing their nearest event are placed first, which reduces travel for teams with few nearby options. Pre-assigned teams are placed before anyone else.

### Output columns

`team_assignments.csv` uses the column layout agreed with the map project:
- **For the map project:** `team_id, team_name, team_zipCode, team_coordinates, event_id, event_zipCode, event_coordinates, program`
- **For the sorting team:** `is_host_team`, `from_manual_override`, `manual_override_notes`, `drive_minutes`, `drive_distance`, `flagged_for_manual_review`, `flagged_reason`

Yes/no values are written as `true` / `false`. `drive_minutes` and `drive_distance` are blank when there are no drive times. Coordinates use the format `POINT (longitude latitude)`. Miles are driving miles for the route chosen (ferry or road) when drive times exist, and straight-line miles otherwise.

`event_summary.csv` (set by `event_summary` in `[files]`) has the columns `event_id, event_zipCode, capacity, teams, fill_percent, flagged_for_manual_review, flagged_reason`.

### Drive times

Without drive times, the sorter uses straight-line distance, which ignores water and mountains. To use driving times instead (a one-time setup), run:
```bash
bash tools/enable_drive_times.sh
python3 -m sorter.cli
```

The setup:
1. Downloads the OpenStreetMap road map for each state in `sorter.toml` from Geofabrik (Washington about 350 MB, Oregon about 240 MB).
2. Joins them into one map, so routes that cross a state line exist.
3. Builds a local route planner (OSRM) and starts it on port 5055.
4. Works out the drive time from every team zip code to every event zip code in `.data/teams.csv` and `.data/events.csv`, and saves them as `.data/drive_matrix.csv`.

It needs Docker (in a codespace) or the Homebrew `osrm-backend` package (on a Mac), `osmium-tool` to join state maps (already installed in a codespace), and about 2 GB of disk per state. Building the route planner used 4.7 GB of memory for Washington alone, and more for each added state. That is tight on the default 8 GB codespace; read the memory note in [CODESPACES.md](CODESPACES.md#machine-types--performance) first.

Rebuild the drive times whenever the teams or events change. The map download and route planner are saved, so a rebuild takes seconds once the route planner is running. All routing happens on your own machine or codespace; no team data is sent anywhere.

### Which states are covered

The `states` setting in `sorter.toml` (`states = ["WA", "OR"]`) controls both the zip code table and the road map, so they always cover the same states. To add a state, for example Idaho, set `states = ["WA", "OR", "ID"]`, then run `bash setup.sh` again and, if you use drive times, `bash tools/enable_drive_times.sh`.

### Zip overrides (when a zip code's location is wrong)

Each zip code's location is its center point. In a large zip code that center can land in a forest or on water, which makes every drive there look far too long. The `[zip_overrides]` section of `sorter.toml` replaces the center with a public location you choose:

```toml
[zip_overrides]
"98027" = { lat = 47.5221, lon = -122.0280, note = "Issaquah High School" }
```

The repository includes this one: the 98027 center sits in Tiger Mountain State Forest and connected to a gravel forest road, adding 50-60 minutes to every drive there. After adding or changing an override, run `bash setup.sh` (it lists each override it used), then rebuild the drive times with `bash tools/enable_drive_times.sh`. Signs that a zip code needs one: drives into it are much slower than drives to other venues, or many teams are flagged "looks closer on the map" toward the same event.

### Installing on your own computer

You need Python 3.12 or newer and, ideally, the [uv](https://github.com/astral-sh/uv) package manager (pip also works).

1. Download the repository:
   ```bash
   git clone https://github.com/eastmk-goblin-mode/FTC-WA-EventAssignment.git
   cd FTC-WA-EventAssignment
   ```
2. Create and turn on a Python environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install the dependencies:
   ```bash
   uv pip install -r requirements.txt setuptools
   ```
4. Run the setup file:
   ```bash
   bash setup.sh
   ```
5. The setup step creates the `.data` folder, where the input and output files go. It is hidden by default; see [Finding the hidden `.data` folder](#finding-the-hidden-data-folder-on-your-own-computer).
6. Add your input files to `.data` and continue from step 4 of [Running the sorter](#running-the-sorter). For our own testing, we used the files we were given.

`setup.sh` (run automatically in a codespace) builds `.data/zips.csv` for the states in `sorter.toml`. It downloads a 10.7 MB public zip code database (US Census/USPS center points) once and checks that the download is intact. Without internet access, it falls back to the included `reference/wa_zips.csv`, which covers Washington only.

Kevin's original scripts (`assign_home_leagues.py`, `process_event_preferences.py`) read fixed file paths under `./data/` and need the `uszipcode` package, which doesn't install on Python 3.12, so `requirements.txt` leaves it out. The sorter replaces them.

### Testing

```bash
python3 -m unittest discover -s tests -t .
```

The tests need nothing beyond Python itself. One test compares a fresh Washington zip table with `reference/wa_zips.csv`; it is skipped until `setup.sh` has downloaded the zip code database.

## FTC assignment plan

Kevin's original plan for FTC in Washington has two steps:

1. Given a list of leagues and teams, assign teams to leagues based only on how close they are. The goal is a set of "home league" assignments that reduces the total travel asked of teams. At least at first, this probably won't account for relationships between teams or barriers like water, so manual adjustments may be needed. Every team must get a home league.

2. Given the leagues, teams, home-league assignments and the event preferences teams submit (ranked 1 to N, from some of the teams), assign each team to its final events. Teams that don't submit preferences go to their home league. Then the submitted preferences are processed in a random but repeatable order, giving each team its highest choice that still has room and skipping full leagues. If a team ends up with no event after its preferences, one option is to fall back to its home league.

There will probably also be a script that checks submitted event preferences against the published rules.
