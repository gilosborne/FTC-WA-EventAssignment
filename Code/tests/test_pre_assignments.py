import tempfile
import unittest
from pathlib import Path

from sorter import cli
from sorter.cli import Override, PreAssignmentError
from tools import convert_pre_assignments


def load(text):
    path = Path(tempfile.mkdtemp()) / "pre.csv"
    path.write_text(text, newline="")
    return cli.load_pre_assignments(path)


class LoadPreAssignmentsTest(unittest.TestCase):
    def test_fll_rows_as_written_by_staff(self):
        self.assertEqual(load("NORTH-SUN,1001,is_host_team,testing host preassignment notes\n"
                              "SOUTH-SAT, 1002, because I am a chaos gremlin\n"), {
            "1001": Override("NORTH-SUN", True, "testing host preassignment notes"),
            "1002": Override("SOUTH-SAT", False, "because I am a chaos gremlin"),
        })

    def test_ftc_rows_with_blank_host_column(self):
        self.assertEqual(load("LeagueA,1003, ,COACH REQUESTS\r\nLeagueA,1004,,registered late\r\n"), {
            "1003": Override("LeagueA", False, "COACH REQUESTS"),
            "1004": Override("LeagueA", False, "registered late"),
        })

    def test_header_row_blank_lines_and_missing_optional_columns(self):
        self.assertEqual(load("event,team_id,is_host_team,notes\n\nSEA,1\nSEA,2,yes\n"), {
            "1": Override("SEA", False, ""),
            "2": Override("SEA", True, ""),
        })

    def test_unquoted_commas_stay_in_the_notes(self):
        self.assertEqual(load("SEA,1,,north, then south\n")["1"].notes, "north, then south")
        self.assertEqual(load('SEA,1,,"quoted, note"\n')["1"].notes, "quoted, note")

    def test_hash_comment_lines_are_the_old_format(self):
        with self.assertRaisesRegex(PreAssignmentError, r"line 1: .*old format.*convert_pre_assignments"):
            load("#COACH REQUESTS\nLeagueA,1003\n")

    def test_unknown_word_in_host_column_stops_the_run(self):
        with self.assertRaisesRegex(PreAssignmentError, r"line 2: is_host_team is 'maybe'"):
            load("SEA,1\nSEA,2,maybe,some note\n")

    def test_row_without_a_team_stops_the_run(self):
        with self.assertRaisesRegex(PreAssignmentError, r"line 1: needs an event and a team_id"):
            load("SEA\n")

    def test_missing_file_means_no_overrides(self):
        self.assertEqual(cli.load_pre_assignments(Path(tempfile.mkdtemp()) / "none.csv"), {})


class ConvertOldFormatTest(unittest.TestCase):
    def test_each_comment_becomes_the_note_for_the_rows_below_it(self):
        old = ("#\r\n#COACH REQUESTS\r\nLeagueA,1003\r\n#\r\n#registered late\r\nLeagueA,1004\r\n"
               "#\r\nLeagueB,1005\r\n")
        self.assertEqual(convert_pre_assignments.convert(old.splitlines()), [
            ("LeagueA", "1003", "", "COACH REQUESTS"),
            ("LeagueA", "1004", "", "registered late"),
            ("LeagueB", "1005", "", ""),
        ])

    def test_converted_file_loads_with_its_notes(self):
        out = Path(tempfile.mkdtemp()) / "new.csv"
        convert_pre_assignments.write(out, [("LeagueA", "1003", "", "COACH REQUESTS, again")])
        self.assertEqual(cli.load_pre_assignments(out),
                         {"1003": Override("LeagueA", False, "COACH REQUESTS, again")})


if __name__ == "__main__":
    unittest.main()
