"""Run settings from sorter.toml, with command-line flags taking precedence."""
import tomllib
from pathlib import Path

DEFAULT_PATH = Path("sorter.toml")
PROGRAMS = ("FLL", "FTC", "FRC")
METHODS = ("bump", "largest", "regret")

DEFAULTS = {
    "program": None,
    "teams": ".data/teams.csv",
    "events": ".data/events.csv",
    "pre_assignments": ".data/pre-assignments.csv",
    "out": ".data/team_assignments.csv",
    "drive_matrix": ".data/drive_matrix.csv",
    "method": "bump",
    "ferry_wait": 30.0,
    "small_zip": 3,
    "large_zip": 30,
    "flag_miles": 40.0,
    "flag_nearest_miles": 75.0,
    "flag_over": 90.0,
    "flag_looks_closer": 30.0,
    "flag_underfilled": 50.0,
    "event_summary": ".data/event_summary.csv",
}

# (section, key) in sorter.toml -> (setting name, accepted types). Setting None = read elsewhere.
KEYS = {
    (None, "program"): ("program", (str,)),
    (None, "states"): (None, (list,)),  # read by tools/region.py
    ("files", "teams"): ("teams", (str,)),
    ("files", "events"): ("events", (str,)),
    ("files", "pre_assignments"): ("pre_assignments", (str,)),
    ("files", "output"): ("out", (str,)),
    ("files", "drive_matrix"): ("drive_matrix", (str,)),
    ("sorting", "method"): ("method", (str,)),
    ("sorting", "ferry_wait"): ("ferry_wait", (int, float)),
    ("review", "small_zip"): ("small_zip", (int,)),
    ("review", "large_zip"): ("large_zip", (int,)),
    ("review", "assigned_miles"): ("flag_miles", (int, float)),
    ("review", "nearest_miles"): ("flag_nearest_miles", (int, float)),
    ("review", "travel_minutes"): ("flag_over", (int, float)),
    ("review", "looks_closer_minutes"): ("flag_looks_closer", (int, float)),
    ("review", "underfilled_percent"): ("flag_underfilled", (int, float)),
    ("files", "event_summary"): ("event_summary", (str,)),
}
SECTIONS = {s for s, _ in KEYS if s}
OTHER_SECTIONS = {"zip_overrides"}  # read by tools/build_zip_table.py, which validates its entries


class ConfigError(Exception):
    pass


def read(path):
    """Settings in a sorter.toml file, keyed by setting name. Raises ConfigError on any problem."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None

    settings = {}
    for name, value in data.items():
        if name in OTHER_SECTIONS:
            if not isinstance(value, dict):
                raise ConfigError(f"{path}: [{name}] must be a section")
            continue
        if name in SECTIONS:
            if not isinstance(value, dict):
                raise ConfigError(f"{path}: [{name}] must be a section")
            items = [((name, k), v) for k, v in value.items()]
        else:
            items = [((None, name), value)]
        for key, v in items:
            label = ".".join(p for p in key if p)
            if key not in KEYS:
                raise ConfigError(f"{path}: unknown setting '{label}'")
            setting, types = KEYS[key]
            if isinstance(v, bool) or not isinstance(v, types):
                raise ConfigError(f"{path}: '{label}' has the wrong type ({type(v).__name__})")
            if setting:
                settings[setting] = v
    return settings


def resolve(cli, path=None):
    """Built-in defaults, overlaid by the config file, overlaid by flags given on the command line.

    cli: {setting: value or None}; None means the flag was not given.
    path: an explicit --config path (must exist), or None for ./sorter.toml if present.
    Returns (settings, path actually read or None).
    """
    if path is not None:
        if not Path(path).exists():
            raise ConfigError(f"config file not found: {path}")
        used = Path(path)
    else:
        used = DEFAULT_PATH if DEFAULT_PATH.exists() else None

    settings = dict(DEFAULTS)
    if used:
        settings.update(read(used))
    settings.update({k: v for k, v in cli.items() if v is not None})

    if settings["program"] not in PROGRAMS:
        raise ConfigError(f"program must be one of {', '.join(PROGRAMS)} "
                          f"(set it in sorter.toml or pass --program); got {settings['program']!r}")
    if settings["method"] not in METHODS:
        raise ConfigError(f"method must be one of {', '.join(METHODS)}; got {settings['method']!r}")
    return settings, used
