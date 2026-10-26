import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sorter import cli

ROOT = Path(__file__).resolve().parent.parent

ZIPS = {
    "98101": (47.61, -122.33, "Seattle", "King County"),
    "98402": (47.25, -122.44, "Tacoma", "Pierce County"),
    "97201": (45.51, -122.69, "Portland", "Multnomah County"),
}
ZIP_STATES = {"98101": "WA", "98402": "WA", "97201": "OR", "83702": "ID"}


class UnassignedReasonTest(unittest.TestCase):
    def reason(self, zip_code, mode="drive", missing_drive_time=True):
        return cli.unassigned_reason(zip_code, ZIPS, ZIP_STATES, {"WA", "OR"}, mode, missing_drive_time)

    def test_zip_in_an_unconfigured_state(self):
        self.assertEqual(self.reason("83702"), "zip is in ID, not one of the states in sorter.toml")

    def test_zip_that_does_not_exist(self):
        self.assertEqual(self.reason("98705"), "zip code not found")

    def test_drive_mode_zip_missing_from_matrix(self):
        self.assertEqual(self.reason("97201"), "missing drive times; rebuild the drive matrix")

    def test_zip_with_every_drive_time_but_every_event_full(self):
        self.assertEqual(self.reason("98101", missing_drive_time=False), "no event with room")

    def test_straight_line_mode_known_zip_is_capacity(self):
        self.assertEqual(self.reason("98101", mode="miles", missing_drive_time=False), "no event with room")


def write_csv(path, rows, header=None):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        w.writerows(rows)


class CliEndToEndTest(unittest.TestCase):
    """Runs the CLI as a subprocess on a tiny region with one team of every kind."""

    def setUp(self):
        d = self.d = Path(tempfile.mkdtemp())
        write_csv(d / "zips.csv", [
            ("98101", 47.61, -122.33, "Seattle", "King County", "WA", "STANDARD"),
            ("98402", 47.25, -122.44, "Tacoma", "Pierce County", "WA", "STANDARD"),
            ("97201", 45.51, -122.69, "Portland", "Multnomah County", "OR", "STANDARD"),
        ], ["zip", "lat", "lon", "city", "county", "state", "type"])
        write_csv(d / "zip_states.csv", [(z, s) for z, s in ZIP_STATES.items()], ["zip", "state"])
        write_csv(d / "events.csv", [("SEA", "98101", 2), ("TAC", "98402", 1)])
        write_csv(d / "teams.csv", [
            ("1", "Near", "98101"),
            ("2", "Portland", "97201"),
            ("3", "Boise", "83702"),
            ("4", "Typo", "98705"),
            ("5", "Tacoma A", "98402"),
            ("6", "Tacoma B", "98402"),
        ])
        write_csv(d / "drive.csv", [
            ("98101", "98402", 35, 30, 35, 30, 10),
            ("98402", "98402", 0, 0, 0, 0, 10),
        ], ["team_zip", "event_zip", "min_ferry_ok", "mi_ferry_ok", "min_no_ferry", "mi_no_ferry", "snap_m"])

    def run_cli(self, *extra):
        d = self.d
        # Own config, so the repo's sorter.toml and any local .data/ files can't leak in.
        (d / "sorter.toml").write_text(f'[files]\npre_assignments = "{d / "no-pre.csv"}"\n'
                                       f'event_summary = "{d / "events-out.csv"}"\n')
        cmd = [sys.executable, "-m", "sorter.cli", "--config", d / "sorter.toml",
               "--program", "FLL", "--teams", d / "teams.csv",
               "--events", d / "events.csv", "--zips", d / "zips.csv", "--zip-states", d / "zip_states.csv",
               "--out", d / "out.csv", *extra]
        result = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True)
        if not (d / "out.csv").exists():
            return result, {}
        with open(d / "out.csv") as f:
            reader = csv.DictReader(f)
            rows = {r["team_id"]: r for r in reader}
        self.header = reader.fieldnames
        return result, rows

    def test_columns_follow_the_data_dictionary(self):
        self.run_cli("--drive-matrix", self.d / "drive.csv")
        self.assertEqual(self.header, [
            "team_id", "team_name", "team_zipCode", "team_coordinates",
            "event_id", "event_zipCode", "event_coordinates", "program",
            "is_host_team", "from_manual_override", "manual_override_notes",
            "drive_minutes", "drive_distance", "flagged_for_manual_review", "flagged_reason",
        ])

    def test_drive_mode_unassigned_reasons_and_rebuild_hint(self):
        result, rows = self.run_cli("--drive-matrix", self.d / "drive.csv", "--small-zip", "0")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((rows["1"]["event_id"], rows["1"]["flagged_for_manual_review"]), ("SEA", "false"))
        self.assertEqual((rows["1"]["drive_minutes"], rows["1"]["drive_distance"]), ("0.0", "0.0"))
        self.assertEqual(rows["2"]["flagged_reason"], "unassigned: missing drive times; rebuild the drive matrix")
        self.assertEqual(rows["3"]["flagged_reason"], "unassigned: zip is in ID, not one of the states in sorter.toml")
        self.assertEqual(rows["4"]["flagged_reason"], "unassigned: zip code not found")
        # 98402 has a drive time only to TAC (1 seat); the 2-team zip group fits nowhere it
        # can be routed, and the missing 98402->SEA time is the real cause.
        self.assertEqual(rows["5"]["flagged_reason"], "unassigned: missing drive times; rebuild the drive matrix")
        self.assertEqual({rows[t]["flagged_for_manual_review"] for t in "2345"}, {"true"})
        self.assertIn("python3 tools/build_drive_matrix.py", result.stdout)
        self.assertIn("83702", result.stdout)

    def test_review_rules_combine_in_flagged_reason(self):
        write_csv(self.d / "events.csv", [("SEA", "98101", 10), ("TAC", "98402", 10)])
        result, rows = self.run_cli("--drive-matrix", self.d / "missing.csv")
        portland = rows["2"]
        self.assertEqual(portland["flagged_for_manual_review"], "true")
        self.assertEqual(portland["drive_minutes"], "")  # straight-line run: no drive figures
        reasons = portland["flagged_reason"].split("; ")
        self.assertEqual([r.split(" (")[0] for r in reasons], [
            "3 or fewer teams in zip",
            "assigned event over 40 straight-line miles",
            "nearest event over 75 straight-line miles",
            "travel over 90 straight-line miles",
        ])
        self.assertEqual(portland["drive_distance"], "")
        self.assertIn("Flagged for manual review", result.stdout)

    def test_manual_override_columns(self):
        write_csv(self.d / "events.csv", [("SEA", "98101", 10), ("TAC", "98402", 10)])
        (self.d / "pre.csv").write_text("TAC, 5, is_host_team, Coach asked to stay south\nSEA,6\n")
        _, rows = self.run_cli("--drive-matrix", self.d / "missing.csv", "--pre-assignments", self.d / "pre.csv")
        self.assertEqual([rows["5"][k] for k in ("event_id", "is_host_team", "from_manual_override",
                                                  "manual_override_notes")],
                         ["TAC", "true", "true", "Coach asked to stay south"])
        self.assertEqual([rows["6"][k] for k in ("event_id", "is_host_team", "from_manual_override",
                                                  "manual_override_notes")], ["SEA", "false", "true", ""])
        self.assertEqual([rows["1"][k] for k in ("event_id", "from_manual_override", "manual_override_notes")],
                         ["SEA", "false", ""])

    def test_ftc_override_file_keeps_notes_and_places_teams(self):
        write_csv(self.d / "events.csv", [("SEA", "98101", 10), ("TAC", "98402", 10)])
        (self.d / "pre.csv").write_text("SEA,5, ,COACH REQUESTS\r\nSEA,6,,registered late\r\n")
        result, rows = self.run_cli("--drive-matrix", self.d / "missing.csv", "--pre-assignments",
                                    self.d / "pre.csv")
        self.assertIn("Pre-assigned 2 teams", result.stdout)
        self.assertEqual({t: (rows[t]["event_id"], rows[t]["is_host_team"], rows[t]["manual_override_notes"])
                          for t in "56"},
                         {"5": ("SEA", "false", "COACH REQUESTS"), "6": ("SEA", "false", "registered late")})

    def test_old_comment_format_stops_the_run_with_the_fix(self):
        (self.d / "pre.csv").write_text("#pre TAC\nTAC,5\n")
        result, _ = self.run_cli("--drive-matrix", self.d / "drive.csv", "--pre-assignments", self.d / "pre.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("line 1: '#' comment lines are the old format", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_host_team_column_becomes_a_boolean(self):
        write_csv(self.d / "teams.csv", [("1", "Near", "98101", "yes"), ("5", "Tacoma A", "98402", ""),
                                         ("6", "Tacoma B", "98402", "no")])
        _, rows = self.run_cli("--drive-matrix", self.d / "drive.csv")
        self.assertEqual({t: rows[t]["is_host_team"] for t in rows}, {"1": "true", "5": "false", "6": "false"})

    def test_every_input_team_is_in_the_output(self):
        _, rows = self.run_cli("--drive-matrix", self.d / "drive.csv")
        self.assertEqual(sorted(rows), ["1", "2", "3", "4", "5", "6"])

    def test_config_file_alone_drives_a_run(self):
        d = self.d
        (d / "run.toml").write_text(
            'program = "FTC"\n'
            f'[files]\nteams = "{d / "teams.csv"}"\nevents = "{d / "events.csv"}"\n'
            f'output = "{d / "cfg-out.csv"}"\ndrive_matrix = "{d / "drive.csv"}"\n'
            f'pre_assignments = "{d / "no-pre.csv"}"\nevent_summary = "{d / "cfg-events.csv"}"\n'
            '[review]\nsmall_zip = 0\n')
        cmd = [sys.executable, "-m", "sorter.cli", "--config", d / "run.toml",
               "--zips", d / "zips.csv", "--zip-states", d / "zip_states.csv"]
        result = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True)
        self.assertIn("Settings from", result.stdout)
        with open(d / "cfg-out.csv") as f:
            rows = {r["team_id"]: r for r in csv.DictReader(f)}
        self.assertEqual(rows["1"]["program"], "FTC")
        self.assertEqual(rows["1"]["flagged_for_manual_review"], "false")  # small_zip = 0 from the file

    def test_pre_assignment_for_unknown_team_or_event_stops_the_run(self):
        (self.d / "pre.csv").write_text("SEA,1\nSEA,999\nNOPE,5\n")
        result, _ = self.run_cli("--drive-matrix", self.d / "drive.csv", "--pre-assignments", self.d / "pre.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("1 team number(s) not in the teams file: 999", result.stderr)
        self.assertIn("event code(s) not in the events file: NOPE", result.stderr)

    def test_looks_closer_on_the_map_is_flagged(self):
        d = self.d
        write_csv(d / "events.csv", [("SEA", "98101", 10), ("TAC", "98402", 10)])
        write_csv(d / "teams.csv", [("2", "Portland", "97201")])
        # Made-up times: TAC is nearer as the crow flies but 40 minutes longer by road.
        write_csv(d / "drive.csv", [
            ("97201", "98101", 60, 50, 60, 50, 10),
            ("97201", "98402", 100, 80, 100, 80, 10),
        ], ["team_zip", "event_zip", "min_ferry_ok", "mi_ferry_ok", "min_no_ferry", "mi_no_ferry", "snap_m"])
        _, rows = self.run_cli("--drive-matrix", d / "drive.csv", "--small-zip", "0")
        self.assertEqual(rows["2"]["event_id"], "SEA")
        self.assertRegex(rows["2"]["flagged_reason"],
                         r"looks closer on the map: TAC is [\d.]+ mi straight-line but 40.0 min farther by road")
        _, rows = self.run_cli("--drive-matrix", d / "drive.csv", "--small-zip", "0", "--flag-looks-closer", "45")
        self.assertNotIn("looks closer", rows["2"]["flagged_reason"])

    def test_event_summary_flags_empty_and_under_filled_events(self):
        d = self.d
        write_csv(d / "events.csv", [("SEA", "98101", 2), ("TAC", "98402", 10), ("SPARE", "98101", 4)])
        result, _ = self.run_cli("--drive-matrix", d / "missing.csv")
        with open(d / "events-out.csv") as f:
            rows = {r["event_id"]: r for r in csv.DictReader(f)}
        self.assertEqual(rows["SEA"]["flagged_for_manual_review"], "false")      # 2 of 2
        self.assertEqual(rows["TAC"]["flagged_reason"], "under-filled: 3 of 10 seats (30%, below 50%)")  # Tacoma pair + Portland
        self.assertEqual(rows["SPARE"]["flagged_reason"], "empty: no teams placed")
        self.assertIn("Events flagged for review (2 of 3)", result.stdout)

    def test_bad_config_stops_with_a_message(self):
        (self.d / "bad.toml").write_text("[review]\nsmall_zips = 2\n")
        result = subprocess.run([sys.executable, "-m", "sorter.cli", "--config", str(self.d / "bad.toml")],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown setting 'review.small_zips'", result.stderr)


if __name__ == "__main__":
    unittest.main()
