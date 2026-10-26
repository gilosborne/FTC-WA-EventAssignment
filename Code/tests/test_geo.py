import math
import unittest

from sorter import geo

ZIPS = {
    "98101": (47.61, -122.33, "Seattle", "King County"),
    "98402": (47.25, -122.44, "Tacoma", "Pierce County"),
}


class StraightLineTest(unittest.TestCase):
    def test_seattle_to_tacoma_is_about_25_miles(self):
        self.assertAlmostEqual(geo.miles_straight_line("98101", "98402", ZIPS), 25.3, delta=0.5)

    def test_unknown_zip_is_infinite_not_an_error(self):
        self.assertEqual(geo.miles_straight_line("98101", "00000", ZIPS), math.inf)


class DriveMinutesTest(unittest.TestCase):
    MATRIX = {
        ("98101", "98402"): (35.0, 35.0),    # road route, no ferry involved
        ("98070", "98402"): (40.0, None),    # island: ferry is the only way off
        ("98110", "98101"): (45.0, 120.0),   # ferry is much faster than driving around
        ("98368", "98277"): (82.0, 95.0),    # ferry slightly faster before the dock wait
    }

    def minutes(self, a, b, wait=30.0):
        return geo.drive_minutes(a, b, self.MATRIX, ferry_wait=wait)

    def test_same_zip_is_zero(self):
        self.assertEqual(self.minutes("98101", "98101"), 0.0)

    def test_road_route_ignores_ferry_wait(self):
        self.assertEqual(self.minutes("98101", "98402"), 35.0)

    def test_ferry_only_route_pays_the_wait(self):
        self.assertEqual(self.minutes("98070", "98402"), 70.0)

    def test_ferry_route_pays_the_wait_when_still_faster(self):
        self.assertEqual(self.minutes("98110", "98101"), 75.0)

    def test_drive_around_wins_when_the_wait_makes_the_ferry_slower(self):
        self.assertEqual(self.minutes("98368", "98277"), 95.0)
        self.assertEqual(self.minutes("98368", "98277", wait=0), 82.0)

    def test_pair_missing_from_matrix_is_infinite_not_an_error(self):
        self.assertEqual(self.minutes("98052", "98020"), math.inf)

    def test_pair_osrm_could_not_route_is_infinite(self):
        self.assertEqual(geo.drive_minutes("A", "B", {("A", "B"): (None, None)}), math.inf)


class DriveMilesTest(unittest.TestCase):
    """Miles must describe the same route drive_minutes chose."""
    MINUTES = DriveMinutesTest.MATRIX
    MILES = {
        ("98101", "98402"): (30.0, 30.0),
        ("98070", "98402"): (20.0, None),
        ("98110", "98101"): (12.0, 90.0),
        ("98368", "98277"): (25.0, 70.0),
    }

    def miles(self, a, b, wait=30.0):
        return geo.drive_miles(a, b, self.MINUTES, self.MILES, ferry_wait=wait)

    def test_same_zip_is_zero(self):
        self.assertEqual(self.miles("98101", "98101"), 0.0)

    def test_road_route(self):
        self.assertEqual(self.miles("98101", "98402"), 30.0)

    def test_ferry_only_route(self):
        self.assertEqual(self.miles("98070", "98402"), 20.0)

    def test_ferry_route_when_it_wins(self):
        self.assertEqual(self.miles("98110", "98101"), 12.0)

    def test_road_miles_when_the_wait_makes_driving_around_faster(self):
        self.assertEqual(self.miles("98368", "98277"), 70.0)
        self.assertEqual(self.miles("98368", "98277", wait=0), 25.0)

    def test_missing_pair_is_infinite(self):
        self.assertEqual(self.miles("98052", "98020"), math.inf)

    def test_matrix_file_round_trip(self):
        import csv, tempfile
        from pathlib import Path
        path = Path(tempfile.mkdtemp()) / "m.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["team_zip", "event_zip", "min_ferry_ok", "mi_ferry_ok", "min_no_ferry", "mi_no_ferry", "snap_m"])
            w.writerow(["98070", "98402", 40, 20, "", "", 5])
        self.assertEqual(geo.load_drive_matrix(path), {("98070", "98402"): (40.0, None)})
        self.assertEqual(geo.load_drive_miles(path), {("98070", "98402"): (20.0, None)})


if __name__ == "__main__":
    unittest.main()
