import math
import unittest

from sorter import assign

ZIPS = {z: (0.0, 0.0, "", "") for z in ("A", "B", "C", "X")}


def table_distance(table):
    """Distance function backed by a {(team_zip, event_zip): cost} dict; missing pairs are inf."""
    return lambda a, b: 0.0 if a == b else table.get((a, b), math.inf)


class GreedyTest(unittest.TestCase):
    EVENTS = [{"code": "E1", "zip": "A", "cap": 2}, {"code": "E2", "zip": "B", "cap": 2}]

    def run_greedy(self, teams, dist, order="largest", locks=None):
        return assign.greedy(self.EVENTS, teams, ZIPS, table_distance(dist), order=order, locks=locks)

    def test_zip_group_goes_to_nearest_event_with_room(self):
        teams = [{"num": "1", "zip": "C"}, {"num": "2", "zip": "C"}]
        out = self.run_greedy(teams, {("C", "A"): 10, ("C", "B"): 5})
        self.assertEqual(out, {"1": "E2", "2": "E2"})

    def test_group_that_fits_nowhere_is_unassigned(self):
        teams = [{"num": str(i), "zip": "C"} for i in range(3)]
        out = self.run_greedy(teams, {("C", "A"): 10, ("C", "B"): 5})
        self.assertEqual(set(out.values()), {None})

    def test_unknown_zip_is_unassigned(self):
        out = self.run_greedy([{"num": "1", "zip": "ZZ"}], {})
        self.assertEqual(out, {"1": None})

    def test_locked_teams_stay_put_and_use_seats(self):
        teams = [{"num": "1", "zip": "C"}, {"num": "2", "zip": "C"}, {"num": "3", "zip": "C"}]
        out = self.run_greedy(teams, {("C", "A"): 10, ("C", "B"): 5}, locks={"1": "E2", "2": "E2"})
        self.assertEqual(out["1"], "E2")
        self.assertEqual(out["2"], "E2")
        self.assertEqual(out["3"], "E1")

    def test_no_computed_distance_means_unassigned_for_every_order(self):
        for order in ("largest", "bump", "regret"):
            with self.subTest(order=order):
                out = self.run_greedy([{"num": "1", "zip": "X"}], {("C", "A"): 1}, order=order)
                self.assertEqual(out, {"1": None})

    def test_partial_distances_only_use_events_that_have_one(self):
        for order in ("largest", "bump", "regret"):
            with self.subTest(order=order):
                out = self.run_greedy([{"num": "1", "zip": "X"}], {("X", "B"): 50}, order=order)
                self.assertEqual(out, {"1": "E2"})

    def test_every_team_appears_exactly_once(self):
        teams = [{"num": str(i), "zip": z} for i, z in enumerate("CCCXZ")]
        out = self.run_greedy(teams, {("C", "A"): 1, ("C", "B"): 2}, locks={"0": "E1"})
        self.assertEqual(sorted(out), sorted(t["num"] for t in teams))


if __name__ == "__main__":
    unittest.main()
